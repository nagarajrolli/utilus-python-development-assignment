# Design Document

## Code Structure

Three layers, each with a single responsibility:

| Layer | Responsibility |
|---|---|
| `data/loader.py` | I/O and data quality; delivers clean DataFrames |
| `metrics/*.py` | Pure business logic on clean data |
| `main.py` | CLI wiring, metric registration, JSON output |

Each metric subclasses `BaseMetric` and implements two things: a `key` (the JSON field name) and a `compute(customers, subscriptions) -> list[dict]` method. The `_METRICS` list in `main.py` is the single registration point — every metric in the list is automatically included in the report. Metrics trust the loader contract and contain no defensive data checks.

## Business Rules

**MRR** — a subscription is active in month M when `start_date ≤ last_day(M) AND (end_date ≥ first_day(M) OR end_date is null)`. No proration: a subscription active for even one day contributes its full `monthly_price`.

**Churn** — a churn event occurs when a subscription has an `end_date` and the customer has no new subscription with `start_date` in `(end_date, end_date + 30 days]`. Attributed to the calendar month of `end_date`. The 30-day boundary is inclusive.

**Cohort retention** — customers are grouped by signup month. Each customer's retention check date is `signup_date + 3 calendar months` (via `dateutil.relativedelta`, so Jan 31 → Apr 30). A customer is retained if they have any subscription where `start_date ≤ check_date AND (end_date ≥ check_date OR end_date is null)`.

## Adding a New Metric

1. Create `metrics/my_metric.py`:

```python
from metrics.base import BaseMetric
import pandas as pd

class MyMetric(BaseMetric):
    key = "my_metric"

    def compute(self, customers: pd.DataFrame, subscriptions: pd.DataFrame) -> list[dict]:
        return [{"field": value}]
```

2. Register it in `main.py`:

```python
_METRICS = [..., MyMetric()]
```

3. Add tests in `tests/test_my_metric.py`.

No other files need to change.

## Assumptions and Trade-offs

- **No proration in MRR**: one day of activity counts the full monthly price. Proration is not specified and would require daily-rate logic.
- **Overlapping subscriptions**: one active subscription per customer at a time; the earlier-starting row is kept and the later one dropped. A side-effect is that a customer whose overlapping row was dropped may appear churned even if they were still active.
- **Unknown `customer_id` in subscriptions**: included in MRR and churn (revenue is real regardless of CRM gaps) but excluded from cohort retention (which is customer-driven). A warning is logged.
- **Duplicate `customer_id` in customers**: earlier signup date kept.
- **Recent cohorts** may show artificially high retention: open subscriptions are treated as active indefinitely, so cohorts whose 3-month check date falls beyond the data range will show inflated retention.
- **Skip-and-warn over fail-fast**: all data quality issues drop the offending row and log a warning so the report is always produced for the rows that are valid.