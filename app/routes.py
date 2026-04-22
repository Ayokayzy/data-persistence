from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models import Profile
from app.services.enrichment import enrich_profile_data, EnrichmentError
from app.services.profile_query import (
    parse_profile_list_params,
    parse_profile_search_params,
    build_profile_list_query,
    apply_sort_and_pagination,
)
from app.services.profile_serialization import serialize_profile_list_item
from app.services.profile_search_parser import parse_nl_profile_query

api_bp = Blueprint('api', __name__)


def success_response(data, message=None, status_code=200):
    response = {'status': 'success'}
    if message:
        response['message'] = message
    response['data'] = data
    return jsonify(response), status_code


def error_response(message, status_code):
    return jsonify({
        'status': 'error',
        'message': message
    }), status_code


@api_bp.route('/profiles', methods=['POST'])
async def create_profile():
    data = request.get_json()
    if not data or 'name' not in data:
        return error_response('Missing or empty name', 400)

    name = data.get('name')
    if name is None:
        return error_response('Missing or empty name', 400)

    if not isinstance(name, str):
        return error_response('Invalid type', 422)

    name = name.strip()
    if not name:
        return error_response('Missing or empty name', 400)

    if len(name) > 255:
        return error_response('Name too long (max 255 characters)', 400)

    # Case-insensitive duplicate check
    existing = Profile.query.filter(db.func.lower(Profile.name) == name.lower()).first()
    if existing:
        return success_response(existing.to_dict(), message='Profile already exists', status_code=200)

    try:
        enriched = await enrich_profile_data(name, timeout=current_app.config['API_TIMEOUT'])
    except EnrichmentError as e:
        return error_response(f'{e.api_name} returned an invalid response', 502)
    except Exception as e:
        return error_response(f'Reached timeout or server error: {str(e)}', 502)

    profile = Profile(
        name=name,
        gender=enriched['gender'],
        gender_probability=enriched['gender_probability'],
        sample_size=enriched['sample_size'],
        age=enriched['age'],
        age_group=enriched['age_group'],
        country_id=enriched['country_id'],
        country_probability=enriched['country_probability'],
        # api_responses=enriched['api_responses'],
    )

    db.session.add(profile)
    db.session.commit()
    return success_response(profile.to_dict(), status_code=201)


def _validate_numeric_params(args):
    """Return an error message if any numeric query param has a non-numeric value."""
    int_params = ('min_age', 'max_age', 'page', 'limit')
    float_params = ('min_gender_probability', 'min_country_probability')
    for key in int_params:
        val = args.get(key)
        if val is not None:
            try:
                int(val)
            except (TypeError, ValueError):
                return 'Invalid query parameters'
    for key in float_params:
        val = args.get(key)
        if val is not None:
            try:
                float(val)
            except (TypeError, ValueError):
                return 'Invalid query parameters'
    return None


@api_bp.route('/profiles', methods=['GET'])
def list_profiles():
    validation_error = _validate_numeric_params(request.args)
    if validation_error:
        return error_response(validation_error, 422)

    params = parse_profile_list_params(request.args)
    base_query = build_profile_list_query(params)
    total = base_query.count()
    profiles = apply_sort_and_pagination(base_query, params).all()
    data = [serialize_profile_list_item(p) for p in profiles]

    return jsonify({
        'status': 'success',
        'page': params.page,
        'limit': params.limit,
        'total': total,
        'data': data
    }), 200


@api_bp.route('/profiles/search', methods=['GET'])
def search_profiles():
    q = request.args.get('q', '')
    if not q or not q.strip():
        return error_response('Unable to interpret query', 400)

    parsed_filters = parse_nl_profile_query(q)
    if not parsed_filters:
        return error_response('Unable to interpret query', 400)

    validation_error = _validate_numeric_params(request.args)
    if validation_error:
        return error_response(validation_error, 422)

    params = parse_profile_search_params(request.args, parsed_filters)
    base_query = build_profile_list_query(params)
    total = base_query.count()
    profiles = apply_sort_and_pagination(base_query, params).all()
    data = [serialize_profile_list_item(p) for p in profiles]

    return jsonify({
        'status': 'success',
        'page': params.page,
        'limit': params.limit,
        'total': total,
        'data': data
    }), 200


@api_bp.route('/profiles/<id>', methods=['GET'])
def get_profile(id):
    profile = Profile.query.get(id)
    if not profile:
        return error_response('Profile not found', 404)
    return success_response(profile.to_dict())


@api_bp.route('/profiles/by-name/<name>', methods=['GET'])
def get_profile_by_name(name):
    if not name or not name.strip():
        return error_response('Missing or empty name', 400)

    profile = Profile.query.filter(db.func.lower(Profile.name) == name.lower()).first()
    if not profile:
        return error_response('Profile not found', 404)
    return success_response(profile.to_dict())


@api_bp.route('/profiles/<id>', methods=['PUT'])
async def update_profile(id):
    profile = Profile.query.get(id)
    if not profile:
        return error_response('Profile not found', 404)

    data = request.get_json() or {}
    new_name = data.get('name', '').strip() if data.get('name') else None

    if new_name:
        if not isinstance(new_name, str):
            return error_response('Invalid type', 422)

        if len(new_name) > 255:
            return error_response('Name too long (max 255 characters)', 400)

        # Check for duplicate (excluding current record)
        duplicate = Profile.query.filter(
            db.func.lower(Profile.name) == new_name.lower(),
            Profile.id != id
        ).first()
        if duplicate:
            return error_response('Name already exists', 409)

        profile.name = new_name

        # Re-fetch enrichment if name changed
        try:
            enriched = await enrich_profile_data(new_name, timeout=current_app.config['API_TIMEOUT'])
        except EnrichmentError as e:
            return error_response(f'{e.api_name} returned an invalid response', 502)
        except Exception as e:
            return error_response(f'Reached timeout or server error: {str(e)}', 502)

        profile.gender = enriched['gender']
        profile.gender_probability = enriched['gender_probability']
        profile.sample_size = enriched['sample_size']
        profile.age = enriched['age']
        profile.age_group = enriched['age_group']
        profile.country_id = enriched['country_id']
        profile.country_probability = enriched['country_probability']
        # profile.api_responses = enriched['api_responses']

    db.session.commit()
    return success_response(profile.to_dict())


@api_bp.route('/profiles/<id>', methods=['DELETE'])
def delete_profile(id):
    profile = Profile.query.get(id)
    if not profile:
        return error_response('Profile not found', 404)

    db.session.delete(profile)
    db.session.commit()
    return '', 204


@api_bp.route('/profiles/stats', methods=['GET'])
def get_stats():
    total = Profile.query.count()

    age_groups = db.session.query(
        Profile.age_group, db.func.count(Profile.id)
    ).filter(Profile.age_group.isnot(None)).group_by(Profile.age_group).all()

    genders = db.session.query(
        Profile.gender, db.func.count(Profile.id)
    ).filter(Profile.gender.isnot(None)).group_by(Profile.gender).all()

    return success_response({
        'total': total,
        'age_group_distribution': {ag: count for ag, count in age_groups},
        'gender_distribution': {g: count for g, count in genders},
    })
