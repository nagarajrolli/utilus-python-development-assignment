import pandas as pd
import pytest

from metrics.churn import MonthlyChurnMetric
from tests.conftest import make_subscriptions


@pytest.fixture
def metric() -> MonthlyChurnMetric:
    return MonthlyChurnMetric()


class TestMonthlyChurn:
    def test_empty_subscriptions_returns_empty(self, metric, no_customers, no_subscriptions):
        assert metric.compute(no_customers, no_subscriptions) == []

    def test_open_subscription_is_not_churn(self, metric, no_customers):
        subs = make_subscriptions([("C001", "2024-01-01", None, 30)])
        result = metric.compute(no_customers, subs)
        assert all(r["churned_customers"] == 0 for r in result)

    def test_ended_subscription_with_no_resubscription_is_churn(self, metric, no_customers):
        subs = make_subscriptions([("C001", "2024-01-01", "2024-03-15", 30)])
        months = {r["month"]: r["churned_customers"] for r in metric.compute(no_customers, subs)}
        assert months["2024-03"] == 1

    def test_resubscription_within_30_days_is_not_churn(self, metric, no_customers):
        subs = make_subscriptions(
            [
                ("C001", "2024-01-01", "2024-03-15", 30),
                ("C001", "2024-04-01", None, 30),  # 17 days later
            ]
        )
        months = {r["month"]: r["churned_customers"] for r in metric.compute(no_customers, subs)}
        assert months.get("2024-03", 0) == 0

    def test_resubscription_exactly_30_days_later_is_not_churn(self, metric, no_customers):
        # end_date = 2024-03-01; 30 days later = 2024-03-31 (inclusive boundary)
        subs = make_subscriptions(
            [
                ("C001", "2024-01-01", "2024-03-01", 30),
                ("C001", "2024-03-31", None, 30),
            ]
        )
        months = {r["month"]: r["churned_customers"] for r in metric.compute(no_customers, subs)}
        assert months.get("2024-03", 0) == 0

    def test_resubscription_31_days_later_is_churn(self, metric, no_customers):
        # end_date = 2024-03-01; 31 days later = 2024-04-01 (outside window)
        subs = make_subscriptions(
            [
                ("C001", "2024-01-01", "2024-03-01", 30),
                ("C001", "2024-04-01", None, 30),
            ]
        )
        months = {r["month"]: r["churned_customers"] for r in metric.compute(no_customers, subs)}
        assert months["2024-03"] == 1

    def test_multiple_churns_same_month(self, metric, no_customers):
        subs = make_subscriptions(
            [
                ("C001", "2024-01-01", "2024-03-15", 30),
                ("C002", "2024-01-01", "2024-03-20", 25),
            ]
        )
        months = {r["month"]: r["churned_customers"] for r in metric.compute(no_customers, subs)}
        assert months["2024-03"] == 2

    def test_churns_in_different_months(self, metric, no_customers):
        subs = make_subscriptions(
            [
                ("C001", "2024-01-01", "2024-02-15", 30),
                ("C002", "2024-01-01", "2024-04-20", 25),
            ]
        )
        months = {r["month"]: r["churned_customers"] for r in metric.compute(no_customers, subs)}
        assert months["2024-02"] == 1
        assert months.get("2024-03", 0) == 0
        assert months["2024-04"] == 1

    def test_all_months_in_range_are_present(self, metric, no_customers):
        subs = make_subscriptions([("C001", "2024-01-01", "2024-03-01", 30)])
        months = [r["month"] for r in metric.compute(no_customers, subs)]
        assert "2024-01" in months
        assert "2024-02" in months
        assert "2024-03" in months

    def test_plan_change_within_30_days_is_not_churn(self, metric, no_customers):
        # Customer ends basic and starts pro the next day — not a churn
        subs = make_subscriptions(
            [
                ("C001", "2024-01-01", "2024-03-31", 30),
                ("C001", "2024-04-01", None, 50),
            ]
        )
        months = {r["month"]: r["churned_customers"] for r in metric.compute(no_customers, subs)}
        assert months.get("2024-03", 0) == 0