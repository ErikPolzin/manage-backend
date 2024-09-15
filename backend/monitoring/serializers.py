from rest_framework.serializers import ModelSerializer, SerializerMethodField, SlugRelatedField
from django.contrib.auth.models import User
from drf_dynamic_fields import DynamicFieldsMixin

from radius.models import Radacct
from radius.serializers import RadacctSerializer
from . import models


class MeshSettingsSerializer(ModelSerializer):
    """Serializes MeshSettings objects from django model to JSON."""

    class Meta:
        """MeshSettingsSerializer metadata."""

        model = models.MeshSettings
        fields = "__all__"


class WlanConfSerializer(ModelSerializer):
    """Serializes WlanConf objects from django model to JSON."""

    class Meta:
        """WlanConfSerializer metadata."""

        model = models.WlanConf
        fields = "__all__"


class MeshSerializer(ModelSerializer):
    """Serializes Mesh objects from django model to JSON."""

    settings = MeshSettingsSerializer(required=False)
    wlanconfs = WlanConfSerializer(many=True, required=False)
    maintainers = SlugRelatedField(many=True, slug_field="username", queryset=User.objects.all())

    class Meta:
        """MeshSerializer metadata."""

        model = models.Mesh
        fields = "__all__"


class AlertSerializer(ModelSerializer):
    """Serializes Alert objects from django model to JSON."""

    node = SerializerMethodField()

    class Meta:
        """ServiceSerializer metadata."""

        model = models.Alert
        fields = "__all__"

    def get_node(self, alert: models.Alert) -> str:
        # The default PrimaryKeyRelatedField doesn't work, because Node's primary
        # key is a MacAddressField, and rest_framework has trouble serializing
        # that to JSON. As a workaround, I manually stringify it here.
        return str(alert.node.mac)


class NodeSerializer(DynamicFieldsMixin, ModelSerializer):
    """Serializes Node objects from django model to JSON."""

    class Meta:
        """Node metadata."""

        model = models.Node
        fields = "__all__"

    neighbours = SerializerMethodField()
    checks = SerializerMethodField()
    latest_alerts = SerializerMethodField()
    num_unresolved_alerts = SerializerMethodField()
    upload_speed = SerializerMethodField()
    download_speed = SerializerMethodField()
    client_sessions = SerializerMethodField()

    def get_checks(self, node: models.Node) -> list[dict]:
        """Run checks defined in settings.DEVICE_CHECKS"""
        return node.check_results.serialize()

    def get_latest_alerts(self, node: models.Node) -> list[dict]:
        """Get the latest alerts for this node."""
        # TODO: Hard-coded for now
        return AlertSerializer(node.alerts.order_by("created")[:10], many=True).data

    def get_num_unresolved_alerts(self, node: models.Node) -> int:
        """Get the number of unresolved alerts for this node."""
        return node.alerts.exclude(status=models.Alert.Status.RESOLVED).count()

    def get_upload_speed(self, node: models.Node) -> float | None:
        """Get node's upload speed."""
        return node.get_upload_speed()

    def get_download_speed(self, node: models.Node) -> float | None:
        """Get node's download speed."""
        return node.get_download_speed()

    def get_neighbours(self, node: models.Node) -> list[str]:
        """Get neighbour's MAC addresses."""
        # This EUI field serialization thing is getting super annoying...
        # This should just be a PrimaryKeyRelatedField,
        return [str(n.mac) for n in node.neighbours.all()]

    def get_client_sessions(self, node: models.Node) -> list[dict]:
        """Serialize radacct objects related to this node's NAS."""
        radaccts = Radacct.objects.filter(nasidentifier=node.nas_name)
        serializer = RadacctSerializer(radaccts, many=True)
        return serializer.data


class ServiceSerializer(ModelSerializer):
    """Serializes Service objects from django model to JSON."""

    class Meta:
        """ServiceSerializer metadata."""

        model = models.Service
        fields = "__all__"
