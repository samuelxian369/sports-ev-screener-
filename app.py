
import streamlit as st
import pandas as pd

from data_providers.odds_api import fetch_odds

from models.nba_win_model import train_and_evaluate


st.set_page_config(
    page_title="Sports Betting EV Screener",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Sports Betting EV Screener")
st.write("Compare sportsbook prices and calculate expected value.")


# -----------------------------
# HELPER FUNCTIONS
# -----------------------------

def format_book(book):

    names = {
        "williamhill_us": "William Hill",
        "betrivers": "BetRivers",
        "hardrockbet": "Hard Rock Bet",
        "betmgm": "BetMGM",
        "draftkings": "DraftKings",
        "fanduel": "FanDuel",
        "fanatics": "Fanatics",
        "circa": "Circa"
    }

    return names.get(book, book.replace("_", " ").title())


def american_to_probability(odds):

    if odds is None:
        return None

    odds = float(odds)

    if odds < 0:
        return abs(odds) / (abs(odds) + 100)

    if odds > 0:
        return 100 / (odds + 100)

    return None


def american_to_decimal(odds):

    odds = float(odds)

    if odds > 0:
        return 1 + odds / 100

    if odds < 0:
        return 1 + 100 / abs(odds)

    raise ValueError("Odds cannot be zero.")


def calculate_ev(estimated_probability, odds, stake=100):

    decimal_odds = american_to_decimal(odds)

    win_profit = (decimal_odds - 1) * stake
    loss_amount = stake

    expected_value = (
        estimated_probability * win_profit
        - (1 - estimated_probability) * loss_amount
    )

    return expected_value


def format_pacific_time(timestamp):

    if pd.isna(timestamp):
        return "Unavailable"

    converted = pd.to_datetime(
        timestamp,
        format="ISO8601",
        utc=True
    )

    return converted.tz_convert(
        "America/Los_Angeles"
    ).strftime("%b %d, %I:%M %p")


def convert_odds_data(response):

    rows = []

    for game in response.get("data", []):

        home = game.get("home_team", "Unknown")
        away = game.get("away_team", "Unknown")

        for book in game.get("books", []):

            for outcome in book.get("outcomes", []):

                odds = outcome.get("price")

                if odds is None:
                    continue

                rows.append({
                    "Event ID": game.get("event_id"),
                    "Game": f"{away} @ {home}",
                    "Start Time UTC": game.get("start_time"),
                    "Sportsbook": format_book(
                        book.get("book", "Unknown")
                    ),
                    "Market": book.get("market", "Unknown"),
                    "Selection": outcome.get("name", "Unknown"),
                    "American Odds": float(odds),
                    "Last Updated UTC": book.get("updated_at"),
                    "Implied Probability": american_to_probability(odds)
                })

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    group_columns = [
        "Event ID",
        "Sportsbook",
        "Market"
    ]

    df["Probability Total"] = (
        df.groupby(group_columns)["Implied Probability"]
        .transform("sum")
    )

    df["Outcome Count"] = (
        df.groupby(group_columns)["Implied Probability"]
        .transform("count")
    )

    df["No-Vig Probability"] = (
        df["Implied Probability"] / df["Probability Total"]
    )

    df.loc[
        (df["Outcome Count"] < 2) |
        (df["Probability Total"] <= 0),
        "No-Vig Probability"
    ] = None

    return df


# -----------------------------
# BEST AVAILABLE ODDS FINDER
# -----------------------------

def find_best_odds(df):

    if df.empty:
        return pd.DataFrame()

    group_columns = [
        "Event ID",
        "Game",
        "Market",
        "Selection"
    ]

    best_indexes = (
        df.groupby(group_columns)["American Odds"].idxmax()
    )

    best = df.loc[best_indexes].copy()

    best = best.rename(columns={
        "Sportsbook": "Best Sportsbook",
        "American Odds": "Best Odds",
        "Last Updated UTC": "Best Price Updated UTC"
    })

    consensus = (
        df.groupby(group_columns)
        .agg(
            Market_Fair_Probability=("No-Vig Probability", "mean"),
            Books_Compared=("No-Vig Probability", "count")
        )
        .reset_index()
    )

    best = best.merge(
        consensus,
        on=group_columns,
        how="left"
    )

    best["Best Price Break-Even"] = (
        best["Best Odds"].apply(american_to_probability)
    )

    best["Probability Difference"] = (
        best["Market_Fair_Probability"]
        - best["Best Price Break-Even"]
    )

    return best.reset_index(drop=True)


# -----------------------------
# SESSION STORAGE
# -----------------------------

if "best_odds" not in st.session_state:
    st.session_state["best_odds"] = None

if "all_quotes" not in st.session_state:
    st.session_state["all_quotes"] = None

if "data_source" not in st.session_state:
    st.session_state["data_source"] = None


# -----------------------------
# FETCH ODDS
# -----------------------------

st.sidebar.header("Screener Settings")

st.sidebar.selectbox(
    "Select Sport",
    ["NBA"]
)

st.sidebar.selectbox(
    "Select Market",
    ["Moneyline"]
)

st.header("NBA Best Available Odds")

st.write(
    "Find the best available sportsbook price for each team."
)

if st.button("Fetch NBA Odds", type="primary"):

    with st.spinner("Retrieving and comparing sportsbook odds..."):

        try:

            response = fetch_odds(
                sport="basketball_nba",
                markets=["h2h"]
            )

            if not response.get("success"):

                st.error("The API returned an unsuccessful response.")

            else:

                df = convert_odds_data(response)

                if df.empty:

                    st.warning("No odds were returned.")

                else:

                    best = find_best_odds(df)

                    st.session_state["best_odds"] = best
                    st.session_state["all_quotes"] = df
                    st.session_state["data_source"] = response.get(
                        "source", "Unknown"
                    )

                    st.success("Odds retrieved and compared!")

        except Exception as error:

            st.error(f"Something went wrong: {error}")


# -----------------------------
# DISPLAY SAVED ODDS TABLES
# -----------------------------

best = st.session_state["best_odds"]
df = st.session_state["all_quotes"]

if best is not None and not best.empty:

    st.subheader("Current Odds Results")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Games Found",
        df["Event ID"].nunique()
    )

    col2.metric(
        "Sportsbook Quotes",
        len(df)
    )

    col3.metric(
        "Selections Compared",
        len(best)
    )

    st.caption(
        f"Provider data source: {st.session_state['data_source']}"
    )

    best_display = best.copy()

    best_display["Start Time"] = (
        best_display["Start Time UTC"]
        .apply(format_pacific_time)
    )

    best_display["Best Price Updated"] = (
        best_display["Best Price Updated UTC"]
        .apply(format_pacific_time)
    )

    best_display["Market Fair Probability"] = (
        best_display["Market_Fair_Probability"]
        .apply(
            lambda x: f"{x:.2%}"
            if pd.notna(x) else "Unavailable"
        )
    )

    best_display["Break-Even Probability"] = (
        best_display["Best Price Break-Even"]
        .apply(lambda x: f"{x:.2%}")
    )

    best_display["Probability Difference"] = (
        best_display["Probability Difference"]
        .apply(
            lambda x: f"{x:+.2%}"
            if pd.notna(x) else "Unavailable"
        )
    )

    best_display = best_display[[
        "Game",
        "Selection",
        "Best Sportsbook",
        "Best Odds",
        "Market Fair Probability",
        "Break-Even Probability",
        "Probability Difference",
        "Books_Compared",
        "Start Time",
        "Best Price Updated"
    ]].copy()

    best_display = best_display.rename(columns={
        "Best Odds": "Best American Odds",
        "Books_Compared": "Books Compared"
    })

    tab1, tab2 = st.tabs([
        "Best Available Odds",
        "All Sportsbook Quotes"
    ])

    with tab1:

        st.subheader("Best Price for Each Team")

        st.dataframe(
            best_display,
            use_container_width=True,
            hide_index=True
        )

        st.download_button(
            "Download Best Odds CSV",
            data=best_display.to_csv(index=False),
            file_name="best_nba_odds.csv",
            mime="text/csv"
        )

    with tab2:

        st.subheader("Individual Sportsbook Prices")

        all_quotes = df.copy()

        all_quotes["Last Updated"] = (
            all_quotes["Last Updated UTC"]
            .apply(format_pacific_time)
        )

        all_quotes["No-Vig Probability"] = (
            all_quotes["No-Vig Probability"]
            .apply(
                lambda x: f"{x:.2%}"
                if pd.notna(x) else "Unavailable"
            )
        )

        all_quotes = all_quotes[[
            "Game",
            "Sportsbook",
            "Selection",
            "American Odds",
            "No-Vig Probability",
            "Last Updated"
        ]]

        st.dataframe(
            all_quotes,
            use_container_width=True,
            hide_index=True
        )

    st.info(
        "The market fair probability is an average of sportsbook "
        "no-vig probabilities. It is a market benchmark, not an "
        "independent prediction."
    )

    # -----------------------------
    # TEMPORARY EV CALCULATOR
    # -----------------------------

    st.divider()

    st.header("Expected Value Calculator")

    st.write(
        "This calculator temporarily uses a manually entered probability "
        "to test the EV calculations. The final version will replace this "
        "input with a probability generated by our statistical model."
    )

    best_for_calculator = best.reset_index(drop=True)

    choice_labels = []

    for index, row in best_for_calculator.iterrows():

        choice_labels.append(
            f"{row['Game']} | {row['Market']} | "
            f"{row['Selection']} | {row['Best Sportsbook']} "
            f"| Option {index + 1}"
        )

    selected_choice = st.selectbox(
        "Choose a selection to evaluate",
        choice_labels
    )

    selected_index = choice_labels.index(selected_choice)

    selected = best_for_calculator.iloc[selected_index]

    st.subheader(selected["Selection"])

    info1, info2, info3 = st.columns(3)

    info1.metric(
        "Best Sportsbook",
        selected["Best Sportsbook"]
    )

    info2.metric(
        "Best American Odds",
        f"{selected['Best Odds']:+.0f}"
    )

    info3.metric(
        "Break-Even Probability",
        f"{selected['Best Price Break-Even']:.2%}"
    )

    if pd.notna(selected["Market_Fair_Probability"]):

        st.write(
            "Average sportsbook no-vig probability: "
            f"**{selected['Market_Fair_Probability']:.2%}**"
        )

    estimated_probability_pct = st.number_input(
        "Temporary estimated win probability (%)",
        min_value=0.0,
        max_value=100.0,
        value=50.0,
        step=0.5
    )

    estimated_probability = estimated_probability_pct / 100

    expected_value = calculate_ev(
        estimated_probability,
        selected["Best Odds"],
        stake=100
    )

    expected_value_pct = expected_value

    st.subheader("EV Calculation Results")

    result1, result2, result3 = st.columns(3)

    result1.metric(
        "Estimated Win Probability",
        f"{estimated_probability_pct:.1f}%"
    )

    result2.metric(
        "Expected Value per $100",
        f"${expected_value:+.2f}"
    )

    result3.metric(
        "Expected ROI",
        f"{expected_value_pct:+.2f}%"
    )

    if expected_value > 0:

        st.success(
            "Positive theoretical EV using the probability you entered."
        )

    elif expected_value < 0:

        st.warning(
            "Negative theoretical EV using the probability you entered."
        )

    else:

        st.info("This estimate is exactly at break-even.")

    st.caption(
        "Important: This is a calculation test, not a betting recommendation. "
        "The result is only as reliable as the probability entered. "
        "The final system will generate its own estimates from statistical "
        "data, and those estimates must be tested against historical results."
    )

else:

    st.info("Click 'Fetch NBA Odds' to load odds and use the calculator.")


st.divider()

st.caption(
    "Development version | NBA Moneyline | BettingDataAPI"
)


# --------------------------------
# NBA PREDICTION MODEL TESTING
# --------------------------------

st.divider()

st.header("🧠 NBA Prediction Model")

st.write(
    "Train the statistical model using historical NBA results "
    "and evaluate its predictions on unseen games."
)


if st.button("Train and Test NBA Model", type="primary"):

    with st.spinner(
        "Training the model and testing historical predictions..."
    ):

        try:

            results = train_and_evaluate()

            st.session_state["nba_model_metrics"] = (
                results["metrics"]
            )

            st.session_state["nba_calibration_report"] = (
                results["calibration_report"]
            )

            st.session_state["nba_test_predictions"] = (
                results["test_predictions"]
            )
            
            st.success("Model training and testing completed!")

        except Exception as error:

            st.error(
                f"Model training failed: {error}"
            )



# Display saved results

if "nba_model_metrics" in st.session_state:

    metrics = st.session_state["nba_model_metrics"]

    st.subheader("Historical Test Results")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Prediction Accuracy",
        f"{metrics['accuracy']:.1%}"
    )

    col2.metric(
        "Model Brier Score",
        f"{metrics['brier_score']:.4f}"
    )

    col3.metric(
        "Model Log Loss",
        f"{metrics['log_loss']:.4f}"
    )

    st.subheader("Model vs. Baseline")

    comparison = pd.DataFrame({
        "Measurement": [
            "Brier Score",
            "Log Loss"
        ],
        "Our Model": [
            metrics["brier_score"],
            metrics["log_loss"]
        ],
        "Simple Baseline": [
            metrics["baseline_brier_score"],
            metrics["baseline_log_loss"]
        ]
    })

    st.dataframe(
        comparison,
        use_container_width=True,
        hide_index=True
    )


    st.divider()

    st.subheader("Probability Calibration")

    st.write(
        "Compare the probabilities predicted by our model "
        "against the actual win rates."
    )

    if "nba_calibration_report" in st.session_state:

        calibration = (
            st.session_state["nba_calibration_report"].copy()
        )

        calibration["Average Predicted Probability"] = (
            calibration["Predicted Probability"]
            .apply(
                lambda x: f"{x:.1%}"
                if pd.notna(x) else "Unavailable"
            )
        )

        calibration["Actual Win Rate"] = (
            calibration["Actual Result"]
            .apply(
                lambda x: f"{x:.1%}"
                if pd.notna(x) else "Unavailable"
            )
        )

        calibration = calibration[[
            "Probability Range",
            "Average Predicted Probability",
            "Actual Win Rate",
            "Predictions"
        ]]

        st.dataframe(
            calibration,
            use_container_width=True,
            hide_index=True
        )

        st.caption(
            "A well-calibrated model should have an actual "
            "win rate close to its average predicted probability. "
            "Ranges with very few predictions are less reliable."
        )

    
    st.write(
        f"Training games: **{metrics['training_rows']:,}**"
    )

    st.write(
        f"Testing games: **{metrics['testing_rows']:,}**"
    )

    st.write(
        f"Testing began: **{metrics['test_start_date']}**"
    )

    if (
        metrics["brier_score"]
        < metrics["baseline_brier_score"]
        and metrics["log_loss"]
        < metrics["baseline_log_loss"]
    ):

        st.success(
            "The model outperformed the simple baseline "
            "on both probability scoring measurements."
        )

    else:

        st.warning(
            "The model has not beaten the baseline on both "
            "measurements. We need to investigate and improve it."
        )

    st.caption(
        "These are historical test results, not a guarantee "
        "of future betting performance. We must validate "
        "probability calibration and test additional seasons."
    )


# ==========================================
# HISTORICAL ODDS DATASET CHECK
# ==========================================

st.header("Historical NBA Odds Dataset")

import os

odds_file = "data/odds_moneyline.csv"

if os.path.exists(odds_file):
    try:
        historical_odds = pd.read_csv(odds_file)

        st.success("Historical odds file loaded successfully!")

        st.write("Total odds records:", len(historical_odds))

        st.write(
            "Date range:",
            historical_odds["game_date"].min(),
            "to",
            historical_odds["game_date"].max()
        )

        st.write(
            "Number of sportsbooks:",
            historical_odds["bookmaker"].nunique()
        )

        st.write("Sportsbooks included:")
        st.write(sorted(historical_odds["bookmaker"].dropna().unique()))

        st.write("Benchmark-eligible records:")
        st.write(
            historical_odds["benchmark_eligible"]
            .astype(str)
            .str.lower()
            .eq("true")
            .sum()
        )

        st.subheader("Sample Historical Odds")
        st.dataframe(historical_odds.head(10))

    except Exception as error:
        st.error(f"Could not read the historical odds file: {error}")

else:
    st.error(f"File not found: {odds_file}")


# ==========================================
# HISTORICAL ODDS DATA QUALITY CHECK
# ==========================================

st.header("Historical Odds Data Quality")

if os.path.exists("data/odds_moneyline.csv"):

    odds_check = pd.read_csv("data/odds_moneyline.csv")

    st.write("Unique games:", odds_check["game_id"].nunique())

    st.write("Odds records per game (average):",
             round(len(odds_check) / odds_check["game_id"].nunique(), 2))

    st.subheader("Snapshot Types")
    st.code(odds_check["snapshot"].value_counts(dropna=False).to_string())

    st.subheader("Quote Quality")
    st.code(odds_check["quote_quality"].value_counts(dropna=False).to_string())

    st.subheader("Data Flags")

    for column in ["benchmark_eligible", "score_verified", "benchmark_only"]:
        st.write(column)
        st.code(odds_check[column].value_counts(dropna=False).to_string())

    st.subheader("Missing Odds Prices")

    st.write("Missing home moneylines:",
             odds_check["home_moneyline"].isna().sum())

    st.write("Missing away moneylines:",
             odds_check["away_moneyline"].isna().sum())

    st.write("Missing no-vig home probabilities:",
             odds_check["home_no_vig_probability"].isna().sum())

    st.write("Missing no-vig away probabilities:",
             odds_check["away_no_vig_probability"].isna().sum())

    st.subheader("Sample Records")
    st.dataframe(odds_check.head(5))


# ==========================================
# NBA TEST PREDICTIONS INSPECTION
# ==========================================

if "nba_test_predictions" in st.session_state:

    predictions_df = st.session_state["nba_test_predictions"]

    st.divider()
    st.header("NBA Test Predictions")

    st.write("Total predictions:", len(predictions_df))

    st.write("Available columns:")
    st.write(list(predictions_df.columns))

    st.subheader("First 10 Predictions")
    st.dataframe(predictions_df.head(10))


# ==========================================
# CHECK MODEL PREDICTIONS AGAINST HISTORICAL ODDS
# ==========================================

if "nba_test_predictions" in st.session_state:

    predictions_df = st.session_state["nba_test_predictions"]

    st.divider()
    st.header("Historical Odds Match Check")

    try:
        odds_df = pd.read_csv("data/odds_moneyline.csv")

        # Convert model predictions into home/away game records
        test_games = predictions_df[
            ["game_date", "home_flag", "team", "opponent"]
        ].copy()

        test_games["game_date"] = (
            pd.to_datetime(test_games["game_date"])
            .dt.strftime("%Y-%m-%d")
        )

        test_games["home_abbr"] = test_games.apply(
            lambda row: row["team"]
            if row["home_flag"] == 1
            else row["opponent"],
            axis=1
        )

        test_games["away_abbr"] = test_games.apply(
            lambda row: row["opponent"]
            if row["home_flag"] == 1
            else row["team"],
            axis=1
        )

        test_games = test_games[
            ["game_date", "home_abbr", "away_abbr"]
        ].drop_duplicates()

        # Keep reliable closing odds records
        odds_df["game_date"] = (
            pd.to_datetime(odds_df["game_date"])
            .dt.strftime("%Y-%m-%d")
        )

        close_odds = odds_df[
            (odds_df["snapshot"] == "close") &
            (odds_df["quote_quality"] == "ok") &
            (odds_df["benchmark_eligible"].astype(str).str.lower() == "true")
        ].copy()

        odds_games = close_odds[
            ["game_date", "home_abbr", "away_abbr"]
        ].drop_duplicates()

        # Match model test games to historical odds games
        matched = test_games.merge(
            odds_games,
            on=["game_date", "home_abbr", "away_abbr"],
            how="inner"
        )

        unmatched = test_games.merge(
            odds_games,
            on=["game_date", "home_abbr", "away_abbr"],
            how="left",
            indicator=True
        )

        unmatched = unmatched[
            unmatched["_merge"] == "left_only"
        ]

        st.write("Model test games:", len(test_games))
        st.write("Historical closing-odds games:", len(odds_games))
        st.write("Successfully matched games:", len(matched))
        st.write("Unmatched model games:", len(unmatched))

        if len(test_games) > 0:
            match_rate = len(matched) / len(test_games) * 100
            st.write(f"Match rate: {match_rate:.1f}%")

        st.subheader("Example Matched Games")
        st.dataframe(matched.head(10))

        st.subheader("Example Unmatched Games")
        st.dataframe(unmatched.head(10))

        st.subheader("Example Historical Closing Odds")
        st.dataframe(
            close_odds[
                [
                    "game_date",
                    "home_abbr",
                    "away_abbr",
                    "bookmaker",
                    "home_moneyline",
                    "away_moneyline",
                    "home_no_vig_probability",
                    "away_no_vig_probability"
                ]
            ].head(10)
        )

    except Exception as error:
        st.error(f"Odds matching check failed: {error}")
