from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.db import close_old_connections
from django.contrib.auth.models import User


class AuthMiddleware:
    """
    Authentication for websocket connections

    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        values = scope['query_string']
        values = parse_qs(values.decode())

        try:
            if values['username'] and values['user_hash']:
                username = values['username'][0]
                received_user_hash = values['user_hash'][0]
                user = await database_sync_to_async(
                    User.objects.get
                )(username=username)
                user_hash = await database_sync_to_async(
                    user._legacy_get_session_auth_hash
                )()
                await database_sync_to_async(close_old_connections)()

                if user_hash == received_user_hash:
                    return await self.app(scope, receive, send)
        except:
            return None
