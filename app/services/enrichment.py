import httpx
import asyncio
from app.services.classification import (
    classify_age_group,
    get_top_nationality,
    validate_genderize_response,
    validate_agify_response,
    validate_nationalize_response,
)


class EnrichmentError(Exception):
    def __init__(self, api_name, message=None):
        self.api_name = api_name
        self.message = message or f'{api_name} returned an invalid response'


async def enrich_profile_data(name: str, timeout: int = 10) -> dict:
    """
    Call all 3 external APIs in parallel and return enriched data.
    Raises EnrichmentError if any API returns invalid response.
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        tasks = [
            client.get(f'https://api.genderize.io?name={name}'),
            client.get(f'https://api.agify.io?name={name}'),
            client.get(f'https://api.nationalize.io?name={name}'),
        ]
        responses = await asyncio.gather(*tasks)

    gender_response = responses[0].json() if responses[0].status_code == 200 else {}
    agify_response = responses[1].json() if responses[1].status_code == 200 else {}
    nationalize_response = responses[2].json() if responses[2].status_code == 200 else {}

    # Validate Genderize
    if not validate_genderize_response(gender_response):
        raise EnrichmentError('Genderize')

    # Validate Agify
    if not validate_agify_response(agify_response):
        raise EnrichmentError('Agify')

    # Validate Nationalize
    if not validate_nationalize_response(nationalize_response):
        raise EnrichmentError('Nationalize')

    gender = gender_response.get('gender')
    gender_probability = gender_response.get('probability')
    sample_size = gender_response.get('count')

    age = agify_response.get('age')
    age_group = classify_age_group(age)

    country_id, country_probability = get_top_nationality(nationalize_response)

    return {
        'gender': gender,
        'gender_probability': gender_probability,
        'sample_size': sample_size,
        'age': age,
        'age_group': age_group,
        'country_id': country_id,
        'country_probability': country_probability,
        # 'api_responses': {
        #     'genderize': gender_response,
        #     'agify': agify_response,
        #     'nationalize': nationalize_response,
        # }
    }
