import csv
import io
import math
from datetime import datetime
from urllib.parse import urlencode

from flask import Blueprint, Response, current_app, jsonify, request

from app import db, limiter
from app.models import Profile
from app.services.auth import require_api_version, require_auth, require_csrf
from app.services.enrichment import EnrichmentError, enrich_profile_data
from app.services.profile_query import (
    apply_sort_and_pagination,
    build_profile_list_query,
    parse_profile_list_params,
    parse_profile_search_params,
)
from app.services.profile_search_parser import parse_nl_profile_query
from app.services.profile_serialization import serialize_profile_list_item

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
@limiter.limit('60 per minute')
@require_auth(roles=['admin'])
async def create_profile():
    csrf_error = require_csrf()
    if csrf_error:
        return csrf_error

    version_error = require_api_version()
    if version_error:
        return version_error

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
        country_name=enriched.get('country_name'),
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
@limiter.limit('60 per minute')
@require_auth(roles=['admin', 'analyst'])
def list_profiles():
    version_error = require_api_version()
    if version_error:
        return version_error

    validation_error = _validate_numeric_params(request.args)
    if validation_error:
        return error_response(validation_error, 422)

    params = parse_profile_list_params(request.args)
    base_query = build_profile_list_query(params)
    total = base_query.count()
    profiles = apply_sort_and_pagination(base_query, params).all()
    data = [serialize_profile_list_item(p) for p in profiles]

    total_pages = math.ceil(total / params.limit) if total else 0

    def build_link(page_value):
        query = request.args.to_dict(flat=True)
        query['page'] = page_value
        query['limit'] = params.limit
        return f'{request.path}?{urlencode(query)}'

    links = {
        'self': build_link(params.page),
        'next': build_link(params.page + 1) if params.page < total_pages else None,
        'prev': build_link(params.page - 1) if params.page > 1 and total_pages > 0 else None,
    }

    return jsonify({
        'status': 'success',
        'page': params.page,
        'limit': params.limit,
        'total': total,
        'total_pages': total_pages,
        'links': links,
        'data': data
    }), 200


@api_bp.route('/profiles/search', methods=['GET'])
@limiter.limit('60 per minute')
@require_auth(roles=['admin', 'analyst'])
def search_profiles():
    version_error = require_api_version()
    if version_error:
        return version_error

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

    total_pages = math.ceil(total / params.limit) if total else 0

    def build_link(page_value):
        query = request.args.to_dict(flat=True)
        query['page'] = page_value
        query['limit'] = params.limit
        return f'{request.path}?{urlencode(query)}'

    links = {
        'self': build_link(params.page),
        'next': build_link(params.page + 1) if params.page < total_pages else None,
        'prev': build_link(params.page - 1) if params.page > 1 and total_pages > 0 else None,
    }

    return jsonify({
        'status': 'success',
        'page': params.page,
        'limit': params.limit,
        'total': total,
        'total_pages': total_pages,
        'links': links,
        'data': data
    }), 200


@api_bp.route('/profiles/<id>', methods=['GET'])
@limiter.limit('60 per minute')
@require_auth(roles=['admin', 'analyst'])
def get_profile(id):
    version_error = require_api_version()
    if version_error:
        return version_error

    profile = Profile.query.get(id)
    if not profile:
        return error_response('Profile not found', 404)
    return success_response(profile.to_dict())


@api_bp.route('/profiles/by-name/<name>', methods=['GET'])
@limiter.limit('60 per minute')
@require_auth(roles=['admin', 'analyst'])
def get_profile_by_name(name):
    version_error = require_api_version()
    if version_error:
        return version_error

    if not name or not name.strip():
        return error_response('Missing or empty name', 400)

    profile = Profile.query.filter(db.func.lower(Profile.name) == name.lower()).first()
    if not profile:
        return error_response('Profile not found', 404)
    return success_response(profile.to_dict())


@api_bp.route('/profiles/<id>', methods=['PUT'])
@limiter.limit('60 per minute')
@require_auth(roles=['admin'])
async def update_profile(id):
    csrf_error = require_csrf()
    if csrf_error:
        return csrf_error

    version_error = require_api_version()
    if version_error:
        return version_error

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
        profile.country_name = enriched.get('country_name')
        profile.country_probability = enriched['country_probability']
        # profile.api_responses = enriched['api_responses']

    db.session.commit()
    return success_response(profile.to_dict())


@api_bp.route('/profiles/<id>', methods=['DELETE'])
@limiter.limit('60 per minute')
@require_auth(roles=['admin'])
def delete_profile(id):
    csrf_error = require_csrf()
    if csrf_error:
        return csrf_error

    version_error = require_api_version()
    if version_error:
        return version_error

    profile = Profile.query.get(id)
    if not profile:
        return error_response('Profile not found', 404)

    db.session.delete(profile)
    db.session.commit()
    return '', 204


@api_bp.route('/profiles/stats', methods=['GET'])
@limiter.limit('60 per minute')
@require_auth(roles=['admin', 'analyst'])
def get_stats():
    version_error = require_api_version()
    if version_error:
        return version_error

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


@api_bp.route('/profiles/export', methods=['GET'])
@limiter.limit('60 per minute')
@require_auth(roles=['admin', 'analyst'])
def export_profiles():
    version_error = require_api_version()
    if version_error:
        return version_error

    export_format = request.args.get('format', '').lower()
    if export_format != 'csv':
        return error_response('Unsupported export format', 400)

    validation_error = _validate_numeric_params(request.args)
    if validation_error:
        return error_response(validation_error, 422)

    params = parse_profile_list_params(request.args)
    query = build_profile_list_query(params)
    sort_column = {'age': Profile.age, 'created_at': Profile.created_at, 'gender_probability': Profile.gender_probability}.get(
        params.sort_by, Profile.created_at
    )
    query = query.order_by(sort_column.asc() if params.order == 'asc' else sort_column.desc())
    rows = query.all()

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=',')
    writer.writerow(
        [
            'id',
            'name',
            'gender',
            'gender_probability',
            'age',
            'age_group',
            'country_id',
            'country_name',
            'country_probability',
            'created_at',
        ]
    )
    for profile in rows:
        item = serialize_profile_list_item(profile)
        writer.writerow(
            [
                item['id'],
                item['name'],
                item['gender'],
                item['gender_probability'],
                item['age'],
                item['age_group'],
                item['country_id'],
                item['country_name'],
                item['country_probability'],
                item['created_at'],
            ]
        )

    output = buffer.getvalue()
    filename = f'profiles_{int(datetime.utcnow().timestamp())}.csv'
    return Response(
        output,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )
