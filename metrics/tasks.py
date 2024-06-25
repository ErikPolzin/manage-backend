from celery import shared_task
from celery.utils.log import get_task_logger

from .models import Node, UptimeMetric, RTTMetric
from .ping import ping

logger = get_task_logger(__name__)


@shared_task
def run_pings():
    for device in Node.objects.filter(last_contact_from_ip__isnull=False):
        ping_data = ping(device.ip or device.last_contact_from_ip)
        rtt_data = ping_data.pop("rtt", None)
        UptimeMetric.objects.create(node=device, **ping_data)
        if rtt_data:
            RTTMetric.objects.create(node=device, **rtt_data)
        logger.info(f"PING {device.last_contact_from_ip}")