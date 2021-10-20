import json
import functools

from asgiref.sync import async_to_sync
from urllib.parse import parse_qs
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer
from channels.utils import await_many_dispatch
from channels.exceptions import StopConsumer, InvalidChannelLayerError, AcceptConnection, DenyConnection


class InterfaceConsumer(AsyncWebsocketConsumer):

    async def websocket_connect(self, message):
        """
        Called when a WebSocket connection is opened.
        """
        try:
            rooms = await self.get_all_rooms()

            if rooms:
                for room in rooms:
                    self.room = (room.split(':'))[2]
                    members = await self.get_room_members()

                    if len(members) == 1:
                        if members[0].startswith(self.username):
                            await self.readd(members[0])
                            break
                        else:
                            await self.channel_layer.group_add(self.room,
                                                               self.channel_name)
                            await self.hack_tool(hset=[[self.room, 'room_guest', self.username]],
                                                 expire=[[self.room, 3600]]
                                                 )
                            break
                    else:
                        if members[0].startswith(self.username):
                            await self.readd(members[0])
                            break
                        elif members[1].startswith(self.username):
                            await self.readd(members[1])
                            break
                        else:
                            await self.new_room()
                            break
            else:
                await self.new_room()
        except AttributeError:
            raise InvalidChannelLayerError(
                "BACKEND is unconfigured or doesn't support groups"
            )
        try:
            await self.connect()
        except AcceptConnection:
            await self.accept()
        except DenyConnection:
            await self.close()

    async def __call__(self, scope, receive, send):
        """
        Dispatches incoming messages to type-based handlers asynchronously.
        """
        self.scope = scope
        self.values = self.scope['query_string']
        self.values = parse_qs(self.values.decode())
        # Распознаём пользователя по логину
        self.username = self.values['username'][0]
        self.room = None

        # Initialize channel layer
        self.channel_layer = get_channel_layer(self.channel_layer_alias)
        if self.channel_layer is not None:
            self.channel_name = await self.channel_layer.new_channel(prefix=self.username)
            self.channel_receive = functools.partial(
                self.channel_layer.receive, self.channel_name
            )
        # Store send function
        if self._sync:
            self.base_send = async_to_sync(send)
        else:
            self.base_send = send
        # Pass messages in from channel layer or client to dispatch method
        try:
            if self.channel_layer is not None:
                await await_many_dispatch(
                    [receive, self.channel_receive], self.dispatch
                )
            else:
                await await_many_dispatch([receive], self.dispatch)
        except StopConsumer:
            # Exit cleanly
            pass

    async def connect(self):
        # Подключаемся
        await self.accept()
        await self.get_data()
        await self.send(text_data=json.dumps({
            'context': 'connect',
            'data': self.data
        }))

    async def disconnect(self, close_code):
        if close_code == 'exit_room':
            await self.channel_layer.group_send(
                self.room,
                {
                    'type': 'notification',
                    'message': 'exit_room'
                }
            )
            await self.hack_tool(delete=[self.room])
            await self.hack_tool(delete=['asgi:group:' + self.room])

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        # Получаем контекст запроса со стороны пользователя
        context = text_data_json['context']
        await self.get_data()
        room_guest = self.data['room_guest']
        room_member = self.data['room_member']

        if room_guest != self.username:
            self.enemy = room_guest
        else:
            self.enemy = room_member

        if context == 'exit_room':
            await self.disconnect(close_code='exit_room')
        elif context == 'send_message':
            await self.redirect_message(text_data_json)
        elif context == 'player_ready':
            await self.ready_handler(text_data_json)
        elif context == 'shot':
            await self.shot_handler(text_data_json)
        elif context == 'miss':
            await self.miss_handler(text_data_json)
        elif context == 'hit':
            await self.hit_handler(text_data_json)

    async def chat_message(self, event):
        message = event['message']

        await self.send(text_data=json.dumps({
            'context': 'message',
            'message': message
        }))

    async def notification(self, event):
        message = event['message']

        await self.send(text_data=json.dumps({
            'context': 'notification',
            'type': message
        }))

    async def action(self, event):
        action_type = event['action_type']
        params = event['params']

        await self.send(text_data=json.dumps({
            'context': 'action',
            'action_type': action_type,
            'params': params
        }))

    async def hack_tool(self, **kwargs):
        try:
            async with self.channel_layer.connection(0) as connection:
                result = []
                for k, v in kwargs.items():
                    val_numb = 0
                    if len(kwargs.items()) > 1:
                        if len(v) > 2:
                            for i in v[val_numb]:
                                res = await connection.__getattribute__(k)(*v[val_numb])
                                result.append(res)
                                val_numb += 1
                        else:
                            res = await connection.__getattribute__(k)(*v[0])
                            result.append(res)
                    else:
                        res = await connection.__getattribute__(k)(v[0])
                        return res
            return result
        except Exception as e:
            print(e)
            return 'None'

    async def get_data(self):
        data = {k.decode('utf8'): v.decode('utf8')
                for k, v in
                (await self.hack_tool(hgetall=[self.room])).items()}
        self.data = data

    async def readd(self, member):
        await self.channel_layer.group_discard(
            self.room,
            member
        )
        await self.channel_layer.group_add(self.room,
                                           self.channel_name)

    async def get_all_rooms(self):
        keys = [
            x.decode("utf8") for x in await self.hack_tool(keys=['*'])
        ]
        rooms = []
        for key in keys:
            if key.startswith('asgi:group:'):
                rooms.append(key)
        return rooms

    async def get_room_members(self):
        members = [
            x.decode("utf8") for x
            in await self.hack_tool(zrange=['asgi:group:' + self.room,
                                            0, -1])
        ]
        return members

    async def new_room(self):
        try:
            r, last_room_number = (
                (self.room[-1].split(':'))[2]).split('_')
            self.room = r + '_' + str(int(last_room_number) + 1)
            await self.channel_layer.group_add(self.room,
                                               self.channel_name)
            await self.hack_tool(hset=[
                [self.room,
                 'room_member', self.username],
                [self.room,
                 'room_guest', 'None'],
                [self.room,
                 'messages', '[]']],
                expire=[[self.room, 3600]]
            )
        except:
            try:
                self.room = 'room_1'
                await self.channel_layer.group_add(self.room,
                                                   self.channel_name)
                await self.hack_tool(hset=[
                    [self.room,
                     'room_member', self.username],
                    [self.room,
                     'room_guest', 'None'],
                    [self.room,
                     'messages', '[]']],
                    expire=[[self.room, 3600]]
                )
            except Exception as e:
                print(e)

    async def redirect_message(self, text_data_json):
        message = text_data_json['message']
        messages = json.loads(self.data['messages'])

        try:
            message = {'id': str(int((messages[-1])['id'])+1),
                       'sender': self.username,
                       'message': message}
        except:
            message = {'id': '1',
                       'sender': self.username,
                       'message': message}
        await self.channel_layer.group_send(
            self.room,
            {
                'type': 'chat_message',
                'message': message
            }
        )
        messages.append(message)
        messages = json.dumps(messages)
        await self.hack_tool(hset=[[self.room, 'messages', messages]],
                             expire=[[self.room, 3600]]
                             )

    async def ready_handler(self, text_data_json):
        selected_cells = json.dumps(text_data_json['selected_cells'])
        await self.hack_tool(hset=[[self.room,
                             self.username + ':selected_cells',
                             selected_cells]],
                             expire=[[self.room, 3600]])
        room_pool = await self.hack_tool(hlen=[self.room])
        if room_pool == 5:
            await self.hack_tool(hset=[[self.room,
                                        self.username + ':access_to_shot',
                                        'false']],
                                 expire=[[self.room, 3600]])
            await self.hack_tool(hset=[[self.room,
                                        self.enemy + ':access_to_shot',
                                        'true']],
                                 expire=[[self.room, 3600]])
            await self.hack_tool(hset=[[self.room,
                                 'game_status',
                                       'started']],
                                 expire=[[self.room, 3600]])
            await self.channel_layer.group_send(
                self.room,
                {
                    'type': 'notification',
                    'message': 'start_game'
                }
            )

    async def shot_handler(self, text_data_json):
        try:
            try:
                selected_cells = self.data[self.enemy + ':selected_cells']
            except:
                selected_cells = []
            try:
                dead_cells = self.data[self.enemy + ':dead_cells']
            except:
                dead_cells = []
            try:
                miss_cells = self.data[self.username + ':miss_cells']
            except:
                miss_cells = []

            if dead_cells:
                dead_cells = json.loads(dead_cells)
            if selected_cells:
                selected_cells = json.loads(selected_cells)
            if miss_cells:
                miss_cells = json.loads(miss_cells)

            if len(dead_cells) < 20:
                if text_data_json['cell'] in selected_cells:
                    dead_cells.append(text_data_json['cell'])
                    dead_cells = json.dumps(dead_cells)
                    await self.hack_tool(hset=[[self.room,
                                                self.enemy + ':dead_cells',
                                                dead_cells]],
                                         expire=[[self.room, 3600]])
                    await self.hack_tool(hset=[[self.room,
                                                self.username + ':hit_cells',
                                                dead_cells]],
                                         expire=[[self.room, 3600]])
                    await self.hack_tool(hset=[[self.room,
                                                self.username + ':access_to_shot',
                                                'false']],
                                         expire=[[self.room, 3600]])
                    await self.hack_tool(hset=[[self.room,
                                                self.enemy + ':access_to_shot',
                                                'true']],
                                         expire=[[self.room, 3600]])

                    await self.channel_layer.group_send(
                        self.room,
                        {
                            'type': 'action',
                            'action_type': 'hit',
                            'params': '{},{}'.format(self.enemy, text_data_json['cell'])
                        }
                    )
                else:
                    miss_cells.append(text_data_json['cell'])
                    miss_cells = json.dumps(miss_cells)

                    await self.hack_tool(hset=[[self.room,
                                                self.username + ':miss_cells',
                                                miss_cells]],
                                         expire=[[self.room, 3600]])
                    await self.hack_tool(hset=[[self.room,
                                                self.username + ':access_to_shot',
                                                'false']],
                                         expire=[[self.room, 3600]])
                    await self.hack_tool(hset=[[self.room,
                                                self.enemy + ':access_to_shot',
                                                'true']],
                                         expire=[[self.room, 3600]])
                    await self.channel_layer.group_send(
                        self.room,
                        {
                            'type': 'action',
                            'action_type': 'miss',
                            'params': '{},{}'.format(self.username, text_data_json['cell'])
                        }
                    )
            else:
                await self.channel_layer.group_send(
                    self.room,
                    {
                        'type': 'action',
                        'action_type': 'lose',
                        'params': '{}'.format(self.enemy)
                    }
                )
        except Exception as e:
            print(e)
