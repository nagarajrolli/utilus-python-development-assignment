import pandas as pd
from dateutil.relativedelta import relativedelta

from metrics.base import BaseMetric

_RETENTION_MONTHS = 3


class CohortRetentionMetric(BaseMetric):
    """
    Signup cohorts with 3-month retention.

    Customers are grouped by their signup month (cohort).  For each cohort:
      cohort_size            — number of unique customers in that signup month
      active_after_3_months  — customers with an active subscription on the
                               date (individual signup_date + 3 calendar months)
      retention_rate_3m      — active_after_3_months / cohort_size, rounded to 4 dp

    The retention check is point-in-time: a customer is counted as retained if
    they have any subscription where
        start_date <= retention_date
        AND (end_date >= retention_date  OR  end_date is null)

    Customers whose retention_date falls beyond the subscription data range are
    still evaluated — open subscriptions (no end_date) are treated as active
    indefinitely.
    """

    key = "cohort_retention_3m"

    def compute(
        self, customers: pd.DataFrame, subscriptions: pd.DataFrame
    ) -> list[dict]:
        custs = customers[customers["signup_date"].notna()].copy()
        if custs.empty:
            return []

        custs["cohort_month"] = custs["signup_date"].dt.to_period("M")
        subs = subscriptions

        results = []
        for cohort_month, group in custs.groupby("cohort_month", sort=True):
            cohort_size = len(group)
            active_count = 0

            for _, customer in group.iterrows():
                retention_date = pd.Timestamp(
                    customer["signup_date"] + relativedelta(months=_RETENTION_MONTHS)
                )
                customer_subs = subs[subs["customer_id"] == customer["customer_id"]]
                is_active = customer_subs[
                    (customer_subs["start_date"] <= retention_date)
                    & (
                        customer_subs["end_date"].isna()
                        | (customer_subs["end_date"] >= retention_date)
                    )
                ]
                if not is_active.empty:
                    active_count += 1

            retention_rate = (
                round(active_count / cohort_size, 4) if cohort_size > 0 else 0.0
            )
            results.append(
                {
                    "cohort_month": str(cohort_month),
                    "cohort_size": cohort_size,
                    "active_after_3_months": active_count,
                    "retention_rate_3m": retention_rate,
                }
            )

        return results
