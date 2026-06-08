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

    @pytest.mark.parametrize(
        "end_date, resub_date, churn_month, expected_churn",
        [
            ("2024-03-15", "2024-04-01", "2024-03", 0),  # 17 days — within window
            ("2024-03-01", "2024-03-31", "2024-03", 0),  # exactly 30 days — inclusive boundary
            ("2024-03-01", "2024-04-01", "2024-03", 1),  # 31 days — outside window
            ("2024-03-31", "2024-04-01", "2024-03", 0),  # plan change next day
        ],
        ids=["within_30_days", "exactly_30_days", "31_days_is_churn", "plan_change"],
    )
    def test_resubscription_window(
        self, metric, no_customers, end_date, resub_date, churn_month, expected_churn
    ):
        subs = make_subscriptions(
            [
                ("C001", "2024-01-01", end_date, 30),
                ("C001", resub_date, None, 30),
            ]
        )
        months = {r["month"]: r["churned_customers"] for r in metric.compute(no_customers, subs)}
        assert months.get(churn_month, 0) == expected_churn

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
