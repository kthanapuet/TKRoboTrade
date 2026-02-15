from abc import ABC, abstractmethod
import pandas as pd


class BaseStrategy(ABC):
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def generate_signals(
        self, df: pd.DataFrame, current_cost: float = 0.0
    ) -> pd.DataFrame:
        pass
