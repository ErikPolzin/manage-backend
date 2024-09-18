from datetime import datetime
from rest_framework.viewsets import ModelViewSet

from monitoring.models import Mesh
from . import models
from . import serializers


class FilterMixin:
    """Allow filtering a view's query set."""

    MAC_FIELD = "mac"
    MIN_TIME_FIELD = "min_time"
    GRANULARITY_FIELD = "granularity"
    MESH_FIELD = "mesh"

    def filter_queryset(self, qs):
        """Filter against a 'min_time' parameter in the request query."""
        qs = super().filter_queryset(qs)
        mac = self.request.query_params.get(self.MAC_FIELD)
        min_time = self.request.query_params.get(self.MIN_TIME_FIELD)
        granularity = self.request.query_params.get(self.GRANULARITY_FIELD)
        mesh_name = self.request.query_params.get(self.MESH_FIELD)
        # No need to filter nodes in mesh if you're already specifying a node id
        if mesh_name is not None and mac is None:
            # Remember meshes are stored in the default database, not the metrics db
            mesh = Mesh.objects.using("default").filter(name=mesh_name).first()
            if mesh:
                # Note the explicit list conversion, otherwise the filtering is
                # done in the db request which casues issues across the two dbs
                mac_addresses = list(mesh.nodes.values_list("mac", flat=True))
                qs = qs.filter(mac__in=mac_addresses)
        if mac is not None:
            qs = qs.filter(mac=mac)
        if min_time is not None:
            try:
                min_time_int = int(min_time)
                qs = qs.filter(created__gt=datetime.fromtimestamp(min_time_int))
            except ValueError:
                pass
        if granularity is not None:
            try:
                g = models.Metric.Granularity[granularity]
                qs = qs.filter(granularity=g)
            except KeyError:
                pass
        return qs


class UptimeViewSet(FilterMixin, ModelViewSet):
    """View/Edit/Add/Delete UptimeMetric items."""

    queryset = models.UptimeMetric.objects.all()
    serializer_class = serializers.UptimeMetricSerializer


class FailuresViewSet(FilterMixin, ModelViewSet):
    """View/Edit/Add/Delete FailuresMetric items."""

    queryset = models.FailuresMetric.objects.all()
    serializer_class = serializers.FailuresMetricSerializer


class RTTViewSet(FilterMixin, ModelViewSet):
    """View/Edit/Add/Delete RTTMetric items."""

    queryset = models.RTTMetric.objects.all()
    serializer_class = serializers.RTTMetricSerializer


class ResourcesViewSet(FilterMixin, ModelViewSet):
    """View/Edit/Add/Delete ResourcesMetric items."""

    queryset = models.ResourcesMetric.objects.all()
    serializer_class = serializers.ResourcesMetricSerializer


class DataUsageViewSet(FilterMixin, ModelViewSet):
    """View/Edit/Add/Delete DataUsageMetric items."""

    queryset = models.DataUsageMetric.objects.all()
    serializer_class = serializers.DataUsageMetricSerializer


class DataRateViewSet(FilterMixin, ModelViewSet):
    """View/Edit/Add/Delete DataRateMetric items."""

    queryset = models.DataRateMetric.objects.all()
    serializer_class = serializers.DataRateMetricSerializer
