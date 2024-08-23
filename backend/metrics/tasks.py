from datetime import datetime, timedelta
import time
from typing import Type
from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone

from monitoring.models import Node
from sync.tasks import sync_all_devices
from .models import UptimeMetric, RTTMetric, Metric
from .ping import ping

logger = get_task_logger(__name__)


@shared_task
def run_pings():
    for device in Node.objects.filter(ip__isnull=False):
        try:
            ping_data = ping(device.ip)
            reachable = ping_data["reachable"]
        except ValueError:
            reachable = False
        # If the ping failed the device is offline
        if not reachable:
            # If the ping fails while the device is rebooting there
            # is no need to update its status to 'offline'
            if device.status != Node.Status.REBOOTING:
                device.status = Node.Status.OFFLINE
        else:
            # Otherwise log the time of the last successful ping. Not that a
            # successful ping is not a guarantee that the node is online, it
            # has to send the server a report first.
            device.last_ping = timezone.now()
        # Update the device reachable status
        device.reachable = reachable
        rtt_data = ping_data.pop("rtt", None)
        UptimeMetric.objects.create(mac=device.mac, **ping_data)
        if rtt_data:
            RTTMetric.objects.create(mac=device.mac, **rtt_data)
        # Update the device health status
        device.update_health_status(save=False)
        device.save(update_fields=["reachable", "last_ping", "status", "health_status"])
        # Optionally generate alerts for this device based on the new status
        device.generate_alert()
        logger.info(f"PING {device.ip} (reachable={reachable})")
    # Sync all devices so that updates are passed to monitoring instances by websocket.
    # Note not calling delay() here, I'm happy to have this run on the same thread
    sync_all_devices()


def aggregate_metrics(metric_type: Type[Metric], to_gran: Metric.Granularity) -> None:
    """Aggregate metrics for a given metric type."""
    from_gran = to_gran.prev_granularity()
    from_gran_name = from_gran.name if from_gran else "None"
    metrics = metric_type.objects.filter(granularity=from_gran)
    metrics_count = metrics.count()
    # HISTOGRAM
    unique_mac_addresses = set(metrics.values_list("mac", flat=True))
    for mac in unique_mac_addresses:
        metrics_for_mac = metrics.filter(mac=mac).order_by("created")
        # Metrics are ordered by their created date in ascending order
        first_metric, last_metric = metrics_for_mac.first(), metrics_for_mac.last()
        if not (first_metric and last_metric):
            continue
        min_time = int(to_gran.round_down(first_metric.created).timestamp())
        # This is round up, but I don't feel like writing a separate round_up function
        max_time = int(to_gran.round_down(last_metric.created).timestamp())+to_gran.value
        # Bucket interval is the dest granularity's total_seconds
        for t0_int in range(min_time, max_time, to_gran.value):
            t0 = datetime.fromtimestamp(t0_int, tz=last_metric.created.tzinfo)
            t1 = t0 + timedelta(seconds=to_gran.value)
            ta = t0 + (t1 - t0) / 2
            # These are the old metrics that are going to be aggregated
            bucket_metrics = metrics_for_mac.filter(created__gte=t0, created__lt=t1)
            if bucket_metrics.exists():
                # Group by mac address
                bucket_metrics.create_aggregated(mac=mac, created=ta, granularity=to_gran)
                bucket_metrics.delete()
    logger.info(
        "Aggregated %d metrics for %s from %s to %s",
        metrics_count,
        metric_type.__name__,
        from_gran_name,
        to_gran.name,
    )


def aggregate_all_metrics(to_gran: Metric.Granularity) -> None:
    """Aggregate metrics for each metric type."""
    start_time = time.time()
    for metric_type in Metric.__subclasses__():
        aggregate_metrics(metric_type, to_gran)
    elapsed_time = timedelta(seconds=time.time() - start_time)
    logger.info("Aggregated %s metrics in %s", to_gran.name, elapsed_time)


@shared_task
def aggregate_all_hourly_metrics():
    """Aggregate to hourly metrics once an hour."""
    aggregate_all_metrics(Metric.Granularity.HOURLY)


@shared_task
def aggregate_all_daily_metrics():
    """Aggregate to daily metrics once a day."""
    aggregate_all_metrics(Metric.Granularity.DAILY)


@shared_task
def aggregate_all_monthly_metrics():
    """Aggregate to monthly metrics once a month."""
    aggregate_all_metrics(Metric.Granularity.MONTHLY)
