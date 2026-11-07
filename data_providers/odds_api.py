
import requests
import streamlit as st
import pandas as pd


API_URL = "https://api.bettingdataapi.com/odds/"


def fetch_odds(sport="nba", markets=None, bookmakers=None):
    """
    Retrieve odds from BettingDataAPI.
    Initial test: NBA moneyline odds.
    """

    try:
        api_key = st.secrets["ODDS_API_KEY"]
    except Exception:
        raise RuntimeError(
            "API key not found. Check Streamlit Secrets."
        )

    headers = {
        "x-api-key": api_key
    }

    params = {}

    try:
        response = requests.get(
            API_URL,
            headers=headers,
            params=params,
            timeout=20
        )

        if response.status_code in (401, 403):
            raise RuntimeError(
                "API key rejected. Check your BettingDataAPI key."
            )

        if response.status_code == 429:
            raise RuntimeError(
                "API request limit reached."
            )

        response.raise_for_status()
        data = response.json()

    except requests.exceptions.RequestException as error:
        raise RuntimeError(
            f"Could not retrieve odds: {error}"
        )

    # Show the returned data structure for initial testing.
    return data
