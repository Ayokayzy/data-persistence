from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app import db
from app.models import Profile


ALLOWED_SORT_FIELDS = {
    'age': Profile.age,
    'created_at': Profile.created_at,
    'gender_probability': Profile.gender_probability,
}
ALLOWED_ORDER_FIELDS = {'asc', 'desc'}
DEFAULT_SORT_BY = 'created_at'
DEFAULT_ORDER = 'desc'
DEFAULT_PAGE = 1
DEFAULT_LIMIT = 10
MAX_LIMIT = 50


def _parse_int(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class ProfileListParams:
    gender: Optional[str]
    age_group: Optional[str]
    country_id: Optional[str]
    min_age: Optional[int]
    max_age: Optional[int]
    min_gender_probability: Optional[float]
    min_country_probability: Optional[float]
    sort_by: str
    order: str
    page: int
    limit: int


def parse_profile_list_params(args) -> ProfileListParams:
    sort_by = args.get('sort_by', DEFAULT_SORT_BY)
    if sort_by not in ALLOWED_SORT_FIELDS:
        sort_by = DEFAULT_SORT_BY

    order = args.get('order', DEFAULT_ORDER)
    if not isinstance(order, str):
        order = DEFAULT_ORDER
    else:
        order = order.lower()
        if order not in ALLOWED_ORDER_FIELDS:
            order = DEFAULT_ORDER

    page = _parse_int(args.get('page'))
    if page is None or page < 1:
        page = DEFAULT_PAGE

    limit = _parse_int(args.get('limit'))
    if limit is None or limit <= 0:
        limit = DEFAULT_LIMIT
    if limit > MAX_LIMIT:
        limit = MAX_LIMIT

    def norm(value):
        if isinstance(value, str):
            stripped = value.strip()
            return stripped if stripped else None
        return value

    return ProfileListParams(
        gender=norm(args.get('gender')),
        age_group=norm(args.get('age_group')),
        country_id=norm(args.get('country_id')),
        min_age=_parse_int(args.get('min_age')),
        max_age=_parse_int(args.get('max_age')),
        min_gender_probability=_parse_float(args.get('min_gender_probability')),
        min_country_probability=_parse_float(args.get('min_country_probability')),
        sort_by=sort_by,
        order=order,
        page=page,
        limit=limit,
    )


def parse_profile_search_params(args, parsed_filters) -> ProfileListParams:
    base = parse_profile_list_params(args)
    return ProfileListParams(
        gender=parsed_filters.get('gender'),
        age_group=parsed_filters.get('age_group'),
        country_id=parsed_filters.get('country_id'),
        min_age=parsed_filters.get('min_age'),
        max_age=parsed_filters.get('max_age'),
        min_gender_probability=parsed_filters.get('min_gender_probability'),
        min_country_probability=parsed_filters.get('min_country_probability'),
        sort_by=base.sort_by,
        order=base.order,
        page=base.page,
        limit=base.limit,
    )


def build_profile_list_query(params: ProfileListParams):
    query = Profile.query

    if params.gender:
        query = query.filter(db.func.lower(Profile.gender) == params.gender.lower())
    if params.age_group:
        query = query.filter(db.func.lower(Profile.age_group) == params.age_group.lower())
    if params.country_id:
        query = query.filter(db.func.lower(Profile.country_id) == params.country_id.lower())

    if params.min_age is not None:
        query = query.filter(Profile.age >= params.min_age)
    if params.max_age is not None:
        query = query.filter(Profile.age <= params.max_age)
    if params.min_gender_probability is not None:
        query = query.filter(Profile.gender_probability >= params.min_gender_probability)
    if params.min_country_probability is not None:
        query = query.filter(Profile.country_probability >= params.min_country_probability)

    return query


def apply_sort_and_pagination(query, params: ProfileListParams):
    sort_column = ALLOWED_SORT_FIELDS.get(params.sort_by, Profile.created_at)
    ordered = query.order_by(sort_column.asc() if params.order == 'asc' else sort_column.desc())
    offset = (params.page - 1) * params.limit
    return ordered.offset(offset).limit(params.limit)
