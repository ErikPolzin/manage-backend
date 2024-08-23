from django.utils.functional import cached_property
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from macaddress.fields import MACAddressField

from metrics.models import ResourcesMetric, RTTMetric, DataRateMetric
from .checks import CheckResults


class WlanConf(models.Model):
    """Fireless configuration."""

    class Security(models.TextChoices):
        """Security mechanism for wireless access."""

        OPEN = "open", "Open"
        WPA_PSK = "wpapsk", "WPA-PSK"

    name = models.CharField(max_length=32)
    passphrase = models.CharField(max_length=100, null=True, blank=True)
    security = models.CharField(max_length=6, choices=Security.choices)
    is_guest = models.BooleanField(default=False)


class Mesh(models.Model):
    """Mesh consisting of nodes.

    Radiusdesk differentiates between a realm, a mesh and a site
    (I believe, where realm > mesh > site) but to keep things simple
    we keep nodes in a simple mesh group.
    """

    class Meta:
        verbose_name_plural = "meshes"

    name = models.CharField(max_length=128, primary_key=True)
    created = models.DateTimeField(auto_now_add=True)
    wlanconfs = models.ManyToManyField(WlanConf, blank=True)
    location = models.CharField(max_length=255, null=True, blank=True)
    lat = models.FloatField(default=0.0)
    lon = models.FloatField(default=0.0)
    maintainers = models.ManyToManyField(User, blank=True)


class MeshSettings(models.Model):
    """Settings for a group of nodes."""

    mesh = models.OneToOneField(Mesh, on_delete=models.CASCADE, related_name="settings")

    alerts_enabled = models.BooleanField(default=True)
    check_rtt = models.IntegerField(null=True, blank=True)
    check_cpu = models.IntegerField(null=True, blank=True)
    check_mem = models.IntegerField(null=True, blank=True)
    check_active = models.DurationField(null=True, blank=True)
    check_daily_data_usage = models.FloatField(null=True, blank=True)
    check_hourly_data_usage = models.FloatField(null=True, blank=True)
    check_daily_uptime = models.IntegerField(null=True, blank=True)
    check_hourly_uptime = models.IntegerField(null=True, blank=True)


class Node(models.Model):
    """Database table for network devices.

    Nodes can be both APs (Access Points) or Mesh Nodes. Radiusdesk has two
    separate tables for these two types, but we treat them as the same table
    (albeit with the `is_ap` and `nas_name` fields.)

    I sometimes use the terms 'node' and 'device' interchangably, although 'node' is
    probably more accurate seeing that e.g. client devices are also network devices
    but they aren't network nodes that can route data.
    """

    class Meta:

        ordering = ["name"]

    class Hardware(models.TextChoices):
        """Hardware choices."""

        UBNT_AC_MESH = "ubnt_ac_mesh", "Ubiquiti AC Mesh"
        TP_LINK_EAP = "tl_eap225_3_o", "TPLink EAP"

    class Status(models.TextChoices):
        """Status choices."""

        UNKNOWN = "unknown", "Unknown"
        OFFLINE = "offline", "Offline"
        ONLINE = "online", "Online"
        REBOOTING = "rebooting", "Rebooting"

    class HealthStatus(models.TextChoices):
        """Health status choices."""

        UNKNOWN = "unknown", "Unknown"
        CRITICAL = "critical", "Critical"
        WARNING = "warning", "Warning"
        DECENT = "decent", "Decent"
        OK = "ok", "Ok"

    # Required Fields
    mac = MACAddressField(primary_key=True, help_text="Physical MAC address")
    name = models.CharField(max_length=255, unique=True, help_text="Unique device name")
    # Optional Fields
    mesh = models.ForeignKey(Mesh, on_delete=models.CASCADE, null=True, blank=True)
    adopted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="The date & time that this device was adopted into its mesh",
    )
    last_contact = models.DateTimeField(
        null=True, blank=True, help_text="The time of last active contect"
    )
    last_ping = models.DateTimeField(
        null=True,
        blank=True,
        help_text="The time that this device was last pinged by the server",
    )
    is_ap = models.BooleanField(
        default=False,
        help_text=(
            "Determines whether this device is an AP (Access Point) "
            "which clients can connect to, or a mesh node that connects other nodes"
        ),
    )
    nas_name = models.CharField(
        max_length=128,
        null=True,
        blank=True,
        help_text="The name of the NAS device for this node",
    )
    reachable = models.BooleanField(default=False)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.UNKNOWN,
        help_text="The online status of this device",
    )
    health_status = models.CharField(
        max_length=16,
        choices=HealthStatus.choices,
        default=HealthStatus.UNKNOWN,
        help_text=(
            "The health status of this node. "
            "Even devices that are online way not be functioning correctly"
        ),
    )
    reboot_flag = models.BooleanField(
        default=False,
        help_text="Will reboot the device the next time it tries to contact the server",
    )
    neighbours = models.ManyToManyField(
        "Node", blank=True, help_text="Neighbouring nodes in the mesh"
    )
    description = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="A user-friendly description of this device",
    )
    hardware = models.CharField(
        max_length=255,
        choices=Hardware.choices,
        default=Hardware.TP_LINK_EAP,
        help_text="The physical device type",
    )
    ip = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="The IP address of the device in the network",
    )
    lat = models.FloatField(
        blank=True, null=True, help_text="Geographical device latitude"
    )
    lon = models.FloatField(
        blank=True, null=True, help_text="Geographical device longitude"
    )
    created = models.DateTimeField(
        auto_now_add=True, help_text="The date & time this device was created"
    )

    @property
    def online(self) -> bool:
        """Check whether this node is online."""
        return self.status == Node.Status.ONLINE

    @online.setter
    def online(self, is_online: bool) -> None:
        """Set this node's online status."""
        self.status = Node.Status.ONLINE if is_online else Node.Status.OFFLINE

    @cached_property
    def last_rate_metric(self) -> DataRateMetric | None:
        """Get the last data rate metric for this node."""
        qs = DataRateMetric.objects.filter(
            mac=self.mac, tx_rate__isnull=False, rx_rate__isnull=False
        )
        return qs.order_by("-created").first()

    @cached_property
    def last_resource_metric(self) -> ResourcesMetric | None:
        """Get the last resource for this node."""
        return ResourcesMetric.objects.filter(mac=self.mac).order_by("-created").first()

    @cached_property
    def last_rtt_metric(self) -> RTTMetric | None:
        """Get the last RTT for this node."""
        return RTTMetric.objects.filter(mac=self.mac).order_by("-created").first()

    @cached_property
    def check_results(self) -> CheckResults:
        """Get new or cached check results for this node."""
        return CheckResults.run_checks(self)

    def get_cpu(self) -> bool | None:
        """Get device CPU usage."""
        return getattr(self.last_resource_metric, "cpu", None)

    def get_mem(self) -> bool | None:
        """Get device memory usage."""
        return getattr(self.last_resource_metric, "memory", None)

    def get_rtt(self) -> bool | None:
        """Get device RTT time."""
        return getattr(self.last_rtt_metric, "rtt_avg", None)

    def get_download_speed(self) -> float | None:
        """Get device download speed."""
        return getattr(self.last_rate_metric, "tx_rate", None)

    def get_upload_speed(self) -> float | None:
        """Get device upload speed."""
        return getattr(self.last_rate_metric, "rx_rate", None)

    def get_health_status(self) -> HealthStatus:
        """Convert CheckResults into health status."""
        # If no checks have been run, assume status is unknown
        if self.check_results.num_run == 0:
            return Node.HealthStatus.UNKNOWN
        if self.check_results.oll_korrect():
            return Node.HealthStatus.OK
        if self.check_results.fewer_than_half_failed():
            return Node.HealthStatus.DECENT
        if self.check_results.more_than_half_failed_but_not_all():
            return Node.HealthStatus.WARNING
        # All failed
        return Node.HealthStatus.CRITICAL

    def update_health_status(self, save: bool = True) -> None:
        """Run health checks and then update this node's health status."""
        self.health_status = self.get_health_status()
        if save:
            self.save(update_fields=["health_status"])

    def generate_alert(self) -> bool:
        """Generate an alert for this node, returns False if no alert is generated."""
        alert = Alert.from_node(self)
        # No alert was generated for this node, nothing to do
        if not alert:
            # Since there is no alert for this node, mark all previous alerts as resolved
            unresolved_alerts = Alert.objects.filter(node=self).exclude(
                status=Alert.Status.RESOLVED
            )
            for a in unresolved_alerts:
                a.resolve()
            return False
        return alert.generate(node=self)

    def __str__(self):
        return f"Node {self.name} ({self.mac})"


class Alert(models.Model):
    """Alert sent to network managers."""

    class Level(models.IntegerChoices):
        """Alert level choices."""

        WARNING = 1, "Warning"
        ERROR = 2, "Error"
        CRITICAL = 3, "Critical"

    class Type(models.IntegerChoices):
        """Alert type choices."""

        NODE_STATUS = 1, "Node Status"
        UPTIME_LOW = 2, "Uptime Low"
        DATA_USAGE_HIGH = 3, "Data Usage High"

    class Status(models.IntegerChoices):
        """Alert type choices."""

        NEW = 1, "New"
        UPGRADED = 2, "Upgraded"
        RENAME = 3, "Rename"
        RESOLVED = 4, "Resolved"

    TITLE_OFFLINE = "Node is offline"
    TITLE_HEALTH_BAD = "Node's health is bad"
    TITLE_HEALTH_CRITICAL = "Node's health is critical"

    TEXT_OFFLINE = "The device is unreachable by ping"
    TEXT_HEALTH_BAD_OR_CRITICAL = "The following health checks failed: {}"

    level = models.SmallIntegerField(choices=Level.choices)
    status = models.SmallIntegerField(choices=Status.choices, default=Status.NEW)
    type = models.SmallIntegerField(choices=Type.choices)
    title = models.CharField(max_length=100)
    text = models.CharField(max_length=255)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    node = models.ForeignKey(
        Node, on_delete=models.CASCADE, related_name="alerts", null=True, blank=True
    )
    mesh = models.ForeignKey(
        Mesh, on_delete=models.CASCADE, related_name="alerts", null=True, blank=True
    )

    @classmethod
    def from_node(cls, node: Node) -> "Alert | None":
        """Generate an alert from a node's status."""
        timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        if node.status == Node.Status.OFFLINE:
            # Level is critical, it should override any health check warnings.
            # Pretty useless to do health checks if the node is offline.
            return Alert(
                level=Alert.Level.CRITICAL,
                type=Alert.Type.NODE_STATUS,
                title=Alert.TITLE_OFFLINE,
                text=f"_{timestamp}_ {Alert.TEXT_OFFLINE}",
                node=node,
                mesh=node.mesh,
            )
        if node.health_status != Node.HealthStatus.OK:
            health_checks_failed = ", ".join(
                c.key for c in node.check_results if not c.passed
            )
            if node.health_status == Node.HealthStatus.CRITICAL:
                return cls(
                    level=Alert.Level.CRITICAL,
                    type=Alert.Type.NODE_STATUS,
                    title=Alert.TITLE_HEALTH_CRITICAL,
                    text=f"_{timestamp}_ {Alert.TEXT_HEALTH_BAD_OR_CRITICAL.format(health_checks_failed)}",
                    node=node,
                    mesh=node.mesh,
                )
            if node.health_status in (
                Node.HealthStatus.WARNING,
                Node.HealthStatus.DECENT,
            ):
                return Alert(
                    level=Alert.Level.ERROR,
                    type=Alert.Type.NODE_STATUS,
                    title=Alert.TITLE_HEALTH_BAD,
                    text=f"_{timestamp}_ {Alert.TEXT_HEALTH_BAD_OR_CRITICAL.format(health_checks_failed)}",
                    node=node,
                    mesh=node.mesh,
                )
        return None

    def add_event(self, text: str) -> str:
        """Add a timestamped event to the alert text."""
        timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"_{timestamp}_ {text}\n{self.text}"

    def generate(self, node: Node | None = None) -> bool:
        """Generate this alert if it is worse than previous alerts of the same type.

        If it is less severe than previous ones, they will be marked as resolved.

        NOTE: You should call this method instead of :meth:`save()` (or creating Alerts)
        through the manager, because this way existing alerts may not be resolved.

        :param node: Optional node this alert is associated with. If a node is specified,
            alerts for other nodes will not be resolved.

        :returns: True if the new alert was generated.
        """
        unresolved_alerts = Alert.objects.filter(type=self.type).exclude(
            status=Alert.Status.RESOLVED
        )
        if node:
            unresolved_alerts = unresolved_alerts.filter(node=node)
        # Only generate a new alert if the current state is worse than
        # that of an alert triggered last (or there are no previous alerts).
        # Otherwise we would be generating new alerts for the same state,
        # e.g. generating a WARNING alert for a node that has already got an
        # unresolved WARNING.
        latest_alert = unresolved_alerts.order_by("-created").first()
        result = True
        # Case 1: There is no previous alert, so a new alert is generated
        # regardless of what the status may have been before
        if not latest_alert:
            self.save()
        # Case 2: A new alert is generated because is is worse than the previous alerts
        elif self.level > latest_alert.level:
            latest_alert.upgrade(self)
        # Case 3: The new report is as bad as previous ones, but may have
        # changed its reasons, so we generate a new one anyway.
        elif self.level == latest_alert.level and self.title != latest_alert.title:
            latest_alert.rename(self)
        else:
            result = False
        # Mark all previous alerts that were worse than the current status as resolved.
        # E.g. if a node generated a CRITICAL alert, but is now OK, that previous alert
        # is assumed to have been resolved.
        alerts_worse_than_current_status = unresolved_alerts.filter(
            level__gt=self.level
        )
        for alert in alerts_worse_than_current_status:
            alert.resolve()
        return result

    def is_resolved(self) -> bool:
        """Check whether this alert has been resolved."""
        return self.status == Alert.Status.RESOLVED

    def upgrade(self, alert: "Alert", save: bool = True) -> None:
        """Upgrade to a more serious alert"""
        self.level = alert.level
        self.title = alert.title
        self.text = self.add_event(alert.text)
        self.modified = timezone.now()
        self.status = Alert.Status.UPGRADED
        if save:
            self.save(update_fields=["text", "level", "title", "modified", "status"])

    def rename(self, alert: "Alert", save: bool = True) -> None:
        """Rename to another alert."""
        self.title = alert.title
        self.modified = timezone.now()
        self.text = self.add_event(f"Renamed {self.title} -> {alert.title}")
        self.status = Alert.Status.RENAME
        if save:
            self.save(update_fields=["text", "title", "modified", "status"])

    def resolve(self, save: bool = True) -> None:
        """Mark this alert as resolved."""
        self.status = Alert.Status.RESOLVED
        self.modified = timezone.now()
        self.text = self.add_event("Resolved this alert")
        if save:
            self.save(update_fields=["status", "modified", "text"])

    def message(self) -> str:
        """Format alert as a message string (e.g. before sending via WhatsApp)."""
        statusName = Alert.Status(self.status).label
        levelName = Alert.Level(self.level).label
        text = f"*[{statusName} {levelName}]* {self.title}"
        if self.node:
            text += f"\nGenerated by node '{self.node.name}'"
        return f"{text}\n{self.text}"

    def __str__(self):
        return f"Alert for {self.node} level={self.level} [{self.created}]"


class Service(models.Model):

    SERVICE_TYPES = (
        ("utility", "utility"),
        ("entertainment", "entertainment"),
        ("games", "games"),
        ("education", "education"),
    )

    API_LOCATIONS = (("cloud", "cloud"), ("local", "local"))

    url = models.URLField(max_length=100, unique=True)
    name = models.CharField(max_length=20, unique=True)
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPES)
    api_location = models.CharField(max_length=10, choices=API_LOCATIONS)
