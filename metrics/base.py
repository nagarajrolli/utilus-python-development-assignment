from abc import ABC, abstractmethod

import pandas as pd


class BaseMetric(ABC):
    @property
    @abstractmethod
    def key(self) -> str:
        """Top-level key used for this metric in the JSON report."""

    @abstractmethod
    def compute(
        self, customers: pd.DataFrame, subscriptions: pd.DataFrame
    ) -> list[dict]:
        """Return a list of result records for this metric."""
