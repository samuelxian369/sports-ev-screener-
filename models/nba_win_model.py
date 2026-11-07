
import pandas as pd
import numpy as np

from pathlib import Path

from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    log_loss
)


# --------------------------------
# FILE LOCATIONS
# --------------------------------

PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"


# --------------------------------
# LOAD HISTORICAL NBA DATA
# --------------------------------

def load_nba_data():

    csv_files = sorted(
        DATA_DIR.glob("*team-game-results.csv")
    )

    if not csv_files:
        raise FileNotFoundError(
            "No NBA CSV files found in the data folder."
        )

    frames = []

    for file in csv_files:

        frame = pd.read_csv(file)

        frame.columns = (
            frame.columns.str.strip().str.lower()
        )

        frames.append(frame)

    df = pd.concat(
        frames,
        ignore_index=True
    )

    required_columns = [
        "team",
        "game_date",
        "opponent",
        "home",
        "points",
        "opponent_points",
        "point_diff",
        "field_goal_pct",
        "three_point_pct",
        "rebounds",
        "assists",
        "turnovers",
        "off_rating_est",
        "def_rating_est"
    ]

    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing CSV columns: {missing}"
        )

    df["game_date"] = pd.to_datetime(
        df["game_date"],
        errors="coerce"
    )

    df["team"] = df["team"].astype(str).str.strip()
    df["opponent"] = (
        df["opponent"].astype(str).str.strip()
    )

    numeric_columns = [
        "points",
        "opponent_points",
        "point_diff",
        "field_goal_pct",
        "three_point_pct",
        "rebounds",
        "assists",
        "turnovers",
        "off_rating_est",
        "def_rating_est"
    ]

    for column in numeric_columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    df = df.dropna(
        subset=[
            "game_date",
            "team",
            "opponent",
            "points",
            "opponent_points"
        ]
    )

    # Convert home/away information into numbers.

    home_values = (
        df["home"].astype(str).str.lower().str.strip()
    )

    df["home_flag"] = home_values.map({
        "true": 1,
        "1": 1,
        "yes": 1,
        "home": 1,
        "h": 1,
        "false": 0,
        "0": 0,
        "no": 0,
        "away": 0,
        "a": 0
    })

    numeric_home = pd.to_numeric(
        df["home"],
        errors="coerce"
    )

    df["home_flag"] = df["home_flag"].fillna(
        numeric_home
    )

    df = df.dropna(subset=["home_flag"])

    # Define whether this team won its game.

    df["target"] = (
        df["points"] > df["opponent_points"]
    ).astype(int)

    df = df.sort_values(
        ["team", "game_date"]
    ).reset_index(drop=True)

    return df


# --------------------------------
# BUILD PRE-GAME STATISTICS
# --------------------------------

def build_features(df):

    df = df.copy()

    statistics = [
        "points",
        "opponent_points",
        "point_diff",
        "field_goal_pct",
        "three_point_pct",
        "rebounds",
        "assists",
        "turnovers",
        "off_rating_est",
        "def_rating_est"
    ]

    team_feature_columns = []

    # Calculate rolling statistics using
    # previous games only.

    for stat in statistics:

        for window, minimum in [
            (5, 3),
            (10, 5)
        ]:

            feature_name = (
                f"team_{stat}_last{window}"
            )

            df[feature_name] = (
                df.groupby("team")[stat]
                .transform(
                    lambda values:
                    values.shift(1)
                    .rolling(
                        window=window,
                        min_periods=minimum
                    )
                    .mean()
                )
            )

            team_feature_columns.append(
                feature_name
            )

    # Retrieve the opponent's pre-game
    # statistics for the same game.

    opponent_features = df[
        ["team", "game_date"] + team_feature_columns
    ].copy()

    opponent_features = opponent_features.rename(
        columns={
            "team": "opponent",
            **{
                column: column.replace(
                    "team_", "opp_"
                )
                for column in team_feature_columns
            }
        }
    )

    df = df.merge(
        opponent_features,
        on=["opponent", "game_date"],
        how="left"
    )

    opponent_feature_columns = [
        column.replace("team_", "opp_")
        for column in team_feature_columns
    ]

    feature_columns = (
        ["home_flag"]
        + team_feature_columns
        + opponent_feature_columns
    )

    # Remove early games without enough
    # previous-game statistics.

    model_data = df.dropna(
        subset=feature_columns + ["target"]
    ).copy()

    return model_data, feature_columns


# --------------------------------
# TRAIN AND TEST THE MODEL
# --------------------------------

def train_and_evaluate():

    df = load_nba_data()

    model_data, feature_columns = build_features(df)

    if len(model_data) < 100:
        raise ValueError(
            "Not enough usable historical games to train."
        )

    # Split by DATE, not random rows.
    # This prevents future games from entering training.

    dates = sorted(
        model_data["game_date"].unique()
    )

    split_index = int(len(dates) * 0.80)

    if split_index <= 0 or split_index >= len(dates):
        raise ValueError(
            "Not enough distinct game dates to create a test set."
        )

    cutoff_date = dates[split_index]

    train = model_data[
        model_data["game_date"] < cutoff_date
    ]

    test = model_data[
        model_data["game_date"] >= cutoff_date
    ]

    X_train = train[feature_columns]
    y_train = train["target"]

    X_test = test[feature_columns]
    y_test = test["target"]

    if y_train.nunique() < 2 or y_test.nunique() < 2:
        raise ValueError(
            "Training or testing data does not contain both outcomes."
        )

    # Standardize statistics and train
    # a logistic regression model.

    model = Pipeline([
        ("scaler", StandardScaler()),
        (
            "classifier",
            LogisticRegression(max_iter=1000)
        )
    ])

    model.fit(X_train, y_train)

    # Generate probabilities on unseen dates.

    predictions = model.predict_proba(X_test)[:, 1]

    # Save individual test predictions for backtesting.

    test_predictions = X_test.copy()

    test_predictions["actual_result"] = y_test.values
    test_predictions["model_probability"] = predictions

    test_predictions["game_date"] = df.loc[X_test.index, "game_date"].values
    test_predictions["team"] = df.loc[X_test.index, "team"].values
    test_predictions["opponent"] = df.loc[X_test.index, "opponent"].values

    predicted_classes = (
        predictions >= 0.50
    ).astype(int)

    # Compare against a simple baseline
    # that always predicts the training win rate.

    baseline_probability = y_train.mean()

    baseline_predictions = np.full(
        len(y_test),
        baseline_probability
    )

    metrics = {
        "training_rows": len(train),
        "testing_rows": len(test),
        "test_start_date": str(
            pd.Timestamp(cutoff_date).date()
        ),
        "accuracy": accuracy_score(
            y_test,
            predicted_classes
        ),
        "brier_score": brier_score_loss(
            y_test,
            predictions
        ),
        "log_loss": log_loss(
            y_test,
            predictions,
            labels=[0, 1]
        ),
        "baseline_brier_score": brier_score_loss(
            y_test,
            baseline_predictions
        ),
        "baseline_log_loss": log_loss(
            y_test,
            baseline_predictions,
            labels=[0, 1]
        )
    }


    # --------------------------------
    # PROBABILITY CALIBRATION REPORT
    # --------------------------------

    calibration_bins = [
        0.0, 0.50, 0.55, 0.60, 0.65,
        0.70, 0.75, 0.80, 0.85, 0.90,
        0.95, 1.000001
    ]

    calibration_labels = [
        "Below 50%",
        "50–55%",
        "55–60%",
        "60–65%",
        "65–70%",
        "70–75%",
        "75–80%",
        "80–85%",
        "85–90%",
        "90–95%",
        "95–100%"
    ]

    calibration_data = pd.DataFrame({
        "Predicted Probability": predictions,
        "Actual Result": y_test.values
    })

    calibration_data["Probability Range"] = pd.cut(
        calibration_data["Predicted Probability"],
        bins=calibration_bins,
        labels=calibration_labels,
        right=False,
        include_lowest=True
    )

    calibration_report = (
        calibration_data
        .groupby("Probability Range", observed=False)
        .agg({
            "Predicted Probability": "mean",
            "Actual Result": "mean"
        })
        .reset_index()
    )

    counts = (
        calibration_data
        .groupby("Probability Range", observed=False)
        .size()
        .reset_index(name="Predictions")
    )

    calibration_report = calibration_report.merge(
        counts,
        on="Probability Range"
    )

    calibration_report = calibration_report[
        calibration_report["Predictions"] > 0
    ].copy()

    return {
        "model": model,
        "metrics": metrics,
        "feature_columns": feature_columns,
        "historical_data": df,
        "calibration_report": calibration_report,
        "test_predictions": test_predictions
    }
