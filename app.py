
import streamlit as st
import pandas as pd

from data_providers.odds_api import fetch_odds


# -----------------------------
# PAGE CONFIGURATION
# -----------------------------

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

sport = st.sidebar.selectbox(
    "Select Sport",
    ["NBA"]
)

market = st.sidebar.selectbox(
    "Select Market",
    ["Moneyline"]
)


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


def convert_odds_data(response):

    rows = []

    games = response.get("data", [])

    for game in games:

        home = game.get("home_team", "Unknown")
        away = game.get("away_team", "Unknown")

        start_time = game.get("start_time")

        for book in game.get("books", []):

            for outcome in book.get("outcomes", []):

                rows.append({
                    "Game": f"{away} @ {home}",
                    "Start Time (UTC)": start_time,
                    "Sportsbook": format_book(
                        book.get("book", "Unknown")
                    ),
                    "Market": book.get("market", "Unknown"),
                    "Selection": outcome.get("name", "Unknown"),
                    "American Odds": outcome.get("price"),
                    "Last Updated (UTC)": book.get("updated_at")
                })

    return pd.DataFrame(rows)


# -----------------------------
# DASHBOARD
# -----------------------------

st.header("NBA Odds Screener")

st.write(
    "Retrieve moneyline odds from multiple sportsbooks."
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

                st.success("Successfully retrieved odds!")

                games = response.get("data", [])

                col1, col2, col3 = st.columns(3)

                col1.metric(
                    "Games Found",
                    len(games)
                )

                col2.metric(
                    "Odds Records",
                    len(odds_table)
                )

                col3.metric(
                    "Data Source",
                    response.get("source", "Unknown").title()
                )

                if odds_table.empty:

                    st.warning("No odds were returned.")

                else:

                    # Convert UTC times to Oakland local time
                    odds_table["Start Time"] = (
                        pd.to_datetime(
                            odds_table["Start Time (UTC)"],
                            utc=True
                        )
                        .dt.tz_convert("America/Los_Angeles")
                        .dt.strftime("%b %d, %I:%M %p")
                    )

                    odds_table["Last Updated"] = (
                        pd.to_datetime(
                            odds_table["Last Updated (UTC)"],
                            utc=True
                        )
                        .dt.tz_convert("America/Los_Angeles")
                        .dt.strftime("%b %d, %I:%M %p")
                    )

                    odds_table = odds_table.drop(
                        columns=[
                            "Start Time (UTC)",
                            "Last Updated (UTC)"
                        ]
                    )

                    st.subheader("Retrieved Sportsbook Odds")

                    st.dataframe(
                        odds_table,
                        use_container_width=True,
                        hide_index=True
                    )

                    st.caption(
                        "Times are displayed in Pacific Time. "
                        "Last Updated refers to each sportsbook's "
                        "quote timestamp, not necessarily the time "
                        "you retrieved the data."
                    )

                    st.download_button(
                        "Download Odds as CSV",
                        data=odds_table.to_csv(index=False),
                        file_name="nba_odds.csv",
                        mime="text/csv"
                    )

        except Exception as error:

            st.error(f"Something went wrong: {error}")


st.divider()

st.caption(
    "Development version | NBA Moneyline | BettingDataAPI"
)
