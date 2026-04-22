def serialize_profile_list_item(profile):
    from datetime import timezone
    dt = profile.created_at
    created_at = (
        dt.replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')
        if dt else None
    )
    return {
        'id': profile.id,
        'name': profile.name,
        'gender': profile.gender,
        'gender_probability': profile.gender_probability,
        'age': profile.age,
        'age_group': profile.age_group,
        'country_id': profile.country_id,
        'country_name': profile.country_name,
        'country_probability': profile.country_probability,
        'created_at': created_at,
    }
