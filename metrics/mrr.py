import pandas as pd

from metrics.base import BaseMetric


class MonthlyMRRMetric(BaseMetric):
    """
    Monthly Recurring Revenue.

    For every calendar month in the data range, sum the monthly_price of all
    subscriptions that are active during that month.  A subscription is
    considered active in month M when:
        start_date <= last day of M
        AND (end_date >= first day of M  OR  end_date is null)

    No proration is applied — a subscription active for even one day in a month
    contributes its full monthly_price to that month's MRR.
    """

    key = "monthly_mrr"

    def compute(
        self, customers: pd.DataFrame, subscriptions: pd.DataFrame
    ) -> list[dict]:
        subs = subscriptions
        if subs.empty:
            return []

        all_dates = pd.concat([subs["start_date"], subs["end_date"].dropna()])
        min_month = subs["start_date"].min().to_period("M")
        max_month = all_dates.max().to_period("M")

        results = []
        for month in pd.period_range(min_month, max_month, freq="M"):
            month_start = month.start_time
            month_end = month.end_time

            active = subs[
                (subs["start_date"] <= month_end)
                & (subs["end_date"].isna() | (subs["end_date"] >= month_start))
            ]
            mrr = round(float(active["monthly_price"].sum()), 2)
            results.append({"month": str(month), "mrr": mrr})

        return results
