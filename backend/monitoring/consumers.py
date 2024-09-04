import json
from channels.generic.websocket import AsyncWebsocketConsumer


class UpdatesConsumer(AsyncWebsocketConsumer):
    """Consumer to distribute data changes to monitoring clients."""

    async def connect(self):
        """Connect a websocket, add to the same updates group."""
        self.mesh_name = self.scope["url_route"]["kwargs"]["mesh_name"]
        await self.channel_layer.group_add(self.mesh_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        """Leave the updates group on websocket disconnect."""
        await self.channel_layer.group_discard(self.mesh_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        """Receive data from websocket."""

    # Receive message from updates group
    async def update_devices(self, event):
        """Receive an update.devices message from the default group."""
        # Just mirror the data across the whole group
        await self.send(
            text_data=json.dumps({"type": "sync:devices", "devices": event["data"]})
        )

    async def update_device(self, event):
        """Receive an update.device message from the default group."""
        # Just mirror the data across the whole group
        await self.send(
            text_data=json.dumps({"type": "sync:device", "device": event["data"]})
        )
