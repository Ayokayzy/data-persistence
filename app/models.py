import uuid
from datetime import datetime, timezone

from app import db


def generate_uuid_v7() -> str:
    """
    Generate a UUID v7-compatible identifier.
    """
    ts_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    rand_a = uuid.uuid4().int & ((1 << 12) - 1)
    rand_b = uuid.uuid4().int & ((1 << 62) - 1)

    value = (ts_ms << 80) | (0x7 << 76) | (rand_a << 64) | (0x2 << 62) | rand_b
    return str(uuid.UUID(int=value))


class Profile(db.Model):
    __tablename__ = 'profiles'

    @staticmethod
    def generate_uuid_v7() -> str:
        return generate_uuid_v7()

    id = db.Column(db.String(36), primary_key=True, default=lambda: Profile.generate_uuid_v7())
    name = db.Column(db.String(255), nullable=False, index=True)
    gender = db.Column(db.String(20), nullable=True)
    gender_probability = db.Column(db.Float, nullable=True)
    sample_size = db.Column(db.Integer, nullable=True)  # count from Genderize API
    age = db.Column(db.Integer, nullable=True)
    age_group = db.Column(db.String(20), nullable=True)
    country_id = db.Column(db.String(10), nullable=True)
    country_name = db.Column(db.String(100), nullable=True)
    country_probability = db.Column(db.Float, nullable=True)
    # api_responses = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('name', name='uq_profile_name'),
    )

    def to_dict(self):
        def format_utc_iso8601(dt):
            if not dt:
                return None
            return dt.replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')

        return {
            'id': self.id,
            'name': self.name,
            'gender': self.gender,
            'gender_probability': self.gender_probability,
            'sample_size': self.sample_size,
            'age': self.age,
            'age_group': self.age_group,
            'country_id': self.country_id,
            'country_name': self.country_name,
            'country_probability': self.country_probability,
            'created_at': format_utc_iso8601(self.created_at),
        }

    def __repr__(self):
        return f'<Profile {self.name}>'


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid_v7)
    github_id = db.Column(db.String(128), unique=True, nullable=False, index=True)
    username = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=True)
    avatar_url = db.Column(db.String(1024), nullable=True)
    role = db.Column(db.String(20), nullable=False, default='analyst')
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_login_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    refresh_tokens = db.relationship(
        'RefreshToken',
        back_populates='user',
        cascade='all, delete-orphan',
        lazy='dynamic',
    )

    def to_dict(self):
        return {
            'id': self.id,
            'github_id': self.github_id,
            'username': self.username,
            'email': self.email,
            'avatar_url': self.avatar_url,
            'role': self.role,
            'is_active': self.is_active,
            'last_login_at': self.last_login_at.isoformat() + 'Z' if self.last_login_at else None,
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
        }


class RefreshToken(db.Model):
    __tablename__ = 'refresh_tokens'

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid_v7)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    token_hash = db.Column(db.String(128), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    revoked_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', back_populates='refresh_tokens')

    @property
    def is_revoked(self):
        return self.revoked_at is not None
