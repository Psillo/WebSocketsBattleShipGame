from django.urls import path
from django.contrib.auth import views

from .views import main, register
from .consumers import InterfaceConsumer


app_name = 'master'

urlpatterns = [
    path('', main, name='main'),
    path('login/', views.LoginView.as_view(template_name='login.html'),
         name='login'),
    path('register/', register, name='register')
]

websocket_urlpatterns = [
    path('ws/game/', InterfaceConsumer.as_asgi())
]
