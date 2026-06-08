import pandas as pd
import pytest


def make_customers(rows: list[tuple]) -> pd.DataFrame:
    """rows: [(customer_id, signup_date_str, country), ...]"""
    return pd.DataFrame(
        [
            {
                "customer_id": cid,
                "signup_date": pd.Timestamp(signup),
                "country": country,
            }
            for cid, signup, country in rows
        ]
    )


def make_subscriptions(rows: list[tuple]) -> pd.DataFrame:
    """rows: [(customer_id, start_date_str, end_date_str_or_None, monthly_price), ...]"""
    return pd.DataFrame(
        [
            {
                "customer_id": cid,
                "start_date": pd.Timestamp(start),
                "end_date": pd.Timestamp(end) if end else pd.NaT,
                "plan": "basic",
                "monthly_price": float(price),
            }
            for cid, start, end, price in rows
        ]
    )


@pytest.fixture
def no_customers() -> pd.DataFrame:
    return pd.DataFrame(columns=["customer_id", "signup_date", "country"])


@pytest.fixture
def no_subscriptions() -> pd.DataFrame:
    return pd.DataFrame(
        columns=["customer_id", "start_date", "end_date", "plan", "monthly_price"]
    )
