# Design Document — Subscription Metrics

## Overview

This project reads two CSV files (`customers.csv`, `subscriptions.csv`), computes
three subscription-business metrics, and writes a single JSON report.

```
python main.py customers.csv subscriptions.csv output.json
```

---

## Project Structure

```
.
├── main.py                        # CLI entry point (click)
├── data/
│   ├── __init__.py
│   └── loader.py                  # CSV loading, cleaning, validation
├── metrics/
│   ├── __init__.py
│   ├── base.py                    # BaseMetric abstract class
│   ├── mrr.py                     # Monthly MRR
│   ├── churn.py                   # Monthly churned customers
│   └── cohort_retention.py        # Signup cohorts with 3-month retention
├── tests/
│   ├── __init__.py
│   ├── conftest.py                # Shared fixtures and DataFrame helpers
│   ├── test_loader.py
│   ├── test_mrr.py
│   ├── test_churn.py
│   └── test_cohort_retention.py
├── customers.csv
├── subscriptions.csv
├── requirements.txt
└── DESIGN.md
```

---

## Data Model

### customers.csv

| Column       | Type   | Notes                          |
|--------------|--------|--------------------------------|
| customer_id  | string | Primary identifier             |
| signup_date  | date   | Date the customer first joined |
| country      | string | ISO country code               |

### subscriptions.csv

| Column        | Type    | Notes                                               |
|---------------|---------|-----------------------------------------------------|
| customer_id   | string  | Foreign key to customers                            |
| start_date    | date    | First day the subscription was active               |
| end_date      | date    | Last day the subscription was active; blank = still active |
| plan          | string  | Plan name (e.g. `basic`, `pro`)                     |
| monthly_price | numeric | Price charged per month                             |

---

## Data Quality Handling

The loader (`data/loader.py`) applies all cleaning before metrics are computed.
Every dropped or modified row is logged as a `WARNING` to stderr.

### customers.csv

| Issue | Handling |
|---|---|
| Unparseable `signup_date` (e.g. month 13, text) | Row skipped — no valid cohort date |
| Duplicate `customer_id` | Earlier `signup_date` kept; later record dropped |
| `country` in lowercase | Normalised to uppercase |
| Missing `country` | Row kept — country is not used by any current metric |
| Leading/trailing whitespace | Stripped from all string fields |

**Assumption:** when two records share the same `customer_id`, the one with the
earlier `signup_date` represents the original customer account.

### subscriptions.csv

| Issue | Handling |
|---|---|
| Unparseable `start_date` | Row skipped |
| Blank / whitespace-only `end_date` | Treated as `null` (subscription still active) |
| Non-blank unparseable `end_date` | Row skipped |
| Non-numeric `monthly_price` | Row skipped |
| `end_date` < `start_date` | Row skipped |
| Leading/trailing whitespace in dates | Stripped before parsing |
| Overlapping subscriptions (same customer) | Earlier-starting row kept; later-starting overlapping row dropped |
| Subscription for unknown `customer_id` | Kept — revenue is real regardless of CRM integrity |

**Assumption — overlapping subscriptions:** business rule is one active
subscription per customer at a time.  When two rows for the same customer
overlap, the earlier-starting one is authoritative.  A side-effect is that a
customer whose overlapping subscription was dropped may show up as churned in
the churn metric even though they were in fact still active.

---

## Business Rules

### Metric 1 — Monthly MRR (`monthly_mrr`)

For every calendar month in the subscription data range, sum `monthly_price`
for all subscriptions that were active during that month.

A subscription is **active in month M** when:
```
start_date <= last_day(M)  AND  (end_date >= first_day(M)  OR  end_date is null)
```

**No proration:** a subscription active for even one day in a month contributes
its full `monthly_price` to that month's MRR.

The output covers every calendar month from `min(start_date)` to
`max(all subscription dates)`, inclusive.

### Metric 2 — Monthly Churn (`monthly_churn`)

A **churn event** occurs when a subscription has an `end_date` AND the customer
has no other subscription with a `start_date` in the window
`(end_date, end_date + 30 days]` — i.e. strictly after the `end_date`, within
30 days inclusive.

The event is attributed to the calendar month of the `end_date`.

**30-day window is inclusive:** a re-subscription starting exactly 30 days after
the end date is treated as a re-subscribe (not a churn).

Plan changes or upgrades (e.g. end basic on Mar 31, start pro on Apr 1) are
treated as continuous activity and do not produce a churn event.

The output covers every calendar month in the same range as the MRR metric, with
`churned_customers = 0` for months with no events.

### Metric 3 — Cohort Retention (`cohort_retention_3m`)

Customers are grouped by their **signup month** (year-month of `signup_date`).

For each cohort:

| Field | Definition |
|---|---|
| `cohort_month` | Year-month of signup (e.g. `2024-01`) |
| `cohort_size` | Number of customers in that signup month |
| `active_after_3_months` | Customers with an active subscription on `signup_date + 3 calendar months` |
| `retention_rate_3m` | `active_after_3_months / cohort_size`, rounded to 4 decimal places |

The retention check is **point-in-time per customer**: each customer's check date
is their own `signup_date + 3 calendar months` (using calendar-month arithmetic,
so Jan 31 + 3 months = Apr 30, not May 1).

A customer is considered active on a given date when they have any subscription
where:
```
start_date <= check_date  AND  (end_date >= check_date  OR  end_date is null)
```

**Note on recent cohorts:** customers who signed up in the last three months will
have a `retention_date` beyond the data range.  Open subscriptions are still
counted as active (no end date means no observed churn), which may result in
artificially high retention rates for recent cohorts.

---

## Architecture

### BaseMetric

```python
class BaseMetric(ABC):
    key: str                    # JSON key in the report
    def compute(customers, subscriptions) -> list[dict]: ...
```

Each metric is a stateless class.  `compute` receives the two cleaned DataFrames
and returns a list of plain dicts that are directly JSON-serialisable.

The `_METRICS` list in `main.py` is the single point of registration — all
metrics in the list are automatically included in the report.

### Separation of concerns

| Layer | Responsibility |
|---|---|
| `data/loader.py` | I/O and data quality; delivers clean DataFrames |
| `metrics/*.py` | Pure business logic on clean data |
| `main.py` | CLI wiring, orchestration, JSON output |

Metrics receive pre-cleaned DataFrames and make no defensive checks — they trust
the loader contract.  This keeps business logic readable.

---

## How to Add a New Metric

1. Create `metrics/my_metric.py`:

```python
from metrics.base import BaseMetric
import pandas as pd

class MyMetric(BaseMetric):
    key = "my_metric"

    def compute(self, customers: pd.DataFrame, subscriptions: pd.DataFrame) -> list[dict]:
        # ... compute and return list[dict]
        return [{"some_field": value}]
```

2. Register it in `main.py`:

```python
from metrics.my_metric import MyMetric

_METRICS = [
    MonthlyMRRMetric(),
    MonthlyChurnMetric(),
    CohortRetentionMetric(),
    MyMetric(),           # add here
]
```

3. Add tests in `tests/test_my_metric.py`.

No other files need to change.

---

## Assumptions

1. `monthly_price` is the flat fee for any month in which the subscription is
   active, regardless of how many days were actually used (no proration).
2. A blank or whitespace-only `end_date` means the subscription is ongoing.
3. A churn event is attributed to the month of the subscription's `end_date`,
   not the month when the window expires.
4. The 30-day re-subscribe window uses calendar days (`timedelta(days=30)`),
   not "one calendar month."
5. "3 calendar months after signup" uses `dateutil.relativedelta` — e.g.
   Jan 31 + 3 months = Apr 30 (not May 1).
6. Subscriptions belonging to `customer_id` values absent from `customers.csv`
   (e.g. C999, C050) are included in MRR and churn but excluded from cohort
   retention (which is customer-driven).
7. For overlapping subscriptions the earlier-starting row is always kept, even
   if the later one has a higher price or longer duration.
8. Customers with invalid `signup_date` are excluded from cohort retention but
   their subscriptions still count toward MRR and churn.

---

## Trade-offs

| Decision | Rationale |
|---|---|
| No proration in MRR | Simpler and consistent with how SaaS MRR is usually reported at the plan level; proration would require daily-rate logic and is not specified |
| All months shown in MRR and churn output (including zero-churn months) | Easier for consumers to join/compare metrics without gaps in the time series |
| Metric classes rather than functions | Enables the registry pattern in `main.py`; trivial to extend |
| Loader performs all cleaning up-front | Metrics stay simple and testable with plain DataFrames; data quality concerns do not leak into business logic |
| Warning-and-skip for bad rows | Fail-fast on every bad row would halt the whole report; skip-and-warn keeps the report useful while surfacing issues |

---

## Running the Project

```bash
# Install dependencies
pip install -r requirements.txt

# Run the report
python main.py customers.csv subscriptions.csv output.json

# Run tests
pytest tests/
```