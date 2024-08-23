from datetime import datetime
from django.db import models
from django.db.models import Avg, Sum, Min
from django.utils import timezone
from macaddress.fields import MACAddressField


class MetricsQuerySet(models.QuerySet):
    """Custom queryset for metrics models.

    Capable of creating new metrics from many aggregated ones.
    """

    def aggregate_fields(self):
        """Aggregate fields values based on SUM_FIELDS, AVG_FIELDS & MIN_FIELDS."""
        sum_kwargs = {fn: Sum(fn) for fn in self.model.SUM_FIELDS}
        avg_kwargs = {fn: Avg(fn) for fn in self.model.AVG_FIELDS}
        min_kwargs = {fn: Min(fn) for fn in self.model.MIN_FIELDS}
        return self.aggregate(**sum_kwargs, **avg_kwargs, **min_kwargs)

    def create_aggregated(self, **fields):
        """Create a metric aggregated from this manager's metrics.

        :param fields: Extra field values. Typically needs to contain at least
            the 'mac' and 'created' fields, since these won't be aggregated.
        """
        return self.create(**fields, **self.aggregate_fields())

    def get_sum(self, field_name: str) -> int:
        """Calculate the sum of values for a particular field."""
        return self.aggregate(Sum(field_name))[f"{field_name}__sum"]

    def get_avg(self, field_name: str) -> float:
        """Calculate the average of values for a particular field."""
        return self.aggregate(Avg(field_name))[f"{field_name}__sum"]

    def get_min(self, field_name: str) -> int:
        """Calculate the minimum of values for a particular field."""
        return self.aggregate(Min(field_name))[f"{field_name}__sum"]


class MetricsManager(models.Manager):
    """Custom manager for metrics."""

    def get_queryset(self) -> MetricsQuerySet:
        """Use the custom MetricsQuerySet."""
        return MetricsQuerySet(self.model, using=self._db)


class Metric(models.Model):
    """Base class for Metric objects."""

    class Granularity(models.IntegerChoices):
        """Time granularity used when aggregating metrics."""

        HOURLY = 60 * 60  # 12 five-min metrics in an hour
        DAILY = 60 * 60 * 24  # 24 hourly metrics in a day
        MONTHLY = 60 * 60 * 24 * 31  # 31 dailty metrics in a month

        def prev_granularity(self) -> "Metric.Granularity | None":
            """Get the previous granularity in the order."""
            prev_index = Metric.GRANULARITY_ORDER.index(self) - 1
            if prev_index == -1:
                return None
            return Metric.GRANULARITY_ORDER[prev_index]

        def round_down(self, value: datetime) -> datetime:
            """Round down to the rearest multiple of this granularity.

            E.g::

              >>> Metric.Granularity.DAILY.round_down("2024-08-22 16:16:00+00:00")
              2024-08-22 16:00:00+00:00
            """
            if self.value == Metric.Granularity.HOURLY:
                return value.replace(minute=0, second=0)
            if self.value == Metric.Granularity.DAILY:
                return value.replace(hour=0, minute=0, second=0)
            if self.value == Metric.Granularity.MONTHLY:
                return value.replace(day=1, hour=0, minute=0, second=0)
            return value

    class Meta:
        """Metric metadata."""

        ordering = ["created"]

    GRANULARITY_ORDER = [
        Granularity.HOURLY,
        Granularity.DAILY,
        Granularity.MONTHLY,
    ]
    # Defined in sub-classes, needed for aggregation
    SUM_FIELDS: set[str] = set()
    AVG_FIELDS: set[str] = set()
    MIN_FIELDS: set[str] = set()

    # Custom manager
    objects = MetricsManager()

    created = models.DateTimeField()
    mac = MACAddressField()
    # granularity = None means that no aggregation has been applied
    granularity = models.IntegerField(choices=Granularity, null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.created is None:
            self.created = timezone.now()
        super().save(*args, **kwargs)


class ResourcesMetric(Metric):
    """Metric for system resources (memor, cpu usage)."""

    AVG_FIELDS = {"memory", "cpu"}

    memory = models.FloatField()
    cpu = models.FloatField(blank=True, null=True)

    def __str__(self):
        return f"Metric: Resources [{self.created}]"


class UptimeMetric(Metric):
    """Metric for uptime, gathered during periodic pings."""

    AVG_FIELDS = {"loss"}
    MIN_FIELDS = {"reachable"}

    reachable = models.BooleanField()
    loss = models.IntegerField()

    def __str__(self):
        return f"Metric: Uptime [{self.created}]"


class RTTMetric(Metric):
    """Metric for round trip time, gathered during periodic pings."""

    AVG_FIELDS = {"rtt_min", "rtt_avg", "rtt_max"}

    rtt_min = models.FloatField(null=True, blank=True)
    rtt_avg = models.FloatField(null=True, blank=True)
    rtt_max = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"Metric: RTT [{self.created}]"


class DataUsageMetric(Metric):
    """Metric for a node's data usage."""

    SUM_FIELDS = {"tx_bytes", "rx_bytes"}

    tx_bytes = models.BigIntegerField()
    rx_bytes = models.BigIntegerField()

    def __str__(self):
        return f"Metric: Data Usage [{self.created}]"


class DataRateMetric(Metric):
    """Metric for a node's transfer/receive speed."""

    AVG_FIELDS = {"tx_rate", "rx_rate"}

    tx_rate = models.IntegerField(null=True, blank=True)
    rx_rate = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"Metric: Data Rate [{self.created}]"


class FailuresMetric(Metric):
    """Metric for wifi failures."""

    AVG_FIELDS = {
        "tx_packets",
        "rx_packets",
        "tx_dropped",
        "rx_dropped",
        "tx_retries",
        "tx_errors",
        "rx_errors",
    }

    tx_packets = models.BigIntegerField()
    rx_packets = models.BigIntegerField()
    tx_dropped = models.IntegerField(null=True, blank=True)
    rx_dropped = models.IntegerField(null=True, blank=True)
    tx_retries = models.IntegerField(null=True, blank=True)
    tx_errors = models.IntegerField(null=True, blank=True)
    rx_errors = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"Metric: Failures [{self.created}]"
