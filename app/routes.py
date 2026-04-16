from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models import Profile
from app.services.enrichment import enrich_profile_data, EnrichmentError

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


@api_bp.route('/profiles', methods=['GET'])
def list_profiles():
    query = Profile.query

    # Optional filters (case-insensitive)
    gender = request.args.get('gender')
    if gender:
        query = query.filter(db.func.lower(Profile.gender) == gender.lower())

    country_id = request.args.get('country_id')
    if country_id:
        query = query.filter(db.func.lower(Profile.country_id) == country_id.lower())

    age_group = request.args.get('age_group')
    if age_group:
        query = query.filter(db.func.lower(Profile.age_group) == age_group.lower())

    profiles = query.order_by(Profile.created_at.desc()).all()

    # Simplified profile objects for list view
    data = [{
        'id': p.id,
        'name': p.name,
        'gender': p.gender,
        'age': p.age,
        'age_group': p.age_group,
        'country_id': p.country_id,
    } for p in profiles]

    return jsonify({
        'status': 'success',
        'count': len(data),
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
