import pandas as pd
import pytest

from data.loader import load_customers, load_subscriptions, warn_unknown_customers


def _csv(tmp_path, name: str, content: str) -> str:
    p = tmp_path / name
    p.write_text(content)
    return str(p)


# ---------------------------------------------------------------------------
# load_customers
# ---------------------------------------------------------------------------


class TestLoadCustomers:
    def test_basic_load(self, tmp_path):
        path = _csv(tmp_path, "c.csv", "customer_id,signup_date,country\nC001,2024-01-01,NL\n")
        df = load_customers(path)
        assert len(df) == 1
        assert df.iloc[0]["customer_id"] == "C001"
        assert df.iloc[0]["signup_date"] == pd.Timestamp("2024-01-01")

    def test_invalid_signup_date_is_skipped(self, tmp_path):
        path = _csv(
            tmp_path,
            "c.csv",
            "customer_id,signup_date,country\nC001,not-a-date,NL\nC002,2024-01-01,DE\n",
        )
        df = load_customers(path)
        assert len(df) == 1
        assert df.iloc[0]["customer_id"] == "C002"

    def test_invalid_month_in_date_is_skipped(self, tmp_path):
        # month 13 does not exist
        path = _csv(
            tmp_path,
            "c.csv",
            "customer_id,signup_date,country\nC001,2024-13-05,NL\nC002,2024-01-01,DE\n",
        )
        df = load_customers(path)
        assert len(df) == 1
        assert df.iloc[0]["customer_id"] == "C002"

    def test_duplicate_customer_id_keeps_earliest(self, tmp_path):
        path = _csv(
            tmp_path,
            "c.csv",
            "customer_id,signup_date,country\nC001,2024-03-01,NL\nC001,2024-01-01,DE\n",
        )
        df = load_customers(path)
        assert len(df) == 1
        assert df.iloc[0]["signup_date"] == pd.Timestamp("2024-01-01")
        assert df.iloc[0]["country"] == "DE"

    def test_country_normalised_to_uppercase(self, tmp_path):
        path = _csv(tmp_path, "c.csv", "customer_id,signup_date,country\nC001,2024-01-01,nl\n")
        df = load_customers(path)
        assert df.iloc[0]["country"] == "NL"

    def test_whitespace_stripped(self, tmp_path):
        path = _csv(
            tmp_path, "c.csv", "customer_id,signup_date,country\n C001 , 2024-01-01 , NL \n"
        )
        df = load_customers(path)
        assert df.iloc[0]["customer_id"] == "C001"
        assert df.iloc[0]["country"] == "NL"

    def test_missing_country_row_is_kept(self, tmp_path):
        path = _csv(tmp_path, "c.csv", "customer_id,signup_date,country\nC001,2024-01-01,\n")
        df = load_customers(path)
        assert len(df) == 1


# ---------------------------------------------------------------------------
# load_subscriptions
# ---------------------------------------------------------------------------


class TestLoadSubscriptions:
    def test_basic_load(self, tmp_path):
        path = _csv(
            tmp_path,
            "s.csv",
            "customer_id,start_date,end_date,plan,monthly_price\nC001,2024-01-01,,basic,30\n",
        )
        df = load_subscriptions(path)
        assert len(df) == 1
        assert pd.isna(df.iloc[0]["end_date"])
        assert df.iloc[0]["monthly_price"] == 30.0

    def test_blank_end_date_becomes_nat(self, tmp_path):
        path = _csv(
            tmp_path,
            "s.csv",
            "customer_id,start_date,end_date,plan,monthly_price\nC001,2024-01-01, ,basic,30\n",
        )
        df = load_subscriptions(path)
        assert pd.isna(df.iloc[0]["end_date"])

    def test_invalid_start_date_skipped(self, tmp_path):
        path = _csv(
            tmp_path,
            "s.csv",
            "customer_id,start_date,end_date,plan,monthly_price\n"
            "C001,bad-date,,basic,30\n"
            "C002,2024-01-01,,basic,25\n",
        )
        df = load_subscriptions(path)
        assert len(df) == 1
        assert df.iloc[0]["customer_id"] == "C002"

    def test_invalid_end_date_skipped(self, tmp_path):
        # Feb 30 does not exist
        path = _csv(
            tmp_path,
            "s.csv",
            "customer_id,start_date,end_date,plan,monthly_price\n"
            "C001,2024-01-01,2024-02-30,basic,30\n"
            "C002,2024-01-01,,basic,25\n",
        )
        df = load_subscriptions(path)
        assert len(df) == 1
        assert df.iloc[0]["customer_id"] == "C002"

    def test_non_numeric_price_skipped(self, tmp_path):
        path = _csv(
            tmp_path,
            "s.csv",
            "customer_id,start_date,end_date,plan,monthly_price\n"
            'C001,2024-01-01,,basic,"thirty"\n'
            "C002,2024-01-01,,basic,25\n",
        )
        df = load_subscriptions(path)
        assert len(df) == 1
        assert df.iloc[0]["customer_id"] == "C002"

    def test_end_before_start_skipped(self, tmp_path):
        path = _csv(
            tmp_path,
            "s.csv",
            "customer_id,start_date,end_date,plan,monthly_price\n"
            "C001,2024-09-29,2024-08-20,basic,20\n"
            "C002,2024-01-01,,basic,25\n",
        )
        df = load_subscriptions(path)
        assert len(df) == 1
        assert df.iloc[0]["customer_id"] == "C002"

    def test_whitespace_in_dates_stripped(self, tmp_path):
        path = _csv(
            tmp_path,
            "s.csv",
            "customer_id,start_date,end_date,plan,monthly_price\n"
            'C001," 2024-01-01 "," 2024-03-01 ",basic,30\n',
        )
        df = load_subscriptions(path)
        assert df.iloc[0]["start_date"] == pd.Timestamp("2024-01-01")
        assert df.iloc[0]["end_date"] == pd.Timestamp("2024-03-01")

    def test_overlapping_keeps_earlier(self, tmp_path):
        path = _csv(
            tmp_path,
            "s.csv",
            "customer_id,start_date,end_date,plan,monthly_price\n"
            "C001,2024-01-01,2024-04-01,basic,30\n"
            "C001,2024-02-01,2024-05-01,basic,30\n",
        )
        df = load_subscriptions(path)
        assert len(df) == 1
        assert df.iloc[0]["start_date"] == pd.Timestamp("2024-01-01")
        assert df.iloc[0]["end_date"] == pd.Timestamp("2024-04-01")

    def test_non_overlapping_keeps_both(self, tmp_path):
        path = _csv(
            tmp_path,
            "s.csv",
            "customer_id,start_date,end_date,plan,monthly_price\n"
            "C001,2024-01-01,2024-03-01,basic,30\n"
            "C001,2024-04-01,,basic,30\n",
        )
        df = load_subscriptions(path)
        assert len(df) == 2

    def test_open_subscription_blocks_subsequent(self, tmp_path):
        path = _csv(
            tmp_path,
            "s.csv",
            "customer_id,start_date,end_date,plan,monthly_price\n"
            "C001,2024-01-01,,basic,30\n"
            "C001,2024-03-01,,basic,30\n",
        )
        df = load_subscriptions(path)
        assert len(df) == 1
        assert df.iloc[0]["start_date"] == pd.Timestamp("2024-01-01")


# ---------------------------------------------------------------------------
# Column validation
# ---------------------------------------------------------------------------


class TestColumnValidation:
    def test_customers_missing_column_raises(self, tmp_path):
        path = _csv(tmp_path, "c.csv", "customer_id,country\nC001,NL\n")
        with pytest.raises(ValueError, match="signup_date"):
            load_customers(path)

    def test_customers_missing_multiple_columns_raises(self, tmp_path):
        path = _csv(tmp_path, "c.csv", "customer_id\nC001\n")
        with pytest.raises(ValueError, match="missing required column"):
            load_customers(path)

    def test_subscriptions_missing_column_raises(self, tmp_path):
        path = _csv(
            tmp_path,
            "s.csv",
            "customer_id,start_date,end_date,plan\nC001,2024-01-01,,basic\n",
        )
        with pytest.raises(ValueError, match="monthly_price"):
            load_subscriptions(path)

    def test_customers_all_columns_present_does_not_raise(self, tmp_path):
        path = _csv(tmp_path, "c.csv", "customer_id,signup_date,country\nC001,2024-01-01,NL\n")
        load_customers(path)  # should not raise

    def test_subscriptions_all_columns_present_does_not_raise(self, tmp_path):
        path = _csv(
            tmp_path,
            "s.csv",
            "customer_id,start_date,end_date,plan,monthly_price\nC001,2024-01-01,,basic,30\n",
        )
        load_subscriptions(path)  # should not raise


# ---------------------------------------------------------------------------
# Unknown customer_id warning
# ---------------------------------------------------------------------------


class TestUnknownCustomerWarning:
    def test_unknown_customer_id_is_warned(self, caplog):
        import logging

        customers = pd.DataFrame(
            [{"customer_id": "C001", "signup_date": pd.Timestamp("2024-01-01"), "country": "NL"}]
        )
        subscriptions = pd.DataFrame(
            [
                {
                    "customer_id": "C999",
                    "start_date": pd.Timestamp("2024-01-01"),
                    "end_date": pd.NaT,
                    "plan": "basic",
                    "monthly_price": 25.0,
                }
            ]
        )
        with caplog.at_level(logging.WARNING, logger="data.loader"):
            warn_unknown_customers(customers, subscriptions)
        assert any("C999" in msg for msg in caplog.messages)

    def test_known_customer_id_produces_no_warning(self, caplog):
        import logging

        customers = pd.DataFrame(
            [{"customer_id": "C001", "signup_date": pd.Timestamp("2024-01-01"), "country": "NL"}]
        )
        subscriptions = pd.DataFrame(
            [
                {
                    "customer_id": "C001",
                    "start_date": pd.Timestamp("2024-01-01"),
                    "end_date": pd.NaT,
                    "plan": "basic",
                    "monthly_price": 30.0,
                }
            ]
        )
        with caplog.at_level(logging.WARNING, logger="data.loader"):
            warn_unknown_customers(customers, subscriptions)
        assert not any("not found in customers" in msg for msg in caplog.messages)