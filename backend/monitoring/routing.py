from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/updates/(?P<mesh_name>\w+)/$", consumers.UpdatesConsumer.as_asgi()),
]
