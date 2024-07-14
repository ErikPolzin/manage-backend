"""Sync with a radiusdesk database."""

import pytz
import time

from mysql.connector import connect
from django.conf import settings
from django.utils.timezone import make_aware, now

from monitoring.models import Mesh, Node, UnknownNode, ClientSession
from metrics.models import (
    FailuresMetric,
    ResourcesMetric,
    DataUsageMetric,
    DataRateMetric,
)
from .utils import bulk_sync


GET_MESHES_QUERY = """
SELECT c.name, c.created
FROM clouds c
"""
GET_NODES_AND_APS_QUERY = """
SELECT m.name, n.name, n.description, n.mac, n.hardware, n.ip, n.last_contact_from_ip
FROM nodes n
JOIN meshes m
ON n.mesh_id = m.id;
SELECT c.name, a.name, a.description, a.mac, a.hardware, null, a.last_contact_from_ip
FROM aps a
JOIN ap_profiles p
ON a.ap_profile_id = p.id
JOIN clouds c
ON p.cloud_id = c.id;
"""
GET_NODE_AND_AP_BYTES_QUERY = """
SELECT n.mac, s.tx_bytes, s.rx_bytes, s.created
FROM node_stations s
JOIN nodes n
ON s.node_id = n.id;
SELECT a.mac, s.tx_bytes, s.rx_bytes, s.created
FROM ap_stations s
JOIN aps a
ON s.ap_id = a.id;
"""
GET_NODE_AND_AP_RATES_QUERY = """
SELECT n.mac, s.rx_bitrate, s.tx_bitrate, s.created
FROM node_stations s
JOIN nodes n
ON s.node_id = n.id;
SELECT a.mac, s.rx_bitrate, s.tx_bitrate, s.created
FROM ap_stations s
JOIN aps a
ON s.ap_id = a.id;
"""
GET_NODE_AND_AP_FAILURES_QUERY = """
SELECT n.mac, s.tx_packets, s.rx_packets, s.tx_failed, s.tx_retries, s.created
FROM node_stations s
JOIN nodes n
ON s.node_id = n.id;
SELECT a.mac, s.tx_packets, s.rx_packets, s.tx_failed, s.tx_retries, s.created
FROM ap_stations s
JOIN aps a
ON s.ap_id = a.id;
"""
GET_NODE_AND_AP_RESOURCES_QUERY = """
SELECT n.mac, l.mem_total, l.mem_free
FROM node_loads l
JOIN nodes n
ON l.node_id = n.id;
SELECT a.mac, l.mem_total, l.mem_free
FROM ap_loads l
JOIN aps a
ON l.ap_id = a.id;
"""
GET_UNKNOWN_NODES_QUERY = """
SELECT u.mac, u.vendor, u.from_ip, u.gateway, u.last_contact, u.created, u.name
FROM unknown_nodes u;
"""
# This is the most perverse way of joining the radacct tabel to the ap table, but there doesn't
# seem to be a more direct way to do it - the calledstationid doesn't match an ap (or an ap_station)
# and I can't link nasidentifiers to APs either!
GET_CONNECTED_CLIENTS_QUERY = """
SELECT r.username, ap.mac, r.acctstarttime, r.acctstoptime, r.acctinputoctets, r.acctoutputoctets, r.callingstationid
FROM radacct r
JOIN data_collectors d
ON d.cp_mac = r.calledstationid
JOIN aps ap
ON ap.lan_ip = d.public_ip;
"""

TZ = pytz.timezone("Africa/Johannesburg")


@bulk_sync(Mesh)
def sync_meshes(cursor):
    """Sync Mesh objects from the radiusdesk database."""
    cursor.execute(GET_MESHES_QUERY)
    for name, created in cursor.fetchall():
        yield {}, {"name": name}


# The nodes that are out of sync mustn't be deleted, they can be potentially added to radiusdesk later
@bulk_sync(Node, delete=False)
def sync_nodes(cursor):
    """Sync Node objects from the radiusdesk database."""
    for result in cursor.execute(GET_NODES_AND_APS_QUERY, multi=True):
        for (
            mesh_name,
            name,
            description,
            mac,
            hardware,
            ip,
            last_contact_from_ip,
        ) in result.fetchall():
            yield {  # Update fields
                "mesh": Mesh.objects.get(name=mesh_name),
                "ip": ip or last_contact_from_ip
            }, {  # Create fields, these will be set initially but won't be synced
                "name": name,
                "description": description,
                "hardware": hardware
            }, {"mac": mac}


@bulk_sync(UnknownNode)
def sync_unknown_nodes(cursor):
    """Sync UnknownNode objects from the radiusdesk database."""
    cursor.execute(GET_UNKNOWN_NODES_QUERY)
    for mac, vendor, from_ip, gateway, last_contact, created, name in cursor.fetchall():
        # If there already exists a node with the same MAC, don't
        # create a new UnknownNode
        if Node.objects.filter(mac=mac).exists():
            continue
        yield {
            "vendor": vendor,
            "from_ip": from_ip,
            "gateway": gateway,
            "last_contact": make_aware(last_contact, TZ),
            "created": make_aware(created, TZ),
            "name": name,
        }, {"mac": mac}


@bulk_sync(DataUsageMetric)
def sync_node_bytes_metrics(cursor):
    """Sync BytesMetric objects from the radiusdesk database."""
    for result in cursor.execute(GET_NODE_AND_AP_BYTES_QUERY, multi=True):
        for mac, tx_bytes, rx_bytes, created in result.fetchall():
            yield {
                "mac": mac,
                "tx_bytes": tx_bytes,
                "rx_bytes": rx_bytes,
            }, {"created": make_aware(created, TZ)}


@bulk_sync(DataRateMetric)
def sync_node_rates_metrics(cursor):
    """Sync DataRateMetric objects from the radiusdesk database."""
    for result in cursor.execute(GET_NODE_AND_AP_RATES_QUERY, multi=True):
        for mac, rx_rate, tx_rate, created in result.fetchall():
            yield {
                "mac": mac,
                "rx_rate": rx_rate,
                "tx_rate": tx_rate,
            }, {"created": make_aware(created, TZ)}


@bulk_sync(FailuresMetric)
def sync_node_failures_metrics(cursor):
    """Sync FailuresMetric objects from the radiusdesk database."""
    for result in cursor.execute(GET_NODE_AND_AP_FAILURES_QUERY, multi=True):
        for (
            node_mac,
            tx_packets,
            rx_packets,
            tx_failed,
            tx_retries,
            created,
        ) in result.fetchall():
            yield {
                "mac": node_mac,
                "tx_packets": tx_packets,
                "rx_packets": rx_packets,
                "tx_dropped": tx_failed,
                "tx_retries": tx_retries,
            }, {"created": make_aware(created, TZ)}


@bulk_sync(ResourcesMetric)
def sync_node_resources_metrics(cursor):
    """Sync NodeLoad objects from the radiusdesk database."""
    for result in cursor.execute(GET_NODE_AND_AP_RESOURCES_QUERY, multi=True):
        for node_mac, mem_total, mem_free in result.fetchall():
            yield {
                "mac": node_mac,
                "memory": mem_free / mem_total * 100,
                "cpu": -1,  # Radiusdesk doesn't track CPU usage??
            }, {"created": now()}


@bulk_sync(ClientSession)
def sync_client_sessions(cursor):
    """Sync ClientSession objects from the radiusdesk database."""
    cursor.execute(GET_CONNECTED_CLIENTS_QUERY)
    for (
        username,
        ap_mac,
        acctstarttime,
        acctstoptime,
        acctinputoctets,
        acctoutputoctets,
        callingstationid,
    ) in cursor.fetchall():
        try:
            uplink = Node.objects.get(mac=ap_mac)
        except Node.DoesNotExist:
            print(f"Skipping uplink {ap_mac}, does not exist")
            continue
        yield {
            "username": username,
            "bytes_recv": acctinputoctets,
            "bytes_sent": acctoutputoctets,
            "end_time": make_aware(acctstoptime, TZ) if acctstoptime else None,
        }, {  # MAC, start time and uplink uniquely identify session
            "mac": callingstationid,
            "start_time": make_aware(acctstarttime, TZ),
            "uplink": uplink,
        }


def run():
    with connect(
        host=settings.RD_DB_HOST,
        user=settings.RD_DB_USER,
        password=settings.RD_DB_PASSWORD,
        database=settings.RD_DB_NAME,
        port=settings.RD_DB_PORT,
    ) as connection:
        with connection.cursor() as cursor:
            start_time = time.time()
            sync_meshes(cursor)
            sync_nodes(cursor)
            sync_unknown_nodes(cursor)
            sync_node_bytes_metrics(cursor)
            sync_node_rates_metrics(cursor)
            sync_node_resources_metrics(cursor)
            sync_node_failures_metrics(cursor)
            sync_client_sessions(cursor)
            elapsed_time = time.time() - start_time
            print(f"Synced with radiusdesk in {elapsed_time:.2f}s")
