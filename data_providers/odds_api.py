
import requests
import streamlit as st


API_URL = "https://api.bettingdataapi.com/odds/"


def fetch_odds(sport="basketball_nba", markets=None, bookmakers=None):

    try:
        api_key = st.secrets["ODDS_API_KEY"]
    except Exception:
        raise RuntimeError(
            "API key not found. Check Streamlit Secrets."
        )

    if markets is None:
        markets = ["h2h"]

    if isinstance(markets, list):
        markets = ",".join(markets)

    headers = {
        "x-api-key": api_key
    }

    params = {
        "sport_key": sport,
        "markets": markets
    }

    if bookmakers:
        params["bookmakers"] = ",".join(bookmakers)

    try:
        response = requests.get(
            API_URL,
            headers=headers,
            params=params,
            timeout=20
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"HTTP {response.status_code}: {response.text}"
            )

        data = response.json()

        if not data.get("success"):
            raise RuntimeError(
                data.get("message", "API request was unsuccessful.")
            )

        return data

    except requests.exceptions.RequestException as error:
        raise RuntimeError(
            f"Could not retrieve odds: {error}"
        )
