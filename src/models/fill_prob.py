"""
fill probability model for predicting order fill likelihood

this module provides:
1. feature extraction from order book state
2. logistic regression model for fill prediction
3. model training and evaluation
4. model persistence and loading
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import List

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from features.imbalance import get_imbalance_features

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class FillFeatures:
    """features used for fill prediction"""

    # order book features
    bid_ask_spread: float
    mid_price: float
    bid_volume: float
    ask_volume: float
    imbalance_1: float
    imbalance_2: float
    imbalance_5: float

    # order features
    price_distance: float  # distance from mid price
    size: float  # order size
    side: str  # buy or sell

    def to_array(self) -> np.ndarray:
        """convert features to numpy array for model input"""
        return np.array(
            [
                self.bid_ask_spread,
                self.mid_price,
                self.bid_volume,
                self.ask_volume,
                self.imbalance_1,
                self.imbalance_2,
                self.imbalance_5,
                self.price_distance,
                self.size,
                1.0 if self.side == "buy" else 0.0,
            ]
        )


class FillProbabilityModel:
    """logistic regression model for fill prediction

    this class handles:
    - feature extraction from order book state
    - model training and evaluation
    - fill probability prediction
    - model persistence and loading

    attributes:
        model: trained logistic regression model
        scaler: feature scaler
        model_path: path to save/load model
    """

    def __init__(self, model_path: str = "data/models/fill_prob.joblib"):
        """initialize model

        args:
            model_path: path to save/load model
        """
        self.model = None
        self.scaler = StandardScaler()
        self.model_path = Path(model_path)
        self.model_path.parent.mkdir(parents=True, exist_ok=True)

    def extract_features(
        self,
        bids: List[List[str]],
        asks: List[List[str]],
        order_price: Decimal,
        order_size: Decimal,
        order_side: str,
    ) -> FillFeatures:
        """extract features from order book state and order

        args:
            bids: list of [price, quantity] pairs, sorted descending
            asks: list of [price, quantity] pairs, sorted ascending
            order_price: price of order
            order_size: size of order
            order_side: side of order (buy or sell)

        returns:
            FillFeatures instance
        """
        # get best bid and ask
        best_bid = Decimal(bids[0][0]) if bids else Decimal("0")
        best_ask = Decimal(asks[0][0]) if asks else Decimal("0")
        mid_price = (best_bid + best_ask) / Decimal("2")

        # calculate spread
        spread = float(best_ask - best_bid) / float(mid_price)

        # calculate volumes
        bid_volume = sum(Decimal(qty) for _, qty in bids)
        ask_volume = sum(Decimal(qty) for _, qty in asks)

        # get imbalance features
        imbalance_features = get_imbalance_features(bids, asks)

        # calculate price distance from mid
        price_distance = float(abs(order_price - mid_price)) / float(mid_price)

        return FillFeatures(
            bid_ask_spread=spread,
            mid_price=float(mid_price),
            bid_volume=float(bid_volume),
            ask_volume=float(ask_volume),
            imbalance_1=imbalance_features["imbalance_1"],
            imbalance_2=imbalance_features["imbalance_2"],
            imbalance_5=imbalance_features["imbalance_5"],
            price_distance=price_distance,
            size=float(order_size),
            side=order_side,
        )

    def train(
        self,
        fills_df: pd.DataFrame,
        test_size: float = 0.2,
        random_state: int = 42,
    ) -> float:
        """train model on backtest fill data

        args:
            fills_df: dataframe with fill data
            test_size: proportion of data to use for testing
            random_state: random seed for reproducibility

        returns:
            auc score on test set
        """
        # extract features and labels
        X = []
        y = []

        for _, row in fills_df.iterrows():
            features = self.extract_features(
                row["bids"],
                row["asks"],
                Decimal(str(row["price"])),
                Decimal(str(row["size"])),
                row["side"],
            )
            X.append(features.to_array())
            y.append(1)  # filled order

            # add negative examples (unfilled orders)
            # sample from a range of prices around the mid price
            mid_price = Decimal(str(row["price"]))
            spread = Decimal("0.01")  # 1% spread
            for _ in range(5):  # generate 5 negative examples per fill
                if row["side"] == "buy":
                    worse_price = mid_price - spread * Decimal(
                        str(np.random.uniform(0.5, 1.5))
                    )
                else:
                    worse_price = mid_price + spread * Decimal(
                        str(np.random.uniform(0.5, 1.5))
                    )

                features = self.extract_features(
                    row["bids"],
                    row["asks"],
                    worse_price,
                    Decimal(str(row["size"])),
                    row["side"],
                )
                X.append(features.to_array())
                y.append(0)  # unfilled order

        X = np.array(X)
        y = np.array(y)

        # split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state
        )

        # scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # train model
        self.model = LogisticRegression(random_state=random_state)
        self.model.fit(X_train_scaled, y_train)

        # evaluate
        y_pred = self.model.predict_proba(X_test_scaled)[:, 1]
        auc = roc_auc_score(y_test, y_pred)

        logger.info(f"trained fill probability model with auc: {auc:.3f}")

        return auc

    def predict(
        self,
        bids: List[List[str]],
        asks: List[List[str]],
        order_price: Decimal,
        order_size: Decimal,
        order_side: str,
    ) -> float:
        """predict fill probability for an order

        args:
            bids: list of [price, quantity] pairs, sorted descending
            asks: list of [price, quantity] pairs, sorted ascending
            order_price: price of order
            order_size: size of order
            order_side: side of order (buy or sell)

        returns:
            predicted fill probability between 0 and 1
        """
        if self.model is None:
            raise RuntimeError("model not trained")

        features = self.extract_features(
            bids, asks, order_price, order_size, order_side
        )
        X = features.to_array().reshape(1, -1)
        X_scaled = self.scaler.transform(X)
        return float(self.model.predict_proba(X_scaled)[0, 1])

    def save(self) -> None:
        """save model and scaler to disk"""
        if self.model is None:
            raise RuntimeError("model not trained")

        joblib.dump({"model": self.model, "scaler": self.scaler}, self.model_path)
        logger.info(f"saved model to {self.model_path}")

    def load(self) -> None:
        """load model and scaler from disk"""
        if not self.model_path.exists():
            raise FileNotFoundError(f"model not found at {self.model_path}")

        saved = joblib.load(self.model_path)
        self.model = saved["model"]
        self.scaler = saved["scaler"]
        logger.info(f"loaded model from {self.model_path}")
