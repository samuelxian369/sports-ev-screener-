
import streamlit as st
import pandas as pd

from data_providers.odds_api import fetch_odds


st.set_page_config(
    page_title="Sports Betting EV Screener",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Sports Betting EV Screener")

st.write(
    "A research platform for identifying "
    "positive Expected Value betting opportunities."
)


# -----------------------------
# SIDEBAR
# -----------------------------

st.sidebar.header("Screener Settings")

sport = st.sidebar.selectbox("Select Sport", ["NBA"])
market = st.sidebar.selectbox("Select Market", ["Moneyline"])


# -----------------------------
# ODDS CALCULATIONS
# -----------------------------

def american_to_probability(odds):

    if odds is None:
        return None

    try:
        odds = float(odds)
    except (ValueError, TypeError):
        return None

    if odds < 0:
        return abs(odds) / (abs(odds) + 100)

    elif odds > 0:
        return 100 / (odds + 100)

    return None


def convert_book(book):

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


def convert_odds_data(response):

    rows = []

    for game in response.get("data", []):

        home = game.get("home_team", "Unknown")
        away = game.get("away_team", "Unknown")

        for book in game.get("books", []):

            for outcome in book.get("outcomes", []):

                odds = outcome.get("price")

                rows.append({
                    "Event ID": game.get("event_id"),
                    "Game": f"{away} @ {home}",
                    "Start Time (UTC)": game.get("start_time"),
                    "Sportsbook": convert_book(
                        book.get("book", "Unknown")
                    ),
                    "Market": book.get("market", "Unknown"),
                    "Selection": outcome.get("name", "Unknown"),
                    "American Odds": odds,
                    "Last Updated (UTC)": book.get("updated_at"),
                    "Implied Probability": american_to_probability(odds)
                })

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    # Calculate no-vig probability separately
    # for each game, sportsbook and market.

    group_columns = [
        "Event ID",
        "Sportsbook",
        "Market"
    ]

    df["Market Probability Total"] = (
        df.groupby(group_columns)["Implied Probability"]
        .transform("sum")
    )

    df["Outcome Count"] = (
        df.groupby(group_columns)["Implied Probability"]
        .transform("count")
    )

    # Only calculate when at least two outcomes are available.
    # A single-sided quote cannot produce a reliable no-vig estimate.

    df["No-Vig Probability"] = (
        df["Implied Probability"] /
        df["Market Probability Total"]
    )

    df.loc[
        (df["Outcome Count"] < 2) |
        (df["Market Probability Total"] <= 0),
        "No-Vig Probability"
    ] = None

    return df


# -----------------------------
# DASHBOARD
# -----------------------------

st.header("NBA Moneyline Analysis")

st.write(
    "Compare sportsbook odds and calculate "
    "vig-free market probabilities."
)

if st.button("Fetch NBA Odds", type="primary"):

    with st.spinner("Retrieving NBA odds..."):

        try:

            response = fetch_odds(
                sport="basketball_nba",
                markets=["h2h"]
            )

            if not response.get("success"):

                st.error("The API returned an unsuccessful response.")

            else:

                odds_table = convert_odds_data(response)

                games = response.get("data", [])

                st.success("Successfully retrieved odds!")

                col1, col2, col3 = st.columns(3)

                col1.metric("Games Found", len(games))

                col2.metric("Odds Records", len(odds_table))

                col3.metric(
                    "Data Source",
                    response.get("source", "Unknown").title()
                )

                if odds_table.empty:

                    st.warning("No odds were returned.")

                else:

                    # Convert timestamps to Pacific Time.

                    odds_table["Start Time"] = (
                        pd.to_datetime(
                            odds_table["Start Time (UTC)"],
                            format="ISO8601",
                            utc=True
                        )
                        .dt.tz_convert("America/Los_Angeles")
                        .dt.strftime("%b %d, %I:%M %p")
                    )

                    odds_table["Last Updated"] = (
                        pd.to_datetime(
                            odds_table["Last Updated (UTC)"],
                            format="ISO8601",
                            utc=True
                        )
                        .dt.tz_convert("America/Los_Angeles")
                        .dt.strftime("%b %d, %I:%M %p")
                    )

                    # Display probabilities as percentages.

                    odds_table["Implied Probability"] = (
                        odds_table["Implied Probability"]
                        .apply(
                            lambda x: f"{x:.2%}"
                            if pd.notna(x) else "—"
                        )
                    )

                    odds_table["No-Vig Probability"] = (
                        odds_table["No-Vig Probability"]
                        .apply(
                            lambda x: f"{x:.2%}"
                            if pd.notna(x) else "Unavailable"
                        )
                    )

                    # Remove internal calculation columns.

                    odds_table = odds_table.drop(
                        columns=[
                            "Event ID",
                            "Start Time (UTC)",
                            "Last Updated (UTC)",
                            "Market Probability Total",
                            "Outcome Count"
                        ]
                    )

                    st.subheader("Sportsbook Odds & Fair Probabilities")

                    st.dataframe(
                        odds_table,
                        use_container_width=True,
                        hide_index=True
                    )

                    st.download_button(
                        "Download Analysis as CSV",
                        data=odds_table.to_csv(index=False),
                        file_name="nba_no_vig_analysis.csv",
                        mime="text/csv"
                    )

                    st.info(
                        "No-vig probabilities are calculated "
                        "separately for each sportsbook. They are "
                        "market benchmarks, not independent predictions."
                    )

        except Exception as error:

            st.error(f"Something went wrong: {error}")


st.divider()

st.caption(
    "Development version | NBA Moneyline | BettingDataAPI"
)
