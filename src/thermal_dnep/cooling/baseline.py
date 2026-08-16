import pandas as pd
import numpy as np

from sklearn.ensemble import RandomForestRegressor


BASELINE_FEATURES = [
    "HourSin",
    "HourCos",
]


def estimate_baseline(
    df: pd.DataFrame,
) -> pd.DataFrame:

    result = df.copy()

    result["BaselineLoad"] = np.nan

    for feeder_code, group in result.groupby(
        "ToolPGDSCode"
    ):

        group = group.sort_values(
            "Timestamp"
        )

        # -----------------------------------------------------
        # Identify relatively cool observations
        # -----------------------------------------------------

        temperature_limit = group[
            "Temperature"
        ].quantile(0.30)

        baseline_data = group[
            group["Temperature"]
            <= temperature_limit
        ].copy()

        # -----------------------------------------------------
        # Baseline model
        # -----------------------------------------------------

        model = RandomForestRegressor(
            n_estimators=200,
            max_depth=10,
            min_samples_leaf=10,
            random_state=42,
            n_jobs=-1,
        )

        X = baseline_data[
            BASELINE_FEATURES
        ]

        y = baseline_data["Load"]

        model.fit(X, y)

        X_all = group[
            BASELINE_FEATURES
        ]

        predicted = model.predict(
            X_all
        )

        result.loc[
            group.index,
            "BaselineLoad",
        ] = predicted

    # ---------------------------------------------------------
    # Cooling load
    # ---------------------------------------------------------

    result["CoolingLoad"] = np.maximum(
        result["Load"]
        - result["BaselineLoad"],
        0,
    )

    return result