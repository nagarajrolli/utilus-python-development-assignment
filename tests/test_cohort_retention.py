import pandas as pd
import pytest

from metrics.cohort_retention import CohortRetentionMetric
from tests.conftest import make_customers, make_subscriptions


@pytest.fixture
def metric() -> CohortRetentionMetric:
    return CohortRetentionMetric()


class TestCohortRetention:
    def test_empty_customers_returns_empty(self, metric, no_customers, no_subscriptions):
        assert metric.compute(no_customers, no_subscriptions) == []

    def test_cohort_size_counts_customers_in_signup_month(self, metric):
        customers = make_customers(
            [("C001", "2024-01-05", "NL"), ("C002", "2024-01-20", "DE"), ("C003", "2024-02-01", "FR")]
        )
        subs = make_subscriptions(
            [("C001", "2024-01-05", None, 30), ("C002", "2024-01-20", None, 25), ("C003", "2024-02-01", None, 20)]
        )
        result = {r["cohort_month"]: r for r in metric.compute(customers, subs)}
        assert result["2024-01"]["cohort_size"] == 2
        assert result["2024-02"]["cohort_size"] == 1

    def test_active_customer_counted_after_3_months(self, metric):
        # C001 signed up 2024-01-05; retention_date = 2024-04-05; open sub → active
        customers = make_customers([("C001", "2024-01-05", "NL")])
        subs = make_subscriptions([("C001", "2024-01-05", None, 30)])
        result = metric.compute(customers, subs)[0]
        assert result["active_after_3_months"] == 1
        assert result["retention_rate_3m"] == 1.0

    def test_inactive_customer_not_counted_after_3_months(self, metric):
        # Subscription ends before the retention check date
        customers = make_customers([("C001", "2024-01-05", "NL")])
        subs = make_subscriptions([("C001", "2024-01-05", "2024-02-01", 30)])
        result = metric.compute(customers, subs)[0]
        assert result["active_after_3_months"] == 0
        assert result["retention_rate_3m"] == 0.0

    def test_retention_rate_is_fraction_of_cohort(self, metric):
        customers = make_customers(
            [("C001", "2024-01-05", "NL"), ("C002", "2024-01-20", "DE")]
        )
        subs = make_subscriptions(
            [
                ("C001", "2024-01-05", None, 30),          # active on 2024-04-05 ✓
                ("C002", "2024-01-20", "2024-02-28", 25),  # ended before 2024-04-20
            ]
        )
        result = metric.compute(customers, subs)[0]
        assert result["active_after_3_months"] == 1
        assert result["retention_rate_3m"] == 0.5

    def test_customer_with_no_subscription_is_not_active(self, metric, no_subscriptions):
        customers = make_customers([("C001", "2024-01-05", "NL")])
        result = metric.compute(customers, no_subscriptions)[0]
        assert result["active_after_3_months"] == 0
        assert result["retention_rate_3m"] == 0.0

    def test_cohorts_ordered_chronologically(self, metric):
        customers = make_customers(
            [("C001", "2024-03-01", "NL"), ("C002", "2024-01-01", "DE")]
        )
        subs = make_subscriptions(
            [("C001", "2024-03-01", None, 30), ("C002", "2024-01-01", None, 25)]
        )
        result = metric.compute(customers, subs)
        assert result[0]["cohort_month"] == "2024-01"
        assert result[1]["cohort_month"] == "2024-03"

    def test_resubscribed_customer_active_at_check_date_is_counted(self, metric):
        # Customer churned and resubscribed; has active sub at retention_date
        customers = make_customers([("C001", "2024-01-05", "NL")])
        subs = make_subscriptions(
            [
                ("C001", "2024-01-05", "2024-02-01", 30),
                ("C001", "2024-03-15", None, 30),  # resubscribed; active on 2024-04-05 ✓
            ]
        )
        result = metric.compute(customers, subs)[0]
        assert result["active_after_3_months"] == 1

    def test_subscription_starting_exactly_on_retention_date_counts(self, metric):
        # start_date == retention_date is the boundary — should be active
        customers = make_customers([("C001", "2024-01-05", "NL")])
        # retention_date = 2024-04-05; subscription starts exactly on that date
        subs = make_subscriptions([("C001", "2024-04-05", None, 30)])
        result = metric.compute(customers, subs)[0]
        assert result["active_after_3_months"] == 1

    def test_subscription_ending_exactly_on_retention_date_counts(self, metric):
        # end_date == retention_date means the subscription was still active that day
        customers = make_customers([("C001", "2024-01-05", "NL")])
        subs = make_subscriptions([("C001", "2024-01-05", "2024-04-05", 30)])
        result = metric.compute(customers, subs)[0]
        assert result["active_after_3_months"] == 1