"""APPROXIMATE reference tables. Good enough for first estimates, NOT for a binding quote.
Check sun hours with NREL PVWatts and use the customer's real bill rate before sending anything."""

# Typical annual-average peak sun hours per day (fixed tilt), rounded.
SUN_HOURS = {
    "AZ": 6.5, "NV": 6.4, "NM": 6.4, "CA": 5.8, "UT": 5.6, "CO": 5.5, "TX": 5.3, "FL": 5.3,
    "SC": 5.0, "GA": 4.9, "NC": 4.8, "VA": 4.6, "NJ": 4.4, "IL": 4.3, "MA": 4.2, "PA": 4.1,
    "NY": 4.0, "OH": 4.0, "OR": 4.0, "MI": 3.9, "WA": 3.6,
}
# Rough residential average price, $/kWh. Replace with the customer's actual rate.
RATES = {
    "AZ": 0.15, "NV": 0.15, "NM": 0.17, "CA": 0.32, "UT": 0.12, "CO": 0.15, "TX": 0.16, "FL": 0.15,
    "SC": 0.15, "GA": 0.15, "NC": 0.14, "VA": 0.15, "NJ": 0.20, "IL": 0.17, "MA": 0.31, "PA": 0.18,
    "NY": 0.25, "OH": 0.17, "OR": 0.14, "MI": 0.20, "WA": 0.12,
}
