from datetime import datetime
from django.test import TestCase

from .models import DataUsageMetric, Metric
from . import tasks

# Create your tests here.


def test_metrics_round_down():
    dt = datetime.fromisoformat("2024-08-22 16:45:15+00:00")
    assert str(Metric.Granularity.DAILY.round_down(dt)) == "2024-08-22 00:00:00+00:00"
    assert str(Metric.Granularity.HOURLY.round_down(dt)) == "2024-08-22 16:00:00+00:00"
    assert str(Metric.Granularity.MONTHLY.round_down(dt)) == "2024-08-01 00:00:00+00:00"


class TestMetricModel(TestCase):

    databases = {"default", "metrics_db"}

    def setUp(self):
        DataUsageMetric.objects.create(mac="ec:27:2f:bf:12:1c", rx_bytes=10, tx_bytes=0, created="2024-08-22 16:16:00+00:00")
        DataUsageMetric.objects.create(mac="ec:27:2f:bf:12:1c", rx_bytes=10, tx_bytes=10, created="2024-08-22 16:30:00+00:00")
        DataUsageMetric.objects.create(mac="ec:27:2f:bf:12:1c", rx_bytes=0, tx_bytes=10, created="2024-08-23 16:16:00+00:00")
        DataUsageMetric.objects.create(mac="ec:27:2f:bf:12:1c", rx_bytes=10, tx_bytes=0, created="2024-09-22 10:00:00+00:00")
        DataUsageMetric.objects.create(mac="f7:bb:16:fb:26:ac", rx_bytes=0, tx_bytes=10, created="2024-08-22 16:16:00+00:00")
        DataUsageMetric.objects.create(mac="f7:bb:16:fb:26:ac", rx_bytes=10, tx_bytes=0, created="2024-08-22 17:30:00+00:00")

    def reset(self):
        DataUsageMetric.objects.all().delete()
        self.setUp()

    def test_metrics_aggregation_decreases_count(self):
        assert DataUsageMetric.objects.count() == 6
        tasks.aggregate_metrics(DataUsageMetric, Metric.Granularity.HOURLY)
        assert DataUsageMetric.objects.count() == 5
        tasks.aggregate_metrics(DataUsageMetric, Metric.Granularity.DAILY)
        assert DataUsageMetric.objects.count() == 4
        tasks.aggregate_metrics(DataUsageMetric, Metric.Granularity.MONTHLY)
        assert DataUsageMetric.objects.count() == 3

    def test_metrics_aggregation_doesnt_change_totals(self):
        old_totals = DataUsageMetric.objects.all().get_sum("rx_bytes")
        tasks.aggregate_metrics(DataUsageMetric, Metric.Granularity.HOURLY)
        new_totals = DataUsageMetric.objects.all().get_sum("rx_bytes")
        assert old_totals == new_totals

    def test_aggregation_order_doesnt_change_totals(self):
        tasks.aggregate_metrics(DataUsageMetric, Metric.Granularity.HOURLY)
        tasks.aggregate_metrics(DataUsageMetric, Metric.Granularity.DAILY)
        tasks.aggregate_metrics(DataUsageMetric, Metric.Granularity.MONTHLY)
        t1 = DataUsageMetric.objects.all().get_sum("rx_bytes")
        self.reset()
        tasks.aggregate_metrics(DataUsageMetric, Metric.Granularity.MONTHLY)
        tasks.aggregate_metrics(DataUsageMetric, Metric.Granularity.HOURLY)
        tasks.aggregate_metrics(DataUsageMetric, Metric.Granularity.DAILY)
        t2 = DataUsageMetric.objects.all().get_sum("rx_bytes")
        self.reset()
        tasks.aggregate_metrics(DataUsageMetric, Metric.Granularity.DAILY)
        tasks.aggregate_metrics(DataUsageMetric, Metric.Granularity.MONTHLY)
        tasks.aggregate_metrics(DataUsageMetric, Metric.Granularity.HOURLY)
        t3 = DataUsageMetric.objects.all().get_sum("rx_bytes")
        assert t1 == t2 == t3