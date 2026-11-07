"""
Base interface for all sports data providers.

Every API provider we connect will follow
this same structure.
"""


def fetch_odds(sport, markets=None, bookmakers=None):
    """
    Retrieve betting odds from a data provider.

    Parameters:
        sport: Sport to retrieve (NBA, NFL, etc.)
        markets: Markets to retrieve (player props, totals, etc.)
        bookmakers: Sportsbooks to retrieve (FanDuel, DraftKings, etc.)

    Returns:
        A standardized list of betting opportunities.
    """

    raise NotImplementedError(
        "A sports data provider has not been connected yet."
    )
