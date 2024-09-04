from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from django.db.models import Q

from .models import Node, HealthStatus
from . import models
from . import serializers


@api_view()
def overview(request):
    return Response({
        "n_nodes": Node.objects.filter(mesh__isnull=False).count(),
        "n_positioned_nodes": Node.objects.filter(lat__isnull=False, lon__isnull=False).count(),
        "n_unknown_nodes": Node.objects.filter(mesh__isnull=True).count(),
        "n_ok_nodes": Node.objects.filter(health_status=HealthStatus.OK).count(),
        "n_online_nodes": Node.objects.filter(status=Node.Status.ONLINE).count(),
    })


class NodeViewSet(ModelViewSet):
    """View/Edit/Add/Delete Node items."""

    queryset = models.Node.objects.all()
    serializer_class = serializers.NodeSerializer

    def get_queryset(self):
        """Filter nodes for a given mesh."""
        qs = super().get_queryset()
        mesh_name = self.request.query_params.get("mesh")
        if mesh_name:
            # Want to include all of the un-adopted nodes
            qs = qs.filter(Q(mesh__isnull=True) | Q(mesh__name=mesh_name))
        return qs


class AlertsViewSet(ModelViewSet):
    """View/Edit/Add/Delete Alert items."""

    queryset = models.Alert.objects.all()
    serializer_class = serializers.AlertSerializer


class MeshViewSet(ModelViewSet):
    """View/Edit/Add/Delete Mesh items."""

    queryset = models.Mesh.objects.all()
    serializer_class = serializers.MeshSerializer

    def get_queryset(self):
        """Only list meshes that this user maintains."""
        return super().get_queryset().filter(maintainers=self.request.user)

    @action(detail=True, methods=["put"])
    def update_settings(self, request, pk=None):
        """Put new settings."""
        mesh = self.get_object()
        serializer = serializers.MeshSettingsSerializer(mesh.settings, data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ServiceViewSet(ModelViewSet):
    """View Service items."""

    queryset = models.Service.objects.all()
    serializer_class = serializers.ServiceSerializer
