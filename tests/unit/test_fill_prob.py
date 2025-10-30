"""
unit tests for fill probability model
"""

from decimal import Decimal

from models.fill_prob import FillFeatures, FillProbabilityModel


def test_feature_extraction():
    """test feature extraction from order book state"""
    # sample order book state
    bids = [
        ["100.0", "1.0"],
        ["99.0", "2.0"],
        ["98.0", "3.0"],
    ]
    asks = [
        ["101.0", "1.0"],
        ["102.0", "2.0"],
        ["103.0", "3.0"],
    ]

    # model
    model = FillProbabilityModel()

    # extract features for buy order
    features = model.extract_features(
        bids=bids,
        asks=asks,
        order_price=Decimal("100.0"),
        order_size=Decimal("1.0"),
        order_side="buy",
    )

    # verify features
    assert isinstance(features, FillFeatures)
    # spread = (ask - bid) / mid_price = (101 - 100) / 100.5 ≈ 0.00995
    assert abs(features.bid_ask_spread - 0.00995) < 0.0001
    assert features.mid_price == 100.5  # (100 + 101) / 2
    assert features.bid_volume == 6.0  # 1 + 2 + 3
    assert features.ask_volume == 6.0  # 1 + 2 + 3
    assert abs(features.price_distance - 0.004975) < 0.0001  # |100 - 100.5| / 100.5
    assert features.size == 1.0
    assert features.side == "buy"

    # verify imbalance features
    assert -1 <= features.imbalance_1 <= 1
    assert -1 <= features.imbalance_2 <= 1
    assert -1 <= features.imbalance_5 <= 1


def test_model_training():
    """test model training and prediction"""
    import pandas as pd

    # sample training data
    data = []
    for i in range(100):
        mid_price = 100.0
        spread = 0.01
        data.append(
            {
                "bids": [[str(mid_price - spread / 2), "1.0"]],
                "asks": [[str(mid_price + spread / 2), "1.0"]],
                "price": str(mid_price),
                "size": "1.0",
                "side": "buy" if i % 2 == 0 else "sell",
            }
        )

    fills_df = pd.DataFrame(data)

    # and train model
    model = FillProbabilityModel()
    auc = model.train(fills_df)

    # verify training
    assert 0 <= auc <= 1
    assert model.model is not None

    # test prediction
    prob = model.predict(
        bids=[["100.0", "1.0"]],
        asks=[["101.0", "1.0"]],
        order_price=Decimal("100.0"),
        order_size=Decimal("1.0"),
        order_side="buy",
    )

    # verify prediction
    assert 0 <= prob <= 1


def test_model_persistence(tmp_path):
    """test model saving and loading"""
    import pandas as pd

    # sample training data
    data = []
    for i in range(100):
        mid_price = 100.0
        spread = 0.01
        data.append(
            {
                "bids": [[str(mid_price - spread / 2), "1.0"]],
                "asks": [[str(mid_price + spread / 2), "1.0"]],
                "price": str(mid_price),
                "size": "1.0",
                "side": "buy" if i % 2 == 0 else "sell",
            }
        )

    fills_df = pd.DataFrame(data)

    # and train model
    model = FillProbabilityModel(model_path=str(tmp_path / "model.joblib"))
    model.train(fills_df)

    # save model
    model.save()

    # new model and load
    model2 = FillProbabilityModel(model_path=str(tmp_path / "model.joblib"))
    model2.load()

    # verify loaded model
    assert model2.model is not None
    assert model2.scaler is not None

    # compare predictions
    prob1 = model.predict(
        bids=[["100.0", "1.0"]],
        asks=[["101.0", "1.0"]],
        order_price=Decimal("100.0"),
        order_size=Decimal("1.0"),
        order_side="buy",
    )

    prob2 = model2.predict(
        bids=[["100.0", "1.0"]],
        asks=[["101.0", "1.0"]],
        order_price=Decimal("100.0"),
        order_size=Decimal("1.0"),
        order_side="buy",
    )

    assert prob1 == prob2
