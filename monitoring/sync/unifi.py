"""Sync with a radiusdesk database."""

import time
from datetime import timedelta

from pymongo import MongoClient
from django.conf import settings

from monitoring.models import Mesh, Node, ClientSession
from metrics.models import (
    DataUsageMetric,
    FailuresMetric,
    ResourcesMetric,
    DataRateMetric,
)
from .utils import bulk_sync, aware_timestamp


@bulk_sync(Mesh)
def sync_meshes(client):
    """Sync Mesh objects from the unifi database."""
    for site in client.ace.site.find():
        yield {}, {"name": site["name"]}


@bulk_sync(Node, delete=False)
def sync_nodes(client):
    """Sync Node objects from the unifi database."""
    for device in client.ace.device.find():
        adoption_details = client.ace.event.find_one(
            {"key": "EVT_AP_Adopted", "ap": device["mac"]}
        )
        name = adoption_details["ap_name"] if adoption_details else device["model"]
        adopt_time = aware_timestamp(device["adopted_at"])
        yield {  # Update fields
            "mesh": Mesh.objects.get(name=device["last_connection_network_name"].lower()),
            "ip": device["ip"],
            "created": adopt_time
        }, {  # Create fields, these won't overwrite if this model has already been synced
            "name": name,
            "description": "",
            "hardware": device["model"]
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


@bulk_sync(ClientSession)
def sync_client_sessions(client: MongoClient):
    """Sync ClientSession objects from the unifi database."""
    # This on'es a bit tricky, unifi doesn't store client sessions, but stores
    # statistics in 5 minute intervals. The idea is to loop through each user's
    # stats in the order they were created and try stitch together each session.
    cursor = client.ace_stat.stat_5minutes.find({"o": "user"})
    for user_mac in cursor.distinct("user"):
        user = client.ace.user.find_one({"mac": user_mac})
        # Could not find this user, skip
        if not user:
            continue
        kwargs, data = {}, {}
        user_data = list(
            client.ace_stat.stat_5minutes.find({"user": user_mac}, sort={"time": 1})
        )
        for i, d1 in enumerate(user_data):
            # We need the next stats entry to see whether there was a significant time delay
            # between the two, i.e. the session was ended
            d2 = user_data[i + 1] if i < len(user_data) - 1 else None
            # start_time, uplink and mac uniquely identify a session
            kwargs.setdefault("start_time", aware_timestamp(d1["time"]))
            kwargs.setdefault("uplink", Node.objects.get(mac=d1["x-set-ap_macs"][0]))
            kwargs["mac"] = user_mac
            # bytes_recv, bytes_sent, end_time and username are session data
            data["bytes_recv"] = data.get("bytes_recv", 0) + d1["rx_bytes"]
            data["bytes_sent"] = data.get("bytes_sent", 0) + d1["tx_bytes"]
            data["end_time"] = aware_timestamp(d1["time"])
            data["username"] = user["hostname"]
            td = timedelta(seconds=(d2["time"] - d1["time"]) / 1000) if d2 else None
            # If this is the last entry, or the session is about to end
            if td is None or td > timedelta(minutes=6):
                yield data, kwargs
                # Reset data and kwargs so the next session will write new defaults
                kwargs, data = {}, {}


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
    sync_client_sessions(_client)
    elapsed_time = time.time() - start_time
    print(f"Synced with unifi in {elapsed_time:.2f}s")
