import re

# ──────────────────────────── country lookup ────────────────────────────

COUNTRY_MAP = {
    # African countries (full coverage)
    "nigeria": "NG", "nigerian": "NG",
    "kenya": "KE", "kenyan": "KE",
    "ghana": "GH", "ghanaian": "GH",
    "south africa": "ZA", "south african": "ZA",
    "ethiopia": "ET", "ethiopian": "ET",
    "egypt": "EG", "egyptian": "EG",
    "tanzania": "TZ", "tanzanian": "TZ",
    "uganda": "UG", "ugandan": "UG",
    "algeria": "DZ", "algerian": "DZ",
    "morocco": "MA", "moroccan": "MA",
    "angola": "AO", "angolan": "AO",
    "mozambique": "MZ", "mozambican": "MZ",
    "cameroon": "CM", "cameroonian": "CM",
    "zimbabwe": "ZW", "zimbabwean": "ZW",
    "senegal": "SN", "senegalese": "SN",
    "zambia": "ZM", "zambian": "ZM",
    "malawi": "MW", "malawian": "MW",
    "rwanda": "RW", "rwandan": "RW",
    "somalia": "SO", "somali": "SO",
    "sudan": "SD", "sudanese": "SD",
    "south sudan": "SS", "south sudanese": "SS",
    "tunisia": "TN", "tunisian": "TN",
    "chad": "TD", "chadian": "TD",
    "guinea": "GN", "guinean": "GN",
    "benin": "BJ", "beninese": "BJ",
    "togo": "TG", "togolese": "TG",
    "sierra leone": "SL", "sierra leonean": "SL",
    "liberia": "LR", "liberian": "LR",
    "mali": "ML", "malian": "ML",
    "burkina faso": "BF", "burkinabe": "BF",
    "niger": "NE", "nigerien": "NE",
    "ivory coast": "CI", "ivorian": "CI",
    "cote d'ivoire": "CI",
    "madagascar": "MG", "malagasy": "MG",
    "botswana": "BW", "motswana": "BW",
    "namibia": "NA", "namibian": "NA",
    "mauritius": "MU", "mauritian": "MU",
    "lesotho": "LS", "basotho": "LS",
    "swaziland": "SZ", "swazi": "SZ",
    "eswatini": "SZ",
    "eritrea": "ER", "eritrean": "ER",
    "djibouti": "DJ", "djiboutian": "DJ",
    "comoros": "KM", "comorian": "KM",
    "cape verde": "CV", "cabo verde": "CV",
    "gabon": "GA", "gabonese": "GA",
    "congo": "CG", "congolese": "CG",
    "democratic republic of congo": "CD",
    "dr congo": "CD",
    "equatorial guinea": "GQ",
    "central african republic": "CF",
    "gambia": "GM", "gambian": "GM",
    "guinea-bissau": "GW",
    "sao tome and principe": "ST",
    "seychelles": "SC", "seychellois": "SC",
    "libya": "LY", "libyan": "LY",
    "mauritania": "MR", "mauritanian": "MR",
    # Major world countries
    "united states": "US", "american": "US", "usa": "US",
    "united kingdom": "GB", "british": "GB", "uk": "GB",
    "france": "FR", "french": "FR",
    "germany": "DE", "german": "DE",
    "canada": "CA", "canadian": "CA",
    "australia": "AU", "australian": "AU",
    "india": "IN", "indian": "IN",
    "china": "CN", "chinese": "CN",
    "brazil": "BR", "brazilian": "BR",
    "japan": "JP", "japanese": "JP",
    "italy": "IT", "italian": "IT",
    "spain": "ES", "spanish": "ES",
    "russia": "RU", "russian": "RU",
    "mexico": "MX", "mexican": "MX",
    "indonesia": "ID", "indonesian": "ID",
    "pakistan": "PK", "pakistani": "PK",
    "bangladesh": "BD", "bangladeshi": "BD",
    "turkey": "TR", "turkish": "TR",
    "saudi arabia": "SA", "saudi": "SA",
    "argentina": "AR", "argentinian": "AR",
    "colombia": "CO", "colombian": "CO",
    "ukraine": "UA", "ukrainian": "UA",
    "netherlands": "NL", "dutch": "NL",
    "sweden": "SE", "swedish": "SE",
    "norway": "NO", "norwegian": "NO",
    "denmark": "DK", "danish": "DK",
    "finland": "FI", "finnish": "FI",
    "poland": "PL", "polish": "PL",
    "portugal": "PT", "portuguese": "PT",
}

# Sort by length descending to match longest first (e.g. "south africa" before "africa")
COUNTRY_KEYS = sorted(COUNTRY_MAP.keys(), key=len, reverse=True)


def parse_query(query: str) -> dict | None:
    """
    Parses a natural language query into filter parameters.
    Returns a dict of filter params, or None if nothing matched.
    """
    q = query.lower().strip()
    filters = {}

    # ── Gender ────────────────────────────────────────────────────
    has_male = bool(re.search(r"\b(male|males|man|men|boy|boys)\b", q))
    has_female = bool(re.search(r"\b(female|females|woman|women|girl|girls)\b", q))

    if has_male and not has_female:
        filters["gender"] = "male"
    elif has_female and not has_male:
        filters["gender"] = "female"
    # both → no gender filter

    # ── Age group ─────────────────────────────────────────────────
    if re.search(r"\b(child|children|kid|kids)\b", q):
        filters["age_group"] = "child"
    elif re.search(r"\b(teenager|teenagers|teen|teens|adolescent)\b", q):
        filters["age_group"] = "teenager"
    elif re.search(r"\b(adult|adults)\b", q):
        filters["age_group"] = "adult"
    elif re.search(r"\b(senior|seniors|elderly|old)\b", q):
        filters["age_group"] = "senior"
    elif re.search(r"\b(young|youth)\b", q):
        # "young" maps to a numeric range, not a stored age_group
        filters["min_age"] = 16
        filters["max_age"] = 24

    # ── Age comparisons ───────────────────────────────────────────
    m = re.search(r"\bbetween\s+(\d+)\s+and\s+(\d+)\b", q)
    if m:
        filters["min_age"] = int(m.group(1))
        filters["max_age"] = int(m.group(2))
    else:
        m_above = re.search(r"\b(above|over|older than)\s+(\d+)\b", q)
        if m_above:
            filters["min_age"] = int(m_above.group(2))

        m_below = re.search(r"\b(below|under|younger than)\s+(\d+)\b", q)
        if m_below:
            filters["max_age"] = int(m_below.group(2))

        m_aged = re.search(r"\baged\s+(\d+)\b", q)
        if m_aged:
            filters["min_age"] = int(m_aged.group(1))
            filters["max_age"] = int(m_aged.group(1))

    # ── Country ───────────────────────────────────────────────────
    for country_key in COUNTRY_KEYS:
        pattern = r"\b" + re.escape(country_key) + r"\b"
        if re.search(pattern, q):
            filters["country_id"] = COUNTRY_MAP[country_key]
            break

    return filters if filters else None
