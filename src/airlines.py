"""
Static IATA airline-code -> name lookup, so alerts and the dashboard can
show "Delta Air Lines" instead of just "DL". Covers the carriers you'll
actually see on US domestic + common international routes. Falls back to
just showing the raw code for anything not in here, so nothing breaks if a
fare comes back on an airline we haven't listed.
"""
from __future__ import annotations

AIRLINES: dict[str, str] = {
    "AA": "American Airlines",
    "DL": "Delta Air Lines",
    "UA": "United Airlines",
    "WN": "Southwest Airlines",
    "B6": "JetBlue",
    "AS": "Alaska Airlines",
    "NK": "Spirit Airlines",
    "F9": "Frontier Airlines",
    "HA": "Hawaiian Airlines",
    "G4": "Allegiant Air",
    "SY": "Sun Country Airlines",
    "AC": "Air Canada",
    "WS": "WestJet",
    "BA": "British Airways",
    "VS": "Virgin Atlantic",
    "LH": "Lufthansa",
    "AF": "Air France",
    "KL": "KLM",
    "IB": "Iberia",
    "AZ": "ITA Airways",
    "LX": "SWISS",
    "OS": "Austrian Airlines",
    "TP": "TAP Air Portugal",
    "EI": "Aer Lingus",
    "AY": "Finnair",
    "SK": "SAS",
    "TK": "Turkish Airlines",
    "EK": "Emirates",
    "EY": "Etihad Airways",
    "QR": "Qatar Airways",
    "SV": "Saudia",
    "CX": "Cathay Pacific",
    "SQ": "Singapore Airlines",
    "JL": "Japan Airlines",
    "NH": "ANA",
    "KE": "Korean Air",
    "OZ": "Asiana Airlines",
    "CI": "China Airlines",
    "BR": "EVA Air",
    "QF": "Qantas",
    "NZ": "Air New Zealand",
    "LA": "LATAM Airlines",
    "AM": "Aeromexico",
    "CM": "Copa Airlines",
    "AV": "Avianca",
    "VY": "Vueling",
    "FR": "Ryanair",
    "U2": "easyJet",
    "W6": "Wizz Air",
    "DY": "Norwegian",
    "4O": "Interjet",
    "VB": "Viva Aerobus",
    "Y4": "Volaris",
}


def get_airline_name(code: str | None) -> str | None:
    if not code:
        return None
    return AIRLINES.get(code.upper(), code.upper())
