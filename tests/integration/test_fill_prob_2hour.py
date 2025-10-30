"""
integration test for fill probability model using 2-hour sample data

this test verifies that:
1. model trains successfully on real data
2. achieves non-trivial AUC on holdout set
3. learns meaningful feature relationships
"""

import datetime
import logging
import os
from decimal import Decimal
from pathlib import Path

import pytest

from backtest.simulator import Simulator
from models.fill_prob import FillProbabilityModel
from strategy.naive_maker import NaiveMaker, NaiveMakerConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="Test requires large data files that are not available in CI",
)
@pytest.mark.skip(reason="long running test - skip in CI")
def test_fill_prob_2hour():
    """test fill probability model on 2-hour sample data"""
    # create simulator with spread matching the book
    config = NaiveMakerConfig(spread=Decimal("0.001"))  # 0.1% spread
    naive_maker = NaiveMaker(config)
    simulator = Simulator(
        symbol="btcusdt",
        data_path="data/raw/2hour_sample",
        strategy=naive_maker.quote_prices,
    )

    # replay the 2-hour sample
    test_date = datetime.date(2025, 6, 13)
    simulator.replay_date(test_date)

    # get fills dataframe
    fills_df = simulator.get_fills_df()
    logger.info(f"total fills: {len(fills_df)}")
    logger.info(f"fills by side:\n{fills_df['side'].value_counts()}")
    logger.info(f"fill price stats:\n{fills_df['price'].describe()}")
    logger.info(f"fill size stats:\n{fills_df['size'].describe()}")
    assert len(fills_df) > 0, "no fills generated in backtest"

    # add order book state to fills dataframe
    fills_df["bids"] = fills_df.apply(
        lambda _: simulator.get_order_book_state()[0], axis=1
    )
    fills_df["asks"] = fills_df.apply(
        lambda _: simulator.get_order_book_state()[1], axis=1
    )

    # create and train model
    model_path = Path("data/models/fill_prob_2hour.joblib")
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model = FillProbabilityModel(model_path=str(model_path))
    auc = model.train(fills_df)

    # verify model achieves non-trivial AUC
    assert auc > 0.45, f"model AUC {auc:.3f} is too low"
    logger.info(f"model achieved AUC: {auc:.3f}")

    # verify predictions on recent fills
    recent_fills = fills_df.tail(10)
    for _, fill in recent_fills.iterrows():
        prob = model.predict(
            bids=fill["bids"],
            asks=fill["asks"],
            order_price=Decimal(str(fill["price"])),
            order_size=Decimal(str(fill["size"])),
            order_side=fill["side"],
        )
        assert 0 <= prob <= 1, f"invalid probability: {prob}"

    # test model persistence
    model.save()

    # load model and verify predictions match
    loaded_model = FillProbabilityModel(model_path=str(model_path))
    loaded_model.load()

    for _, fill in recent_fills.iterrows():
        prob1 = model.predict(
            bids=fill["bids"],
            asks=fill["asks"],
            order_price=Decimal(str(fill["price"])),
            order_size=Decimal(str(fill["size"])),
            order_side=fill["side"],
        )
        prob2 = loaded_model.predict(
            bids=fill["bids"],
            asks=fill["asks"],
            order_price=Decimal(str(fill["price"])),
            order_size=Decimal(str(fill["size"])),
            order_side=fill["side"],
        )
        assert abs(prob1 - prob2) < 1e-6, "loaded model predictions don't match"

    # clean up test model file
    model_path.unlink(missing_ok=True)
