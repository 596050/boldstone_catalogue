"""Explicit instrument identities; no substitution of a proxy for its underlying."""

# All twelve month codes are searched, including less liquid delivery months.
# This is a declared search space, not a claim all such contracts were listed.
MONTHS = "FGHJKMNQUVXZ"
ROOTS = (
    ("QGC", "commodities/gold", "COMEX gold futures"),
    ("QCL", "commodities/oil/wti", "NYMEX WTI crude futures"),
    ("EB", "commodities/oil/brent", "ICE Brent crude futures"),
    ("@TU", "treasuries/2_year", "2-year Treasury note futures"),
    ("@FV", "treasuries/5_year", "5-year Treasury note futures"),
    ("@TY", "treasuries/10_year", "10-year Treasury note futures"),
    ("@US", "treasuries/bond", "US Treasury bond futures"),
    ("@TN", "treasuries/ultra_10_year", "Ultra 10-year Treasury note futures"),
    ("@UB", "treasuries/ultra_bond", "Ultra Treasury bond futures"),
    ("@VX", "volatility/vix_futures", "VIX futures, not the cash VIX index"),
    ("@DX", "currencies/us_dollar_index", "US dollar index futures"),
    ("@FF", "rates/fed_funds_futures", "30-day Fed Funds futures"),
    ("@SR3", "rates/sofr_futures", "Three-month SOFR futures"),
)

SERIES = (
    ("XAUUSD.FXCM", "commodities/gold/spot/fxcm", "FXCM gold/USD spot", "spot"),
    ("XAUUSD.COMP", "commodities/gold/spot/tenfore", "Tenfore gold/USD composite; may be discontinued", "spot"),
    ("VIX.XO", "volatility/vix", "S&P 500 implied volatility", "index"),
    ("MOVE.X", "volatility/move", "ICE bond market volatility", "index"),
    ("VVIX.XO", "volatility/vvix", "Volatility of VIX", "index"),
    ("SKEW.XO", "volatility/skew", "Option-implied tail-risk pricing", "index"),
    ("VIX9D.XO", "volatility/vix_9_day", "9-day implied volatility", "index"),
    ("VIX3M.XO", "volatility/vix_3_month", "3-month implied volatility", "index"),
    ("OVX.XO", "volatility/oil_etf", "USO ETF option-implied volatility, not oil prices", "index"),
    ("GVZ.XO", "volatility/gold_etf", "GLD ETF option-implied volatility, not gold prices", "index"),
    ("IRX.XO", "rates/treasury_yields/13_week", "13-week Treasury yield index, not bond prices", "yield_index"),
    ("FVX.XO", "rates/treasury_yields/5_year", "5-year Treasury yield index", "yield_index"),
    ("TNX.XO", "rates/treasury_yields/10_year", "10-year Treasury yield index", "yield_index"),
    ("TYX.XO", "rates/treasury_yields/30_year", "30-year Treasury yield index", "yield_index"),
    ("EFFR.X", "rates/effective_fed_funds", "Effective Fed Funds rate; release-driven", "published_rate"),
    ("SOFR.X", "rates/sofr", "SOFR; release-driven", "published_rate"),
    ("PRIME.X", "rates/prime", "Prime rate; release-driven", "published_rate"),
    ("MTG30YR.X", "rates/mortgage_30_year", "Mortgage rate; possibly stale", "published_rate"),
    ("PCRATIO.Z", "market_breadth/put_call_ratio", "CBOE put/call ratio; possibly discontinued", "breadth"),
    ("JTYT.Z", "market_breadth/nyse_only_tick", "NYSE-only net tick", "breadth"),
    ("JTNT.Z", "market_breadth/nyse_tick", "NYSE net tick", "breadth"),
    ("TRIN.Z", "market_breadth/nyse_trin", "NYSE TRIN", "breadth"),
    ("IINA.Z", "market_breadth/nyse_advances", "NYSE advancing issues", "breadth"),
    ("IIND.Z", "market_breadth/nyse_declines", "NYSE declining issues", "breadth"),
)

GUIDES = ["https://iqhelp.dtn.com/api/"] + [
    "https://ws1.dtn.com/IQ/Guide/" + name for name in (
        "futures_comex_gbx.html", "futures_nymex_gbx.html", "futures_iceec.html",
        "futures_cbot_gbx.html", "futures_cme_gbx.html", "futures_cfe.html",
        "futures_icefu.html", "forex_fxcm.html", "indices_cboe.html",
        "indices_nyse_global.html", "indices_rates.html", "stats_all.html",
    )
]
