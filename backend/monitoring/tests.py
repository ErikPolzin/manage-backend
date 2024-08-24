from datetime import datetime
from django.test import TestCase

from metrics.models import ResourcesMetric, RTTMetric, DataUsageMetric
from .models import Mesh, Node, MeshSettings


class TestMeshModel(TestCase):
    """Test cases related to the Mesh model."""

    databases = {"default", "metrics_db"}

    def setUp(self):
        # Setup two test meshes, one with two nodes, one with a single node
        meshA = Mesh.objects.create(name="meshA")
        meshB = Mesh.objects.create(name="meshB")
        Node.objects.create(mac="6c:75:14:7d:65:d4", name="nodeA", mesh=meshA)
        Node.objects.create(mac="c6:e5:08:9b:88:cf", name="nodeB", mesh=meshA)
        Node.objects.create(mac="03:96:15:b4:57:64", name="nodeC", mesh=meshB)
        # Create some dummy metrics
        DataUsageMetric.objects.create(
            mac="6c:75:14:7d:65:d4",  # Node A
            tx_bytes=100,
            rx_bytes=50,
            created="2024-08-22 15:00:00+00:00",
        )
        DataUsageMetric.objects.create(
            mac="6c:75:14:7d:65:d4",  # Node A
            tx_bytes=2000,
            rx_bytes=20,
            created="2024-08-22 16:30:00+00:00",
        )
        DataUsageMetric.objects.create(
            mac="c6:e5:08:9b:88:cf",  # Node B
            tx_bytes=40,
            rx_bytes=600,
            created="2024-08-22 12:00:00+00:00",
        )
        DataUsageMetric.objects.create(
            mac="c6:e5:08:9b:88:cf",  # Node B
            tx_bytes=600,
            rx_bytes=500,
            created="2024-08-18 12:05:00+00:00",
        )
        DataUsageMetric.objects.create(
            mac="03:96:15:b4:57:64",  # Node C
            tx_bytes=700,
            rx_bytes=1000,
            created="2024-08-22 16:00:00+00:00",
        )

    def test_settings_creation(self):
        mesh = Mesh.objects.get(name="meshA")
        # Check that a MeshSettings instance has been crated
        self.assertIsInstance(mesh.settings, MeshSettings)
        old_id = mesh.settings.id
        # No new settings created
        mesh.save()
        self.assertEqual(old_id, mesh.settings.id)

    def test_daily_data_usage_adds_rx_and_tx_bytes(self):
        meshB = Mesh.objects.get(name="meshB")
        now = datetime.fromisoformat("2024-08-22 17:00:00+00:00")
        assert meshB.get_daily_data_usage(now) == 1700

    def test_daily_data_usage_includes_relevant_nodes(self):
        meshA = Mesh.objects.get(name="meshA")
        now = datetime.fromisoformat("2024-08-22 17:05:00+00:00")
        assert meshA.get_daily_data_usage(now) == 2810

    def test_hourly_data_usage(self):
        meshA = Mesh.objects.get(name="meshA")
        now = datetime.fromisoformat("2024-08-22 16:50:00+00:00")
        assert meshA.get_hourly_data_usage(now) == 2020

    def test_no_data_usage(self):
        meshA = Mesh.objects.get(name="meshA")
        now = datetime.fromisoformat("2028-08-22 16:50:00+00:00")
        assert meshA.get_hourly_data_usage(now) == 0


class TestAlertModel(TestCase):
    """Test cases related to the Alert model."""

    databases = {"default", "metrics_db"}

    def setUp(self):
        self.mesh = Mesh.objects.create(name="testmesh")
        self.node = Node.objects.create(
            mac="6c:75:14:7d:65:d4", name="testnode", mesh=self.mesh
        )

    def test_high_cpu_generates_alert_then_resolves(self):
        assert not self.node.generate_alert()
        ResourcesMetric.objects.create(memory=90, cpu=95, mac=self.node.mac)
        assert not self.node.generate_alert()
        self.mesh.settings.check_cpu = 80
        self.mesh.settings.save()
        cpu_alert = self.node.generate_alert()
        assert cpu_alert and not cpu_alert.is_resolved() and "cpu" in cpu_alert.text
        ResourcesMetric.objects.create(memory=40, cpu=20, mac=self.node.mac)
        assert not self.node.generate_alert()
        cpu_alert.refresh_from_db()
        assert cpu_alert.is_resolved()

    def test_high_memory_generates_alert_then_resolves(self):
        assert not self.node.generate_alert()
        ResourcesMetric.objects.create(memory=90, cpu=95, mac=self.node.mac)
        assert not self.node.generate_alert()
        self.mesh.settings.check_mem = 50
        self.mesh.settings.save()
        mem_alert = self.node.generate_alert()
        assert mem_alert and not mem_alert.is_resolved() and "mem" in mem_alert.text
        ResourcesMetric.objects.create(memory=40, cpu=20, mac=self.node.mac)
        assert not self.node.generate_alert()
        mem_alert.refresh_from_db()
        assert mem_alert.is_resolved()

    def test_high_rtt_generates_alert_then_resolves(self):
        assert not self.node.generate_alert()
        RTTMetric.objects.create(
            rtt_min=100, rtt_max=600, rtt_avg=200, mac=self.node.mac
        )
        assert not self.node.generate_alert()
        self.mesh.settings.check_rtt = 100
        self.mesh.settings.save()
        rtt_alert = self.node.generate_alert()
        assert rtt_alert and not rtt_alert.is_resolved() and "rtt" in rtt_alert.text
        RTTMetric.objects.create(rtt_min=50, rtt_max=200, rtt_avg=75, mac=self.node.mac)
        assert not self.node.generate_alert()
        rtt_alert.refresh_from_db()
        assert rtt_alert.is_resolved()

    def test_high_daily_data_usage_generates_alert(self):
        assert not self.node.generate_alert()
        DataUsageMetric.objects.create(rx_bytes=100, tx_bytes=600, mac=self.node.mac)
        assert not self.mesh.generate_alert()
        self.mesh.settings.check_daily_data_usage = 650
        self.mesh.settings.save()
        data_alert = self.mesh.generate_alert()
        assert (
            data_alert
            and not data_alert.is_resolved()
            and "data_usage" in data_alert.text
        )
