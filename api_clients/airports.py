"""
Turn what a visitor typed into an airport code.

"LKO" stays "LKO". "Lucknow" becomes "LKO". Unknown text raises ValueError so
the planner can explain instead of searching for nothing.
"""

import re

# City (or common alias) -> main airport. Not exhaustive; visitors can always
# type the 3-letter code for anywhere that is missing.
CITY_AIRPORTS = {
    # India
    "lucknow": "LKO", "delhi": "DEL", "new delhi": "DEL", "mumbai": "BOM", "bombay": "BOM",
    "bengaluru": "BLR", "bangalore": "BLR", "chennai": "MAA", "madras": "MAA", "kolkata": "CCU",
    "calcutta": "CCU", "hyderabad": "HYD", "pune": "PNQ", "ahmedabad": "AMD", "goa": "GOI",
    "jaipur": "JAI", "kochi": "COK", "cochin": "COK", "varanasi": "VNS", "srinagar": "SXR",
    "guwahati": "GAU", "patna": "PAT", "bhubaneswar": "BBI", "indore": "IDR", "nagpur": "NAG",
    "chandigarh": "IXC", "amritsar": "ATQ", "thiruvananthapuram": "TRV", "trivandrum": "TRV",
    "coimbatore": "CJB", "raipur": "RPR", "ranchi": "IXR", "dehradun": "DED", "udaipur": "UDR",
    "jodhpur": "JDH", "vijayawada": "VGA", "visakhapatnam": "VTZ", "vizag": "VTZ",
    "madurai": "IXM", "surat": "STV", "bhopal": "BHO", "leh": "IXL", "port blair": "IXZ",
    "jammu": "IXJ", "tirupati": "TIR", "mangaluru": "IXE", "mangalore": "IXE", "agartala": "IXA",
    # Asia and the Gulf
    "dubai": "DXB", "abu dhabi": "AUH", "doha": "DOH", "muscat": "MCT", "kuwait": "KWI",
    "bahrain": "BAH", "manama": "BAH", "riyadh": "RUH", "jeddah": "JED", "singapore": "SIN",
    "bangkok": "BKK", "phuket": "HKT", "kuala lumpur": "KUL", "jakarta": "CGK", "bali": "DPS",
    "denpasar": "DPS", "manila": "MNL", "hong kong": "HKG", "taipei": "TPE", "seoul": "ICN",
    "tokyo": "HND", "osaka": "KIX", "shanghai": "PVG", "beijing": "PEK", "hanoi": "HAN",
    "ho chi minh city": "SGN", "saigon": "SGN", "colombo": "CMB", "kathmandu": "KTM",
    "dhaka": "DAC", "male": "MLE", "maldives": "MLE", "tashkent": "TAS", "baku": "GYD",
    "tbilisi": "TBS", "almaty": "ALA", "tel aviv": "TLV", "istanbul": "IST",
    # Europe
    "london": "LHR", "manchester": "MAN", "edinburgh": "EDI", "dublin": "DUB", "paris": "CDG",
    "amsterdam": "AMS", "brussels": "BRU", "frankfurt": "FRA", "munich": "MUC", "berlin": "BER",
    "zurich": "ZRH", "geneva": "GVA", "vienna": "VIE", "prague": "PRG", "warsaw": "WAW",
    "budapest": "BUD", "rome": "FCO", "milan": "MXP", "venice": "VCE", "madrid": "MAD",
    "barcelona": "BCN", "lisbon": "LIS", "athens": "ATH", "copenhagen": "CPH", "stockholm": "ARN",
    "oslo": "OSL", "helsinki": "HEL", "moscow": "SVO",
    # Americas, Africa, Oceania
    "new york": "JFK", "nyc": "JFK", "boston": "BOS", "washington": "IAD", "chicago": "ORD",
    "miami": "MIA", "atlanta": "ATL", "houston": "IAH", "dallas": "DFW", "denver": "DEN",
    "las vegas": "LAS", "los angeles": "LAX", "san francisco": "SFO", "seattle": "SEA",
    "orlando": "MCO", "toronto": "YYZ", "vancouver": "YVR", "montreal": "YUL",
    "mexico city": "MEX", "sao paulo": "GRU", "rio de janeiro": "GIG", "buenos aires": "EZE",
    "lima": "LIM", "santiago": "SCL", "bogota": "BOG", "cairo": "CAI", "casablanca": "CMN",
    "nairobi": "NBO", "lagos": "LOS", "johannesburg": "JNB", "cape town": "CPT",
    "sydney": "SYD", "melbourne": "MEL", "auckland": "AKL",
}

CODE_CITIES = {}
for _city, _code in CITY_AIRPORTS.items():
    CODE_CITIES.setdefault(_code, _city.title())


def resolve_airport(text: str):
    """Return (airport_code, city_name). Raises ValueError if nothing matches."""
    cleaned = re.sub(r"\s+", " ", str(text or "").strip())
    if not cleaned:
        raise ValueError("Enter a city or a 3-letter airport code.")

    key = cleaned.lower()
    if key in CITY_AIRPORTS:
        code = CITY_AIRPORTS[key]
        return code, cleaned.title()

    if len(cleaned) == 3 and cleaned.isalpha():
        code = cleaned.upper()
        return code, CODE_CITIES.get(code, code)

    # "Delhi (DEL)" -> DEL
    bracketed = re.search(r"\(([A-Za-z]{3})\)", cleaned)
    if bracketed:
        code = bracketed.group(1).upper()
        return code, CODE_CITIES.get(code, code)

    # "Lucknow airport", "Delhi International Airport", "Mumbai, India"
    trimmed = re.sub(r"\b(international|intl|airport|city|india|uk|usa|uae)\b", " ", key)
    trimmed = re.sub(r"[^a-z ]", " ", trimmed)
    trimmed = re.sub(r"\s+", " ", trimmed).strip()
    if trimmed in CITY_AIRPORTS:
        return CITY_AIRPORTS[trimmed], trimmed.title()
    for name, code in CITY_AIRPORTS.items():
        if name in trimmed.split(",")[0]:
            return code, name.title()

    # Not in the table: ask Duffel, which knows thousands of airports and cities.
    try:
        from api_clients.duffel_client import resolve_place
        match = resolve_place(cleaned)
    except Exception:
        match = None
    if match:
        return match["iata_code"], match.get("city_name") or match.get("name") or cleaned.title()

    raise ValueError(f"Could not find an airport for '{cleaned}'. Try the 3-letter code.")
