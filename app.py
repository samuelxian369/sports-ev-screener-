import streamlit as st
import pandas as pd
import numpy as np

# Page configuration
st.set_page_config(
    page_title="Sports Betting EV Screener",
    page_icon="📊",
    layout="wide"
)

# Main title
st.title("Sports Betting EV Screener")

st.write(
    "Your personal platform for identifying "
    "positive Expected Value betting opportunities."
)

# Sidebar
st.sidebar.header("Screener Settings")

sport = st.sidebar.selectbox(
    "Select Sport",
    ["All Sports", "NBA", "NFL", "MLB", "NHL", "Soccer", "Tennis"]
)

market = st.sidebar.selectbox(
    "Select Market",
    ["All Markets", "Player Props", "Game Lines", "Totals", "Moneyline"]
)

# Dashboard metrics
col1, col2, col3 = st.columns(3)

col1.metric("Opportunities Found", "--")
col2.metric("Average Expected Value", "--")
col3.metric("Sports Covered", "7")

# Main section
st.header("Betting Opportunities")

st.info(
    "Your screener is being built. "
    "Sportsbook data will appear here once we connect an API."
)

st.write("Selected Sport:", sport)
st.write("Selected Market:", market)
