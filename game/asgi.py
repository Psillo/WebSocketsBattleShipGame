import os


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'game.settings')

from django.core.asgi import get_asgi_application
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from master.middleware import AuthMiddleware


from master.urls import websocket_urlpatterns


application = ProtocolTypeRouter({
    "http": django_asgi_app,
    'websocket':  AuthMiddleware(URLRouter(websocket_urlpatterns))
})
