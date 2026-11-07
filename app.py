
import streamlit as st
import pandas as pd

from data_providers.odds_api import fetch_odds


st.set_page_config(
    page_title="Sports Betting EV Screener",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Sports Betting EV Screener")
st.write("Compare sportsbook prices and identify the best available odds.")


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

    # Calculate no-vig probabilities separately
    # for each game and sportsbook.

    book_groups = [
        "Event ID",
        "Sportsbook",
        "Market"
    ]

    df["Probability Total"] = (
        df.groupby(book_groups)["Implied Probability"]
        .transform("sum")
    )

    df["Outcome Count"] = (
        df.groupby(book_groups)["Implied Probability"]
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

    # Find the highest American odds for each selection.
    best_indexes = (
        df.groupby(group_columns)["American Odds"].idxmax()
    )

    best = df.loc[best_indexes].copy()

    best = best.rename(columns={
        "Sportsbook": "Best Sportsbook",
        "American Odds": "Best Odds",
        "Last Updated UTC": "Best Price Updated UTC"
    })

    # Average no-vig probability across available books.
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

    # Compare the best price's break-even probability
    # with the average market no-vig probability.

    best["Best Price Break-Even"] = (
        best["Best Odds"].apply(american_to_probability)
    )

    best["Probability Difference"] = (
        best["Market_Fair_Probability"]
        - best["Best Price Break-Even"]
    )

    return best


# -----------------------------
# DASHBOARD
# -----------------------------

st.sidebar.header("Screener Settings")

sport = st.sidebar.selectbox("Select Sport", ["NBA"])
market = st.sidebar.selectbox("Select Market", ["Moneyline"])

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

                    st.success("Odds retrieved and compared!")

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

                    # Format timestamps for Pacific Time.

                    best["Start Time"] = (
                        pd.to_datetime(
                            best["Start Time UTC"],
                            format="ISO8601",
                            utc=True
                        )
                        .dt.tz_convert("America/Los_Angeles")
                        .dt.strftime("%b %d, %I:%M %p")
                    )

                    best["Best Price Updated"] = (
                        pd.to_datetime(
                            best["Best Price Updated UTC"],
                            format="ISO8601",
                            utc=True
                        )
                        .dt.tz_convert("America/Los_Angeles")
                        .dt.strftime("%b %d, %I:%M %p")
                    )

                    best["Market Fair Probability"] = (
                        best["Market_Fair_Probability"]
                        .apply(
                            lambda x: f"{x:.2%}"
                            if pd.notna(x) else "Unavailable"
                        )
                    )

                    best["Break-Even Probability"] = (
                        best["Best Price Break-Even"]
                        .apply(lambda x: f"{x:.2%}")
                    )

                    best["Probability Difference"] = (
                        best["Probability Difference"]
                        .apply(
                            lambda x: f"{x:+.2%}"
                            if pd.notna(x) else "Unavailable"
                        )
                    )

                    best_display = best[[
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
                            pd.to_datetime(
                                all_quotes["Last Updated UTC"],
                                format="ISO8601",
                                utc=True
                            )
                            .dt.tz_convert("America/Los_Angeles")
                            .dt.strftime("%b %d, %I:%M %p")
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
                        "Probability Difference compares the average "
                        "no-vig market probability with the break-even "
                        "probability of the best available price. "
                        "It is not an independent EV estimate."
                    )

        except Exception as error:

            st.error(f"Something went wrong: {error}")


st.divider()

st.caption(
    "Development version | NBA Moneyline | BettingDataAPI"
)
