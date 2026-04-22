import re


# Full country name → ISO code mapping (all countries in seed data + common aliases)
COUNTRY_NAME_TO_CODE = {
    'algeria': 'DZ',
    'angola': 'AO',
    'australia': 'AU',
    'benin': 'BJ',
    'botswana': 'BW',
    'brazil': 'BR',
    'burkina faso': 'BF',
    'burundi': 'BI',
    'cameroon': 'CM',
    'canada': 'CA',
    'cape verde': 'CV',
    'central african republic': 'CF',
    'chad': 'TD',
    'china': 'CN',
    'comoros': 'KM',
    "cote d'ivoire": 'CI',
    "côte d'ivoire": 'CI',
    'ivory coast': 'CI',
    'djibouti': 'DJ',
    'dr congo': 'CD',
    'democratic republic of congo': 'CD',
    'democratic republic of the congo': 'CD',
    'egypt': 'EG',
    'equatorial guinea': 'GQ',
    'eritrea': 'ER',
    'eswatini': 'SZ',
    'swaziland': 'SZ',
    'ethiopia': 'ET',
    'france': 'FR',
    'gabon': 'GA',
    'gambia': 'GM',
    'the gambia': 'GM',
    'germany': 'DE',
    'ghana': 'GH',
    'guinea': 'GN',
    'guinea-bissau': 'GW',
    'india': 'IN',
    'japan': 'JP',
    'kenya': 'KE',
    'lesotho': 'LS',
    'liberia': 'LR',
    'libya': 'LY',
    'madagascar': 'MG',
    'malawi': 'MW',
    'mali': 'ML',
    'mauritania': 'MR',
    'mauritius': 'MU',
    'morocco': 'MA',
    'mozambique': 'MZ',
    'namibia': 'NA',
    'niger': 'NE',
    'nigeria': 'NG',
    'republic of the congo': 'CG',
    'congo': 'CG',
    'rwanda': 'RW',
    'senegal': 'SN',
    'seychelles': 'SC',
    'sierra leone': 'SL',
    'somalia': 'SO',
    'south africa': 'ZA',
    'south sudan': 'SS',
    'sudan': 'SD',
    'sao tome and principe': 'ST',
    'são tomé and príncipe': 'ST',
    'tanzania': 'TZ',
    'togo': 'TG',
    'tunisia': 'TN',
    'uganda': 'UG',
    'united kingdom': 'GB',
    'uk': 'GB',
    'britain': 'GB',
    'great britain': 'GB',
    'united states': 'US',
    'usa': 'US',
    'us': 'US',
    'america': 'US',
    'western sahara': 'EH',
    'zambia': 'ZM',
    'zimbabwe': 'ZW',
}

# All valid ISO codes present in seed data (for direct code matching)
VALID_COUNTRY_CODES = {v for v in COUNTRY_NAME_TO_CODE.values()}


def _normalize_query(query: str) -> str:
    return re.sub(r'\s+', ' ', query.strip().lower())


def _extract_country(normalized: str):
    """Return ISO code if a country name or code is found after 'from', else None."""
    from_match = re.search(r'\bfrom\s+([a-z][a-z\s\'\-\.]+?)(?:\s+(?:sorted|page|limit|order|above|over|under|below|aged?|with|and|who|that)|$)', normalized)
    if not from_match:
        # Try bare "from <word>" at end of string
        from_match = re.search(r'\bfrom\s+([a-z][a-z\s\'\-\.]+)', normalized)
    if not from_match:
        return None

    country_text = from_match.group(1).strip().rstrip('.,')

    # Try direct ISO code match (2 uppercase letters) — input already lowercased
    if re.fullmatch(r'[a-z]{2}', country_text):
        code = country_text.upper()
        if code in VALID_COUNTRY_CODES:
            return code

    # Try longest-match first against name dict
    if country_text in COUNTRY_NAME_TO_CODE:
        return COUNTRY_NAME_TO_CODE[country_text]

    # Try progressively shorter phrases (handles trailing noise)
    words = country_text.split()
    for length in range(len(words), 0, -1):
        candidate = ' '.join(words[:length])
        if candidate in COUNTRY_NAME_TO_CODE:
            return COUNTRY_NAME_TO_CODE[candidate]

    return None


def parse_nl_profile_query(query: str):
    if not isinstance(query, str):
        return None

    normalized = _normalize_query(query)
    if not normalized:
        return None

    parsed = {
        'gender': None,
        'age_group': None,
        'country_id': None,
        'min_age': None,
        'max_age': None,
        'min_gender_probability': None,
        'min_country_probability': None,
    }
    interpreted = False

    # Gender — support male/female/men/women/boys/girls
    has_male = bool(re.search(r'\b(male|males|men|man|boys|boy)\b', normalized))
    has_female = bool(re.search(r'\b(female|females|women|woman|girls|girl)\b', normalized))

    if has_male and not has_female:
        parsed['gender'] = 'male'
        interpreted = True
    elif has_female and not has_male:
        parsed['gender'] = 'female'
        interpreted = True
    elif has_male and has_female:
        # Both present — drop gender constraint but still count as interpreted
        interpreted = True

    # Age group
    age_group_terms = ('child', 'teenager', 'adult', 'senior')
    for term in age_group_terms:
        if re.search(rf'\b{term}(s)?\b', normalized):
            parsed['age_group'] = term
            interpreted = True
            break

    # "young" → 16–24
    if re.search(r'\byoung\b', normalized):
        parsed['min_age'] = 16
        parsed['max_age'] = 24
        interpreted = True

    # above/over N → min_age
    min_age_match = re.search(r'\b(?:above|over)\s+(\d{1,3})\b', normalized)
    if min_age_match:
        parsed['min_age'] = int(min_age_match.group(1))
        interpreted = True

    # under/below N → max_age
    max_age_match = re.search(r'\b(?:under|below)\s+(\d{1,3})\b', normalized)
    if max_age_match:
        parsed['max_age'] = int(max_age_match.group(1))
        interpreted = True

    # aged N / age N → exact age as both min and max
    exact_age_match = re.search(r'\bage[d]?\s+(\d{1,3})\b', normalized)
    if exact_age_match:
        age = int(exact_age_match.group(1))
        parsed['min_age'] = age
        parsed['max_age'] = age
        interpreted = True

    # Country
    country_id = _extract_country(normalized)
    if country_id:
        parsed['country_id'] = country_id
        interpreted = True

    if not interpreted:
        return None

    return parsed
