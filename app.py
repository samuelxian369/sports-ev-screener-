
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
