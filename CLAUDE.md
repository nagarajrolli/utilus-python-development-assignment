# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run all tests
pytest tests/

# Run a single test file
pytest tests/test_mrr.py

# Run a single test by name
pytest tests/test_churn.py::TestMonthlyChurn::test_ended_subscription_with_no_resubscription_is_churn

# Run the metrics report
python main.py data/raw/customers.csv data/raw/subscriptions.csv data/output/report.json

# Format code (rewrites files)
./scripts/lint.sh format

# Lint only (no changes)
./scripts/lint.sh lint

# Format + lint
./scripts/lint.sh all
```

## Architecture

### Data flow

```
CSV files → data/loader.py → clean DataFrames → metrics/*.py → list[dict] → main.py → JSON
```

All data quality cleaning happens in `loader.py` before any metric sees the data. Metrics receive clean DataFrames and contain no defensive checks.

### Adding a metric

1. Create `metrics/my_metric.py` subclassing `BaseMetric` with a `key: str` and `compute(customers, subscriptions) -> list[dict]`.
2. Append `MyMetric()` to `_METRICS` in `main.py`.
3. Add tests in `tests/test_my_metric.py`.

No other files change.

### Key design decisions

- **Loader is the single quality gate.** Bad rows are skipped with a `WARNING` to stderr; the report is always produced for valid rows. Validation of required columns raises `ValueError`, surfaced as `click.UsageError`.
- **Metrics are stateless classes.** Each holds only a `key` and a `compute` method. The `_METRICS` list in `main.py` is the sole registration point.
- **Churn window** is `(end_date, end_date + 30 days]` — strictly after end_date, 30th day inclusive, using `timedelta(days=30)`.
- **Cohort retention** check date is per-customer: `signup_date + 3 calendar months` via `dateutil.relativedelta`.
- **Overlapping subscriptions** (same customer): earlier-starting row kept, later dropped. This can cause false churn events for affected customers.

### Test helpers

`tests/conftest.py` exports two plain functions (not fixtures) — `make_customers(rows)` and `make_subscriptions(rows)` — imported explicitly by each test file. The `no_customers` and `no_subscriptions` fixtures are auto-available via conftest.