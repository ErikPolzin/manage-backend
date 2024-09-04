import logging
import json
import zlib
import struct

from django.utils import timezone
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from monitoring.models import Node
from sync.tasks import sync_device, sync_all_devices
from ..utils import get_src_ip

reports_logger = logging.getLogger("reports")
logger = logging.getLogger(__file__)
last_contact = None
# TODO: AES-GCM key is hard-coded for now
aesgcm = AESGCM(bytes.fromhex("1d5f4f08478db1ab4b0caa05e3e65d11"))


def parse_inform(data: bytes) -> dict:
    """Parse data from the inform request."""
    headers, payload = data[:40], data[40:]
    magic, version, hardware, flags, iv, payload_version, payload_len = struct.unpack("!II6sh16sII", headers)
    assert magic == 1414414933 and payload_version == 1
    decrypted = aesgcm.decrypt(iv, payload, headers)
    # 0x01 = Encrypted
    # 0x02 = ZLibCompressed
    # 0x04 = SnappyCompressed
    # 0x08 = EncryptedGCM
    if flags == 11:
        decompressed = zlib.decompress(decrypted)
    elif flags == 9:
        decompressed = decrypted
    else:
        # TODO: support Snappy compressed flag
        raise ValueError(f"Unsupported inform flags '{flags}', must be 11 or 9")
    return json.loads(decompressed)


def parse_report(request: HttpRequest, data: dict) -> Node.Report:
    """Parse a standardised report from unifi inform data."""
    try:
        memu = data["sys_stats"]["mem_used"]
        memt = data["sys_stats"]["mem_total"]
    except KeyError as e:
        print(data)
        raise e
    return Node.Report(
        ip=get_src_ip(request),
        is_ap=True,  # UniFi nodes are always APs
        mem=round(memu/memt*100)
    )


def hook_unifi_report_request(request: HttpRequest) -> None:
    """Hook calls by nodes to the unifi API."""
    data = parse_inform(request.body)
    report = parse_report(request, data)
    mac = data["mac"]
    node = Node.objects.filter(mac=mac).first()
    if node:
        # Want to throttle this a little, by default unifi sends reports
        # every five seconds.
        if node.last_contact:
            dt = (timezone.now() - node.last_contact).total_seconds()
            if dt < 60:
                return
        # Received a report for an existing node
        node.on_receive_report(report)
    else:
        # Could not find a node with this MAC, create a new one
        Node.on_receive_unregistered_report(mac, report)
    sync_device.delay(str(node.mac))
    reports_logger.info("%s REQUEST %s", mac, json.dumps(data))
    return mac


def hook_unifi_report_response(response: HttpResponse | StreamingHttpResponse, mac: str) -> None:
    """Hook a response from the radiusdesk server back to the node."""
    if isinstance(response, StreamingHttpResponse):
        response_data = parse_inform(response.getvalue())
    else:
        response_data = parse_inform(response.content)
    reports_logger.info("%s RESPONSE %s", mac, json.dumps(response_data))


def hook_unifi(
    request: HttpRequest,
    path: str,
    response: HttpResponse | None = None,
    hook_data=None,
) -> None:
    """Hook calls by nodes to the radiusdesk API."""
    if path == "inform":
        if response:
            return hook_unifi_report_response(response, hook_data)
        else:
            return hook_unifi_report_request(request)
