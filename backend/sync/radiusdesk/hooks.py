from copy import deepcopy
import logging
import json

from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.core.serializers.json import DjangoJSONEncoder

from monitoring.models import Node
from sync.tasks import sync_device, sync_all_devices
from ..utils import get_src_ip, mem_kb_to_bytes

reports_logger = logging.getLogger("reports")
logger = logging.getLogger(__file__)


def parse_report(request: HttpRequest, data: dict) -> Node.Report:
    """Parse a standardised report from RADIUSdesk inform data."""
    mem = None
    if data["report_type"] == "full":
        mem_data = data["system_info"]["sys"]["memory"]
        memf = mem_kb_to_bytes(mem_data["free"])
        memt = mem_kb_to_bytes(mem_data["total"])
        if memf != -1 and memt != -1 and memt != 0:
            mem = 100 - round(memf / memt * 100)
    return Node.Report(
        ip=get_src_ip(request),
        is_ap=data["mode"] == "ap",
        mem=mem
    )


def hook_rd_report_request(request: HttpRequest) -> None:
    """Hook a request coming from a radiusdesk node to the server."""
    report_data = json.loads(request.body)
    report = parse_report(request, report_data)
    # This little deepcopy bug wasted FOUR AND A HALF HOURS of my life :)
    # DON'T MODIFY DATA THAT'S GOING TO BE FORWARDED!!!!!
    report_copy = deepcopy(report_data)
    mac = report_copy.pop("mac")
    node = Node.objects.filter(mac=mac).first()
    if node:
        node.on_receive_report(report)
    else:
        Node.on_receive_unregistered_report(mac, report)
    sync_device.delay(mac)
    reports_logger.info("%s REQUEST %s", mac, json.dumps(report_copy))
    return mac  # We need the mac when we process the response


def hook_rd_report_response(response: HttpResponse | StreamingHttpResponse, mac: str) -> None:
    """Hook a response from the radiusdesk server back to the node."""
    if isinstance(response, StreamingHttpResponse):
        response_data = json.loads(response.getvalue())
    else:
        response_data = json.loads(response.body)
    if response_data.get("success") and mac:
        node = Node.objects.filter(mac=mac).first()
        if node:
            # Allow our reboot_flag to also reboot nodes
            reboot_flag = response_data["reboot_flag"] or node.reboot_flag
            if reboot_flag:
                # We're about to send the reboot flag back to the node, we can reset it now
                node.reboot_flag = False
                node.status = Node.Status.REBOOTING
                node.save(update_fields=["reboot_flag", "status"])
                sync_device.delay(str(node.mac))
            response_data["reboot_flag"] = reboot_flag
    content = json.dumps(response_data, cls=DjangoJSONEncoder)
    reports_logger.info("%s RESPONSE %s", mac, content)
    # Patch the response content
    if isinstance(response, StreamingHttpResponse):
        response.streaming_content = [content]
    else:
        response.content = content


def hook_rd(
    request: HttpRequest,
    path: str,
    response: HttpResponse | None = None,
    hook_data=None,
) -> None:
    """Hook calls by nodes to the radiusdesk API."""
    if path == "cake4/rd_cake/nodes/get-config-for-node.json":
        pass
    elif path == "cake4/rd_cake/node-reports/submit_report.json":
        if response:
            return hook_rd_report_response(response, hook_data)
        else:
            return hook_rd_report_request(request)
    elif path == "cake4/rd_cake/node-actions/get_actions_for.json":
        pass
