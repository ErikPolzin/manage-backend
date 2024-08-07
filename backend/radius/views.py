from rest_framework.viewsets import ModelViewSet

from . import serializers
from . import models


class RadacctViewSet(ModelViewSet):
    """View Radacct items."""

    queryset = models.Radacct.objects.all().order_by("username")
    serializer_class = serializers.RadacctSerializer
