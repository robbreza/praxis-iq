"""Lighthouse client configuration — USIO (first deployment). Configuration-driven and
ticker-agnostic by design: a new client is a new file like this one, no code changes."""

USIO = {
    "client_id": "usio",
    "ticker": "USIO",
    "name": "Usio, Inc.",
    "exchange": "NASDAQ",
    "cik": "1088034",
    "sector": "Payments / Fintech",

    # Benchmarks for the market/peer attribution model (adjust as data is wired).
    "benchmarks": {
        "broad_market": "SPY",
        "small_cap": "IWM",
        "sector": "IPAY",        # fintech/payments ETF proxy
    },

    # Business peers (from USIO's own competition set; dynamic mktcap/liquidity peers derived later).
    "business_peers": ["RPAY", "PSFE", "PAY", "CASS", "GDOT", "EVTC"],

    # Standard trading-day lookback conventions (Spec 1).
    "lookbacks_days": [21, 63, 126, 252],

    # Absorbability band inputs for the sector-appetite screen (micro-cap correction).
    "float_shares": None,        # wire from market_data
    "adv_shares": None,          # 20d average daily volume

    # Champion/challenger candidates for expected-return (Spec 1).
    "expected_return_models": ["naive", "ols_static", "ols_roll_63", "ols_roll_126", "ols_roll_252"],
}
