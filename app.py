
import streamlit as st
import json

from data_providers.odds_api import fetch_odds


# Page configuration
st.set_page_config(
    page_title="Sports Betting EV Screener",
    page_icon="📊",
    layout="wide"
)


# Main title
st.title("📊 Sports Betting EV Screener")

st.write(
    "A sports betting research platform "
    "focused on identifying positive Expected Value."
)


# Sidebar
st.sidebar.header("Screener Settings")

sport = st.sidebar.selectbox(
    "Select Sport",
    ["NBA"]
)

market = st.sidebar.selectbox(
    "Select Market",
    ["Moneyline"]
)


# Dashboard metrics
col1, col2, col3 = st.columns(3)

col1.metric("Opportunities Found", "--")
col2.metric("Average Expected Value", "--")
col3.metric("Sports Covered", "1")


# Main section
st.header("API Connection Test")

st.write(
    "We're testing the connection to BettingDataAPI "
    "before building the odds analysis system."
)


# Fetch odds button
if st.button("Fetch NBA Odds", type="primary"):

    with st.spinner("Connecting to BettingDataAPI..."):

        try:
            data = fetch_odds(sport="basketball_nba")

            st.success("API request completed!")

            st.subheader("Raw API Response")

            st.json(data)

        except Exception as error:

            st.error("The API request failed.")

            st.code(str(error))


# Footer
st.divider()

st.caption(
    "Development version — NBA moneyline testing."
)

