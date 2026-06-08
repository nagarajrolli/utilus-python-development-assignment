import json
import logging
import sys

import click

from data.loader import load_customers, load_subscriptions, warn_unknown_customers
from metrics.churn import MonthlyChurnMetric
from metrics.cohort_retention import CohortRetentionMetric
from metrics.mrr import MonthlyMRRMetric

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s", stream=sys.stderr)

_METRICS = [
    MonthlyMRRMetric(),
    MonthlyChurnMetric(),
    CohortRetentionMetric(),
]


@click.command()
@click.argument("customers_file", type=click.Path(exists=True))
@click.argument("subscriptions_file", type=click.Path(exists=True))
@click.argument("output_file", type=click.Path())
def main(customers_file: str, subscriptions_file: str, output_file: str) -> None:
    """Compute subscription metrics and write a JSON report to OUTPUT_FILE."""
    try:
        customers = load_customers(customers_file)
        subscriptions = load_subscriptions(subscriptions_file)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc

    warn_unknown_customers(customers, subscriptions)

    report = {metric.key: metric.compute(customers, subscriptions) for metric in _METRICS}

    with open(output_file, "w") as fh:
        json.dump(report, fh, indent=2)

    click.echo(f"Report written to {output_file}")


if __name__ == "__main__":
    main()