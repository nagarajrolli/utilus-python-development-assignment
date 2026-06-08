from datetime import timedelta

import pandas as pd

from metrics.base import BaseMetric

_RESUBSCRIBE_WINDOW_DAYS = 30


class MonthlyChurnMetric(BaseMetric):
    """
    Monthly churned customer count.

    A churn event occurs when a subscription has an end_date AND the customer
    has no new subscription whose start_date falls in the half-open interval
    (end_date, end_date + 30 days] — i.e. strictly after the end_date and
    within 30 days inclusive.

    The churn event is attributed to the calendar month of the end_date.

    All months in the subscription data range are included in the output,
    with churned_customers = 0 for months with no events.
    """

    key = "monthly_churn"

    def compute(self, customers: pd.DataFrame, subscriptions: pd.DataFrame) -> list[dict]:
        subs = subscriptions
        if subs.empty:
            return []

        churn_by_month: dict = {}

        ended = subs[subs["end_date"].notna()]
        for _, row in ended.iterrows():
            end_date: pd.Timestamp = row["end_date"]
            window_end = end_date + timedelta(days=_RESUBSCRIBE_WINDOW_DAYS)

            resubscribed = subs[
                (subs["customer_id"] == row["customer_id"])
                & (subs["start_date"] > end_date)
                & (subs["start_date"] <= window_end)
            ]
            if resubscribed.empty:
                month = end_date.to_period("M")
                churn_by_month[month] = churn_by_month.get(month, 0) + 1

        all_dates = pd.concat([subs["start_date"], subs["end_date"].dropna()])
        min_month = subs["start_date"].min().to_period("M")
        max_month = all_dates.max().to_period("M")

        return [
            {"month": str(m), "churned_customers": churn_by_month.get(m, 0)}
            for m in pd.period_range(min_month, max_month, freq="M")
        ]