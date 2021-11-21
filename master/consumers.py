import json
import functools

from urllib.parse import parse_qs
from asgiref.sync import async_to_sync

from channels.layers import get_channel_layer
from channels.utils import await_many_dispatch
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.exceptions import (StopConsumer, InvalidChannelLayerError,
                                 AcceptConnection, DenyConnection)


class InterfaceConsumer(AsyncWebsocketConsumer):

    async def websocket_connect(self, message):
        """
        Called when a WebSocket connection is opened.
        """
        try:
            groups = await self.get_all_groups()

            if groups:
                for group in groups:
                    self.group = (group.split(':'))[2]
                    members = await self.get_group_members()

                    if len(members) == 1:
                        if members[0].startswith(self.username):
                            await self.readd(members[0])
                            break
                        else:
                            await self.channel_layer.group_add(
                                self.group,
                                self.channel_name
                            )
                            await self.redis_connection_manager(hset=[
                                [self.group, 'room_guest', self.username]
                            ], expire=[[self.group, 3600]])
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
        self.group = None
        # Initialize channel layer
        self.channel_layer = get_channel_layer(self.channel_layer_alias)

        if self.channel_layer is not None:
            self.channel_name = await self.channel_layer.new_channel(
                prefix=self.username
            )
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
        """
        Подключаемся и отправляем состояние комнаты.

        Connect and send the state of the room.
        """
        await self.accept()
        await self.get_data()
        await self.send(text_data=json.dumps({'context': 'connect',
                                              'data': self.data}))

    async def disconnect(self, close_code):
        """
        Отключаем пользователей от группы и удаляем состояние комнаты при
        выходе одного из пользователей.

        Disconnect users from the group and delete the room state when
        logging out of one of the users.
        """
        if close_code == 'exit_room':
            await self.channel_layer.group_send(self.group,
                                                {'type': 'notification',
                                                 'message': 'exit_room'})
            await self.redis_connection_manager(delete=[self.group])
            await self.redis_connection_manager(delete=['asgi:group:' +
                                                        self.group])

    async def receive(self, text_data):
        """
        Главный обработчик.

        Main handler.
        """
        text_data_json = json.loads(text_data)
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

    async def chat_message(self, event):
        """
        Отправляет сообщение группе с контекстом 'сообщение'.

        Sends a message to the group with the context 'message'.
        """
        message = event['message']

        await self.send(text_data=json.dumps({'context': 'message',
                                              'message': message}))

    async def notification(self, event):
        """
        Отправляет сообщение группе с контекстом 'уведомление'.

        Sends a message to the group with the context 'notification'.
        """
        message = event['message']

        await self.send(text_data=json.dumps({'context': 'notification',
                                              'type': message}))

    async def action(self, event):
        """
        Отправляет сообщение группе с контекстом 'действие'
        (выстрел, промах, попадание).

        Sends a message to the group with the context 'action'
        (shot, miss, hit).
        """
        action_type = event['action_type']
        params = event['params']

        await self.send(text_data=json.dumps({'context': 'action',
                                              'action_type': action_type,
                                              'params': params}))

    async def redis_connection_manager(self, **kwargs):
        """
        Используется для более простого и краткого взаимодействия с redis.
        Позволяет использовать одну/несколько комманд,
        с одним/множеством параметром/ов.

        Used for easier and concise interaction with redis.
        Allows to use one/several commands, with one/many parameter/s.

        Примеры/Examples:

        await self.redis_connection_manager(
            hset=[[key, field, value],
                [key, field, value],
                [key, field, value]],
            expire=[[key, value]]
        )

        await self.redis_connection_manager(keys=['*'])
        """
        try:
            async with self.channel_layer.connection(0) as connection:
                result = []

                for k, v in kwargs.items():
                    val_numb = 0

                    if len(kwargs.items()) > 1:
                        if len(v) > 2:
                            for i in v[val_numb]:
                                res = await connection.__getattribute__(
                                    k
                                )(*v[val_numb])
                                result.append(res)
                                val_numb += 1
                        else:
                            res = await connection.__getattribute__(k)(*v[0])
                            result.append(res)
                    else:
                        res = await connection.__getattribute__(k)(v[0])
                        return res
            return result
        except:
            return 'None'

    async def get_data(self):
        """
        Получаем всю сохранённую информацию о комнате (состояние комнаты).

        We get all the stored information about the room (room state).
        """
        data = {k.decode('utf8'): v.decode('utf8')
                for k, v in
                (await self.redis_connection_manager(
                    hgetall=[self.group]
                )).items()}
        self.data = data

    async def readd(self, member):
        """
        Передобавляем пользователя в channels группу.

        Re-add the user to the channels group.
        """
        await self.channel_layer.group_discard(self.group, member)
        await self.channel_layer.group_add(self.group, self.channel_name)

    async def get_all_groups(self):
        """
        Получаем список всех channels групп.

        Get a list of all channels groups.
        """
        keys = [x.decode("utf8") for x in await self.redis_connection_manager(
            keys=['*']
        )]
        groups = []

        for key in keys:
            if key.startswith('asgi:group:'):
                groups.append(key)
        return groups

    async def get_group_members(self):
        """
        Получаем список всех членов в channels группе.

        Get a list of all members in the channels group.
        """
        members = [x.decode("utf8") for x
                   in await self.redis_connection_manager(
                       zrange=['asgi:group:' + self.group, 0, -1]
        )]
        return members

    async def new_room(self):
        """
        Создаём новую комнату (инициализируем состояние комнаты) и добавляем
        нового члена в группу.

        Create a new room (initialize the state of the room) and add a new
        member to the group.
        """
        try:
            r, last_room_number = self.group[-1].split(':')[2].split('_')
            self.group = r + '_' + str(int(last_room_number) + 1)
            await self.channel_layer.group_add(self.group, self.channel_name)
            await self.redis_connection_manager(hset=[
                [self.group, 'room_member', self.username],
                [self.group, 'room_guest', 'None'],
                [self.group, 'messages', '[]']
            ], expire=[[self.group, 3600]])
        except:
            self.group = 'room_1'
            await self.channel_layer.group_add(self.group,
                                               self.channel_name)
            await self.redis_connection_manager(hset=[
                [self.group, 'room_member', self.username],
                [self.group, 'room_guest', 'None'],
                [self.group, 'messages', '[]']
            ], expire=[[self.group, 3600]])

    async def redirect_message(self, text_data_json):
        """
        Переадресовываем сообщения по группе и сохраняем их в состояние
        комнаты.

        Forward messages by group and save them in state rooms.
        """
        message = text_data_json['message']
        messages = json.loads(self.data['messages'])

        try:
            message = {'id': str(int((messages[-1])['id'])+1),
                       'sender': self.username,
                       'message': message}
        except:
            message = {'id': '1', 'sender': self.username, 'message': message}
        await self.channel_layer.group_send(self.group,
                                            {'type': 'chat_message',
                                             'message': message})
        messages.append(message)
        messages = json.dumps(messages)
        await self.redis_connection_manager(hset=[
            [self.group, 'messages', messages]
        ], expire=[[self.group, 3600]])

    async def ready_handler(self, text_data_json):
        """
        Обработчик готовности пользователей в комнате.

        User readiness handler in the room.
        """
        selected_cells = json.dumps(text_data_json['selected_cells'])
        await self.redis_connection_manager(hset=[
            [self.group, self.username + ':selected_cells', selected_cells]
        ], expire=[[self.group, 3600]])
        room_pool = await self.redis_connection_manager(hlen=[self.group])

        if room_pool == 5:
            await self.redis_connection_manager(hset=[
                [self.group,
                 self.username + ':access_to_shot',
                 'false']], expire=[[self.group, 3600]])
            await self.redis_connection_manager(hset=[
                [self.group,
                 self.enemy + ':access_to_shot',
                 'true']], expire=[[self.group, 3600]])
            await self.redis_connection_manager(hset=[[self.group,
                                                       'game_status',
                                                       'started']],
                                                expire=[[self.group, 3600]])
            await self.channel_layer.group_send(self.group,
                                                {'type': 'notification',
                                                 'message': 'start_game'})

    async def shot_handler(self, text_data_json):
        """
        Обработчик выстрелов, промахов, попаданий. Завершает игру,
        когда все корабли одного из пользователей, в комнате, уничтожены.

        Handler for shots, misses, hits. Ends the game when all the ships of
        one of the users in the room are destroyed.
        """
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
                await self.redis_connection_manager(hset=[
                    [self.group, self.enemy + ':dead_cells', dead_cells]
                ], expire=[[self.group, 3600]])
                await self.redis_connection_manager(hset=[
                    [self.group, self.username + ':hit_cells', dead_cells]
                ], expire=[[self.group, 3600]])
                await self.redis_connection_manager(hset=[
                    [self.group, self.username + ':access_to_shot', 'false']
                ], expire=[[self.group, 3600]])
                await self.redis_connection_manager(hset=[
                    [self.group, self.enemy + ':access_to_shot', 'true']
                ], expire=[[self.group, 3600]])

                await self.channel_layer.group_send(
                    self.group,
                    {'type': 'action',
                     'action_type': 'hit',
                     'params': '{},{}'.format(self.enemy,
                                              text_data_json['cell'])}
                )
            else:
                miss_cells.append(text_data_json['cell'])
                miss_cells = json.dumps(miss_cells)

                await self.redis_connection_manager(hset=[
                    [self.group, self.username + ':miss_cells',
                     miss_cells]
                ], expire=[[self.group, 3600]])
                await self.redis_connection_manager(hset=[
                    [self.group, self.username + ':access_to_shot',
                     'false']
                ], expire=[[self.group, 3600]])
                await self.redis_connection_manager(hset=[
                    [self.group, self.enemy + ':access_to_shot',
                     'true']
                ], expire=[[self.group, 3600]])
                await self.channel_layer.group_send(
                    self.group,
                    {'type': 'action',
                     'action_type': 'miss',
                     'params': '{},{}'.format(self.username,
                                              text_data_json['cell'])}
                )
        else:
            await self.channel_layer.group_send(
                self.group,
                {'type': 'action',
                 'action_type': 'lose',
                 'params': '{}'.format(self.enemy)}
            )
