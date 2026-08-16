import pandas as pd
import matplotlib.pyplot as plt


def save_cooling_results(
    metrics: pd.DataFrame,
    predictions: pd.DataFrame,
    output_dir,
):

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    metrics.to_csv(
        output_dir / "cooling_metrics.csv",
        index=False,
    )

    predictions.to_parquet(
        output_dir
        / "cooling_predictions.parquet",
        index=False,
    )


def plot_cooling_example(
    predictions: pd.DataFrame,
    output_dir,
):

    if predictions.empty:
        return

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    feeder = (
        predictions["ToolPGDSCode"]
        .iloc[0]
    )

    data = predictions[
        predictions["ToolPGDSCode"]
        == feeder
    ].head(24 * 7)

    plt.figure(
        figsize=(12, 5)
    )

    plt.plot(
        data["Timestamp"],
        data["CoolingLoad"],
        label="Estimated Cooling Load",
    )

    plt.plot(
        data["Timestamp"],
        data["PredictedCoolingLoad"],
        label="ML Prediction",
    )

    plt.xlabel("Time")
    plt.ylabel("Cooling Load")
    plt.title(
        f"Cooling Load Estimation - {feeder}"
    )

    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()

    plt.savefig(
        output_dir
        / f"cooling_{feeder}.png",
        dpi=300,
    )

    plt.close()