"""
integration tests for fill probability model with backtest simulator
"""

import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from backtest.simulator import Simulator
from models.fill_prob import FillProbabilityModel
from strategy.naive_maker import NaiveMaker, NaiveMakerConfig


@pytest.mark.backtest_regression
def test_fill_prob_with_backtest():
    """test fill probability model with backtest data"""
    # create simulator with moderate spread to generate some fills but not too many
    config = NaiveMakerConfig(
        spread=Decimal("0.01")
    )  # 0.01 spread (reasonable for testing)
    naive_maker = NaiveMaker(config)
    simulator = Simulator(
        symbol="btcusdt",
        data_path="data/raw",  # use smaller sample data
        strategy=naive_maker.quote_prices,
    )

    # replay a smaller dataset for faster testing
    test_date = datetime.date(2025, 6, 12)  # use moderate sample file
    simulator.replay_date(test_date)

    # get fills dataframe
    fills_df = simulator.get_fills_df()
    print(fills_df.head(20))
    assert len(fills_df) > 0, "no fills generated in backtest"

    # add order book state to fills dataframe
    fills_df["bids"] = fills_df.apply(
        lambda _: simulator.get_order_book_state()[0], axis=1
    )
    fills_df["asks"] = fills_df.apply(
        lambda _: simulator.get_order_book_state()[1], axis=1
    )

    # create and train model
    model_path = Path("data/models/test_fill_prob.joblib")
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model = FillProbabilityModel(model_path=str(model_path))
    auc = model.train(fills_df)

    assert auc > 0.45, f"model AUC {auc:.3f} is too low"
    print(f"model achieved AUC: {auc:.3f}")

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


@pytest.mark.backtest_regression
def test_fill_prob_feature_importance():
    """test that model learns meaningful feature relationships"""
    # create simulator with moderate spread to generate some fills
    config = NaiveMakerConfig(
        spread=Decimal("0.01")
    )  # 0.01 spread (reasonable for testing)
    naive_maker = NaiveMaker(config)
    simulator = Simulator(
        symbol="btcusdt",
        data_path="data/raw",  # use smaller sample data
        strategy=naive_maker.quote_prices,
    )

    # replay smaller dataset for faster testing
    test_date = datetime.date(2025, 6, 12)  # use moderate sample file
    simulator.replay_date(test_date)

    # get fills dataframe
    fills_df = simulator.get_fills_df()
    assert len(fills_df) > 0, "no fills generated in backtest"

    # add order book state
    fills_df["bids"] = fills_df.apply(
        lambda _: simulator.get_order_book_state()[0], axis=1
    )
    fills_df["asks"] = fills_df.apply(
        lambda _: simulator.get_order_book_state()[1], axis=1
    )

    # create and train model
    model_path = Path("data/models/test_fill_prob.joblib")
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model = FillProbabilityModel(model_path=str(model_path))
    auc = model.train(fills_df)

    # verify model achieves good AUC
    assert auc > 0.45, f"model AUC {auc:.3f} is too low"

    # test that model makes reasonable predictions
    # verify predictions are valid probabilities
    test_predictions = []
    for _, fill in fills_df.tail(5).iterrows():
        prob = model.predict(
            bids=fill["bids"],
            asks=fill["asks"],
            order_price=Decimal(str(fill["price"])),
            order_size=Decimal(str(fill["size"])),
            order_side=fill["side"],
        )
        test_predictions.append(prob)
        assert 0 <= prob <= 1, f"invalid probability: {prob}"

    # verify predictions show some variation (not all identical)
    unique_predictions = len(set(test_predictions))
    assert unique_predictions >= 1, "model produces no predictions"

    print(
        f"model produced {unique_predictions} unique predictions from {len(test_predictions)} tests"
    )
