"""Sync with a radiusdesk database."""

import time

from pymongo import MongoClient
from django.conf import settings

from monitoring.models import Mesh, Node
from metrics.models import (
    DataUsageMetric,
    FailuresMetric,
    ResourcesMetric,
    DataRateMetric,
)
from ..utils import bulk_sync, aware_timestamp


@bulk_sync(Mesh)
def sync_meshes(client):
    """Sync Mesh objects from the unifi database."""
    for site in client.ace.site.find():
        yield {}, {"name": site["name"]}


@bulk_sync(Node, delete=False)
def sync_nodes(client):
    """Sync Node objects from the unifi database."""
    for device in client.ace.device.find():
        # The name doesn't seem to be stored directly, looks like it's
        # assigned during an adoption event
        adoption_details = client.ace.event.find_one(
            {"key": "EVT_AP_Adopted", "ap": device["mac"]}
        )
        name = adoption_details["ap_name"] if adoption_details else device["model"]
        adopt_time = aware_timestamp(device["adopted_at"])
        yield {  # Update fields
            "ip": device["ip"],
            "adopted_at": adopt_time,
        }, {  # Create fields, these won't overwrite if this model has already been synced
            "name": name,
            "is_ap": True,  # Seems like all UniFi nodes are APs
            "mesh": Mesh.objects.filter(name=device["last_connection_network_name"].lower()).first(),
            "description": "",
            "hardware": device["model"],
        }, {  # Lookup fields
            "mac": device["mac"]
        }


@bulk_sync(DataUsageMetric)
def sync_node_data_usage_metrics(client):
    """Sync DataUsageMetric objects from the unifi database."""
    latest_metric = DataUsageMetric.objects.last()
    last_created = latest_metric.created if latest_metric else None
    aps = client.ace_stat.stat_hourly.find({"o": "ap"})
    for ap in aps:
        created_aware = aware_timestamp(ap["time"])
        if last_created and created_aware < last_created:
            continue
        yield {
            "mac": ap["ap"],
            "tx_bytes": ap.get("tx_bytes"),
            "rx_bytes": ap.get("rx_bytes"),
        }, {"created": created_aware}


@bulk_sync(DataRateMetric)
def sync_node_data_rate_metrics(client):
    """Sync DataRateMetric objects from the unifi database."""
    latest_metric = DataRateMetric.objects.last()
    last_created = latest_metric.created if latest_metric else None
    aps = client.ace_stat.stat_5minutes.find({"o": "ap"})
    for ap in aps:
        created_aware = aware_timestamp(ap["time"])
        if last_created and created_aware < last_created:
            continue
        bytes_per_5mins_to_bits_per_second = 8 / 5 / 60
        yield {
            "mac": ap["ap"],
            "tx_rate": ap.get("client-tx_bytes") * bytes_per_5mins_to_bits_per_second,
            "rx_rate": ap.get("client-rx_bytes") * bytes_per_5mins_to_bits_per_second,
        }, {"created": created_aware}


@bulk_sync(FailuresMetric)
def sync_node_failures_metrics(client):
    """Sync FailuresMetric objects from the unifi database."""
    latest_metric = FailuresMetric.objects.last()
    last_created = latest_metric.created if latest_metric else None
    aps = client.ace_stat.stat_hourly.find({"o": "ap"})
    for ap in aps:
        created_aware = aware_timestamp(ap["time"])
        if last_created and created_aware < last_created:
            continue
        yield {
            "mac": ap["ap"],
            "tx_packets": ap.get("tx_packets"),
            "rx_packets": ap.get("rx_packets"),
            "tx_dropped": ap.get("tx_dropped"),
            "rx_dropped": ap.get("rx_dropped"),
            "tx_errors": ap.get("tx_failed"),
            "rx_errors": ap.get("rx_failed"),
            "tx_retries": ap.get("tx_retries"),
        }, {"created": created_aware}


@bulk_sync(ResourcesMetric)
def sync_node_resources_metrics(client):
    """Sync NodeLoad objects from the unifi database."""
    latest_metric = ResourcesMetric.objects.last()
    last_created = latest_metric.created if latest_metric else None
    aps = client.ace_stat.stat_hourly.find({"o": "ap"})
    for ap in aps:
        created_aware = aware_timestamp(ap["time"])
        if last_created and created_aware < last_created:
            continue
        yield {
            "mac": ap["ap"],
            "memory": ap.get("mem"),
            "cpu": ap.get("cpu"),
        }, {"created": created_aware}


def run():
    _client = MongoClient(
        host=settings.UNIFI_DB_HOST,
        port=int(settings.UNIFI_DB_PORT),
        username=settings.UNIFI_DB_USER,
        password=settings.UNIFI_DB_PASSWORD,
    )
    start_time = time.time()
    sync_meshes(_client)
    sync_nodes(_client)
    sync_node_data_usage_metrics(_client)
    sync_node_data_rate_metrics(_client)
    sync_node_failures_metrics(_client)
    sync_node_resources_metrics(_client)
    elapsed_time = time.time() - start_time
    print(f"Synced with unifi in {elapsed_time:.2f}s")
