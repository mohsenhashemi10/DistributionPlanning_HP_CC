import pandas as pd

from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)


MODEL_FEATURES = [
    "Temperature",
    "TemperatureSquared",
    "RelativeHumidity",
    "HumiditySquared",
    "SolarRadiation",
    "SolarLog",
    "CDD",
    "CDDSquared",
    "HourSin",
    "HourCos",
]


def train_cooling_model(
    df: pd.DataFrame,
):

    models = {}
    predictions = []
    metrics = []

    for feeder_code, group in df.groupby(
        "ToolPGDSCode"
    ):

        group = group.sort_values(
            "Timestamp"
        ).copy()

        # -----------------------------------------------------
        # Remove zero cooling observations from training
        # -----------------------------------------------------

        train_data = group[
            group["CoolingLoad"] > 0
        ].copy()

        if len(train_data) < 100:

            print(
                f"WARNING: insufficient cooling "
                f"observations for {feeder_code}"
            )

            continue

        X = train_data[
            MODEL_FEATURES
        ]

        y = train_data[
            "CoolingLoad"
        ]

        # -----------------------------------------------------
        # Chronological split
        # -----------------------------------------------------

        split = int(
            len(train_data) * 0.8
        )

        X_train = X.iloc[:split]
        X_test = X.iloc[split:]

        y_train = y.iloc[:split]
        y_test = y.iloc[split:]

        # -----------------------------------------------------
        # Model
        # -----------------------------------------------------

        model = RandomForestRegressor(
            n_estimators=300,
            max_depth=15,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1,
        )

        model.fit(
            X_train,
            y_train,
        )

        prediction = model.predict(
            X_test
        )

        # -----------------------------------------------------
        # Metrics
        # -----------------------------------------------------

        mae = mean_absolute_error(
            y_test,
            prediction,
        )

        rmse = mean_squared_error(
            y_test,
            prediction,
        ) ** 0.5

        r2 = r2_score(
            y_test,
            prediction,
        )

        metrics.append(
            {
                "ToolPGDSCode": feeder_code,
                "MAE": mae,
                "RMSE": rmse,
                "R2": r2,
                "TestSamples": len(y_test),
            }
        )

        models[
            feeder_code
        ] = model

        test_data = train_data.iloc[
            split:
        ].copy()

        test_data[
            "PredictedCoolingLoad"
        ] = prediction

        predictions.append(
            test_data
        )

    metrics_df = pd.DataFrame(
        metrics
    )

    if predictions:
        predictions_df = pd.concat(
            predictions,
            ignore_index=True,
        )
    else:
        predictions_df = pd.DataFrame()

    return (
        models,
        metrics_df,
        predictions_df,
    )