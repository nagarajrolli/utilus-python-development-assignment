import logging

import pandas as pd

logger = logging.getLogger(__name__)

_CUSTOMERS_REQUIRED = {"customer_id", "signup_date", "country"}
_SUBSCRIPTIONS_REQUIRED = {"customer_id", "start_date", "end_date", "plan", "monthly_price"}


def _require_columns(df: pd.DataFrame, required: set[str], source: str) -> None:
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"{source}: missing required column(s): {', '.join(sorted(missing))}"
        )


def warn_unknown_customers(customers: pd.DataFrame, subscriptions: pd.DataFrame) -> None:
    """Log a warning for every subscription whose customer_id is absent from customers."""
    known = set(customers["customer_id"])
    unknown = set(subscriptions["customer_id"]) - known
    for cid in sorted(unknown):
        logger.warning(
            "subscriptions: customer_id %s not found in customers — "
            "included in MRR/churn, excluded from cohort retention",
            cid,
        )


def load_customers(path: str) -> pd.DataFrame:
    """
    Load and clean customers.csv.

    Cleaning applied:
    - Whitespace stripped from all string fields
    - country normalised to uppercase
    - Rows with unparseable signup_date are dropped (warning logged)
    - Duplicate customer_id: earliest signup_date is kept (warning logged)

    Raises ValueError if any required column is absent.
    """
    df = pd.read_csv(path, dtype=str)
    df.columns = df.columns.str.strip()
    _require_columns(df, _CUSTOMERS_REQUIRED, path)
    for col in df.select_dtypes(include="str").columns:
        df[col] = df[col].str.strip()

    df["country"] = df["country"].str.upper()

    df["signup_date"] = pd.to_datetime(df["signup_date"], format="mixed", errors="coerce")
    invalid = df[df["signup_date"].isna()]
    for _, row in invalid.iterrows():
        logger.warning("customers: skipping %s — unparseable signup_date", row["customer_id"])
    df = df[df["signup_date"].notna()].copy()

    duplicates = df[df.duplicated("customer_id", keep=False)]["customer_id"].unique()
    for cid in duplicates:
        logger.warning("customers: duplicate customer_id %s — keeping earliest record", cid)
    df = df.sort_values("signup_date").drop_duplicates(subset="customer_id", keep="first")

    return df.reset_index(drop=True)


def load_subscriptions(path: str) -> pd.DataFrame:
    """
    Load and clean subscriptions.csv.

    Cleaning applied:
    - Whitespace stripped from all string fields
    - start_date: rows with unparseable value dropped (warning logged)
    - end_date: blank/empty → NaT (subscription still active);
                non-blank unparseable → row dropped (warning logged)
    - monthly_price: non-numeric rows dropped (warning logged)
    - Rows where end_date < start_date dropped (warning logged)
    - Overlapping subscriptions per customer: earlier-starting row kept,
      later-starting overlapping row dropped (warning logged)

    Raises ValueError if any required column is absent.
    """
    df = pd.read_csv(path, dtype=str)
    df.columns = df.columns.str.strip()
    _require_columns(df, _SUBSCRIPTIONS_REQUIRED, path)
    for col in df.select_dtypes(include="str").columns:
        df[col] = df[col].str.strip()

    # --- start_date ---
    df["start_date"] = pd.to_datetime(df["start_date"], format="mixed", errors="coerce")
    bad_start = df[df["start_date"].isna()]
    for _, row in bad_start.iterrows():
        logger.warning(
            "subscriptions: skipping %s — unparseable start_date", row["customer_id"]
        )
    df = df[df["start_date"].notna()].copy()

    # --- end_date ---
    # Blank strings become NaT (still active); only non-blank failures are errors.
    raw_end = df["end_date"].fillna("").str.strip()
    is_blank = raw_end == ""
    df["end_date"] = pd.to_datetime(raw_end.where(~is_blank, other=pd.NaT), errors="coerce")
    bad_end = ~is_blank & df["end_date"].isna()
    for idx in df[bad_end].index:
        logger.warning(
            "subscriptions: skipping %s — unparseable end_date",
            df.at[idx, "customer_id"],
        )
    df = df[~bad_end].copy()

    # --- monthly_price ---
    df["monthly_price"] = pd.to_numeric(df["monthly_price"], errors="coerce")
    bad_price = df[df["monthly_price"].isna()]
    for _, row in bad_price.iterrows():
        logger.warning(
            "subscriptions: skipping %s — non-numeric monthly_price", row["customer_id"]
        )
    df = df[df["monthly_price"].notna()].copy()

    # --- end before start ---
    inverted = df["end_date"].notna() & (df["end_date"] < df["start_date"])
    for _, row in df[inverted].iterrows():
        logger.warning(
            "subscriptions: skipping %s — end_date is before start_date", row["customer_id"]
        )
    df = df[~inverted].copy()

    # --- overlapping subscriptions ---
    df = _drop_overlapping(df)

    return df.reset_index(drop=True)


def _drop_overlapping(df: pd.DataFrame) -> pd.DataFrame:
    """
    For each customer keep the earliest-starting subscription; drop any later
    subscription whose start_date falls before the previous kept subscription's
    end_date (or drop it entirely if the previous subscription is still open).
    """
    keep: list[int] = []

    for customer_id, group in df.groupby("customer_id", sort=False):
        sorted_group = group.sort_values("start_date")
        prev_end: pd.Timestamp | None = None
        prev_is_open: bool = False

        for idx, row in sorted_group.iterrows():
            overlaps = prev_is_open or (
                prev_end is not None and row["start_date"] < prev_end
            )
            if overlaps:
                logger.warning(
                    "subscriptions: dropping overlapping subscription for %s starting %s",
                    customer_id,
                    row["start_date"].date(),
                )
            else:
                keep.append(idx)
                prev_end = row["end_date"] if pd.notna(row["end_date"]) else None
                prev_is_open = pd.isna(row["end_date"])

    return df.loc[keep]