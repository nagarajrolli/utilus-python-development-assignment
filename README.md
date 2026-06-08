# Subscription Metrics

A CLI tool that reads customer and subscription CSV files and produces a JSON report with three SaaS business metrics.

## Metrics

| Metric | Key in report | Description |
|---|---|---|
| Monthly MRR | `monthly_mrr` | Sum of `monthly_price` for all active subscriptions per calendar month |
| Monthly churn | `monthly_churn` | Customers whose subscription ended with no re-subscription within 30 days |
| Cohort retention (3m) | `cohort_retention_3m` | % of customers still active 3 months after their signup date, grouped by signup month |

## Project Structure

```
.
├── main.py                  # CLI entry point
├── data/
│   ├── loader.py            # CSV loading and data quality cleaning
│   ├── raw/                 # Source CSV files
│   │   ├── customers.csv
│   │   └── subscriptions.csv
│   └── output/              # Generated reports (git-ignored)
├── metrics/
│   ├── base.py              # BaseMetric interface
│   ├── mrr.py
│   ├── churn.py
│   └── cohort_retention.py
├── tests/
├── DESIGN.md                # Architecture, business rules, assumptions
└── requirements.txt
```

## Installation

Requires Python 3.11+.

```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
python main.py <customers_file> <subscriptions_file> <output_file>
```

**Example:**

```bash
python main.py data/raw/customers.csv data/raw/subscriptions.csv data/output/report.json
```

Data quality warnings (invalid dates, unknown customer IDs, etc.) are printed to stderr. The report is always written for the rows that could be parsed successfully.

## Input Format

### customers.csv

| Column | Type | Notes |
|---|---|---|
| `customer_id` | string | Primary identifier |
| `signup_date` | date | Date the customer first joined |
| `country` | string | ISO country code |

### subscriptions.csv

| Column | Type | Notes |
|---|---|---|
| `customer_id` | string | Foreign key to customers |
| `start_date` | date | First day the subscription was active |
| `end_date` | date | Last day active; blank means still active |
| `plan` | string | Plan name (e.g. `basic`, `pro`) |
| `monthly_price` | numeric | Price charged per month |

## Data Quality Handling

All issues are logged as warnings to stderr. The affected row is skipped and the report is produced from the remaining valid data.

### customers.csv

| Issue | Handling |
|---|---|
| Unparseable `signup_date` | Row skipped |
| Duplicate `customer_id` | Earlier `signup_date` kept; later record dropped |
| `country` in lowercase | Normalised to uppercase |
| Missing `country` | Row kept — country is not used by any current metric |

### subscriptions.csv

| Issue | Handling |
|---|---|
| Unparseable `start_date` | Row skipped |
| Blank / whitespace-only `end_date` | Treated as null — subscription still active |
| Non-blank unparseable `end_date` | Row skipped |
| Non-numeric `monthly_price` | Row skipped |
| `end_date` before `start_date` | Row skipped |
| Overlapping subscriptions (same customer) | Earlier-starting row kept; later one dropped |
| `customer_id` absent from customers.csv | Included in MRR/churn; excluded from cohort retention |

## Output Format

```json
{
  "monthly_mrr": [
    { "month": "2024-01", "mrr": 85.0 },
    { "month": "2024-02", "mrr": 135.0 }
  ],
  "monthly_churn": [
    { "month": "2024-01", "churned_customers": 0 },
    { "month": "2024-02", "churned_customers": 1 }
  ],
  "cohort_retention_3m": [
    {
      "cohort_month": "2024-01",
      "cohort_size": 3,
      "active_after_3_months": 2,
      "retention_rate_3m": 0.6667
    }
  ]
}
```

## Running Tests

```bash
pytest tests/
```

## Design

See [DESIGN.md](DESIGN.md) for the architecture, business rules, how to add a metric, and known trade-offs.