def classify_age_group(age):
    if age is None:
        return None
    if 0 <= age <= 12:
        return 'child'
    elif 13 <= age <= 19:
        return 'teenager'
    elif 20 <= age <= 59:
        return 'adult'
    elif age >= 60:
        return 'senior'
    return None


def get_top_nationality(nationalize_response):
    if not nationalize_response or 'country' not in nationalize_response:
        return None, None

    countries = nationalize_response.get('country', [])
    if not countries:
        return None, None

    # Sort by probability descending and pick the top
    top = max(countries, key=lambda x: x.get('probability', 0))
    return top.get('country_id'), top.get('probability')


def validate_genderize_response(response: dict) -> bool:
    """Genderize must return valid gender and count > 0."""
    gender = response.get('gender')
    count = response.get('count', 0)
    return gender is not None and count > 0


def validate_agify_response(response: dict) -> bool:
    """Agify must return valid age."""
    return response.get('age') is not None


def validate_nationalize_response(response: dict) -> bool:
    """Nationalize must return country data."""
    countries = response.get('country', [])
    return bool(countries)
