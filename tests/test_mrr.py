import pytest

from metrics.mrr import MonthlyMRRMetric
from tests.conftest import make_subscriptions


@pytest.fixture
def metric() -> MonthlyMRRMetric:
    return MonthlyMRRMetric()


class TestMonthlyMRR:
    def test_empty_subscriptions_returns_empty(
        self, metric, no_customers, no_subscriptions
    ):
        assert metric.compute(no_customers, no_subscriptions) == []

    def test_single_open_subscription_appears_in_start_month(
        self, metric, no_customers
    ):
        subs = make_subscriptions([("C001", "2024-03-01", None, 50)])
        result = metric.compute(no_customers, subs)
        months = {r["month"]: r["mrr"] for r in result}
        assert months["2024-03"] == 50.0

    def test_subscription_spans_multiple_months(self, metric, no_customers):
        subs = make_subscriptions([("C001", "2024-01-15", "2024-03-15", 30)])
        months = {r["month"]: r["mrr"] for r in metric.compute(no_customers, subs)}
        assert months["2024-01"] == 30.0
        assert months["2024-02"] == 30.0
        assert months["2024-03"] == 30.0
        assert "2024-04" not in months

    def test_subscription_not_active_before_start_month(self, metric, no_customers):
        subs = make_subscriptions([("C001", "2024-02-01", None, 30)])
        months = {r["month"]: r["mrr"] for r in metric.compute(no_customers, subs)}
        assert "2024-01" not in months
        assert months["2024-02"] == 30.0

    def test_multiple_subscriptions_summed_in_same_month(self, metric, no_customers):
        subs = make_subscriptions(
            [("C001", "2024-01-01", None, 30), ("C002", "2024-01-10", None, 20)]
        )
        months = {r["month"]: r["mrr"] for r in metric.compute(no_customers, subs)}
        assert months["2024-01"] == 50.0

    def test_ended_subscription_excluded_from_next_month(self, metric, no_customers):
        subs = make_subscriptions([("C001", "2024-01-01", "2024-01-31", 50)])
        months = {r["month"]: r["mrr"] for r in metric.compute(no_customers, subs)}
        assert months["2024-01"] == 50.0
        assert "2024-02" not in months

    def test_subscription_ending_on_first_day_of_month_is_active_that_month(
        self, metric, no_customers
    ):
        # end_date = Feb 1 means the subscription was active on Feb 1
        subs = make_subscriptions([("C001", "2024-01-01", "2024-02-01", 40)])
        months = {r["month"]: r["mrr"] for r in metric.compute(no_customers, subs)}
        assert months["2024-02"] == 40.0

    def test_mrr_rounded_to_two_decimal_places(self, metric, no_customers):
        subs = make_subscriptions([("C001", "2024-01-01", None, 33.333)])
        months = {r["month"]: r["mrr"] for r in metric.compute(no_customers, subs)}
        assert months["2024-01"] == 33.33
