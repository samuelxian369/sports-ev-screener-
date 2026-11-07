
import requests
import streamlit as st
import pandas as pd


API_URL = "https://api.the-odds-api.com/v4/sports"


def fetch_odds(sport="basketball_nba", markets=None, bookmakers=None):
    """
    Fetch odds from The Odds API.

    Initial test: NBA moneyline odds.
    """

    # Get the API key from Streamlit's secure settings
    try:
        api_key = st.secrets["ODDS_API_KEY"]
    except Exception:
        raise RuntimeError(
            "API key not found. Check Streamlit Secrets settings."
        )

    # Start with the basic moneyline market
    if markets is None:
        markets = ["h2h"]

    if isinstance(markets, list):
        markets = ",".join(markets)

    params = {
        "apiKey": api_key,
        "regions": "us",
        "markets": markets,
        "oddsFormat": "american"
    }

    if bookmakers:
        params["bookmakers"] = ",".join(bookmakers)

    # Send the request
    try:
        response = requests.get(
            f"{API_URL}/{sport}/odds",
            params=params,
            timeout=20
        )

        if response.status_code == 401:
            raise RuntimeError(
                "API key was rejected. Check your Streamlit Secrets."
            )

        if response.status_code == 429:
            raise RuntimeError(
                "API request limit reached. Try again later."
            )

        response.raise_for_status()
        games = response.json()

    except requests.exceptions.RequestException as error:
        raise RuntimeError(f"Could not retrieve odds: {error}")

    # Convert the response into a table
    rows = []

    for game in games:
        for bookmaker in game.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                for outcome in market.get("outcomes", []):

                    rows.append({
                        "Game": (
                            f"{game['away_team']} @ {game['home_team']}"
                        ),
                        "Start Time": game.get("commence_time"),
                        "Sportsbook": bookmaker.get("title"),
                        "Market": market.get("key"),
                        "Selection": outcome.get("name"),
                        "Odds": outcome.get("price"),
                        "Last Updated": market.get("last_update")
                    })

    return pd.DataFrame(rows)
