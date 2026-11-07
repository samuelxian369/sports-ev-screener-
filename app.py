
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
    "Your personal platform for identifying "
    "positive Expected Value betting opportunities."
)

st.sidebar.header("Screener Settings")

sport = st.sidebar.selectbox(
    "Select Sport",
    ["NBA"]
)

market = st.sidebar.selectbox(
    "Select Market",
    ["Moneyline"]
)

st.header("Live Odds Test")

st.write(
    "This is our first connection to a real sportsbook "
    "odds data provider."
)

if st.button("Fetch NBA Odds"):
    with st.spinner("Retrieving odds..."):
        try:
            odds = fetch_odds(
                sport="basketball_nba",
                markets=["h2h"]
            )

            if odds.empty:
                st.warning(
                    "The API connected, but no odds were returned. "
                    "There may be no available games."
                )
            else:
                st.success("Successfully retrieved odds!")
                st.metric("Odds Retrieved", len(odds))
                st.dataframe(
                    odds,
                    use_container_width=True
                )

        except Exception as error:
            st.error(f"Something went wrong: {error}")

st.caption(
    "Initial testing version — NBA moneyline markets only."
)
