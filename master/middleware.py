from urllib.parse import parse_qs
from django.db import close_old_connections
from channels.db import database_sync_to_async
from django.contrib.auth.models import User


class AuthMiddleware:
    """Авторизация для websocket соединений"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        values = scope['query_string']
        values = parse_qs(values.decode())
        try:
            if values['username'] and values['user_hash']:
                username = values['username'][0]
                received_user_hash = values['user_hash'][0]
                user = await database_sync_to_async(User.objects.get)(username=username)
                user_hash = await database_sync_to_async(user._legacy_get_session_auth_hash)()

                if str(user_hash) == received_user_hash:
                    close_old_connections()
                    return await self.app(scope, receive, send)
        except:
            return None
