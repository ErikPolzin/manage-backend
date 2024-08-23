from django.test import TestCase

from metrics.models import ResourcesMetric, RTTMetric
from .models import Mesh, Node, MeshSettings


class TestMeshModel(TestCase):

    def test_settings_creation(self):
        mesh = Mesh.objects.create(name="testmesh")
        # Check that a MeshSettings instance has been crated
        self.assertIsInstance(mesh.settings, MeshSettings)
        old_id = mesh.settings.id
        # No new settings created
        mesh.save()
        self.assertEqual(old_id, mesh.settings.id)


class TestAlertModel(TestCase):

    databases = {"default", "metrics_db"}

    def setUp(self):
        self.mesh = Mesh.objects.create(name="testmesh")
        self.node = Node.objects.create(
            mac="6c:75:14:7d:65:d4",
            name="testnode",
            mesh=self.mesh
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
        RTTMetric.objects.create(rtt_min=100, rtt_max=600, rtt_avg=200, mac=self.node.mac)
        assert not self.node.generate_alert()
        self.mesh.settings.check_rtt = 100
        self.mesh.settings.save()
        rtt_alert = self.node.generate_alert()
        assert rtt_alert and not rtt_alert.is_resolved() and "rtt" in rtt_alert.text
        RTTMetric.objects.create(rtt_min=50, rtt_max=200, rtt_avg=75, mac=self.node.mac)
        assert not self.node.generate_alert()
        rtt_alert.refresh_from_db()
        assert rtt_alert.is_resolved()
