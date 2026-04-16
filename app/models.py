from app import db
import uuid
from datetime import datetime


class Profile(db.Model):
    __tablename__ = 'profiles'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False, index=True)
    gender = db.Column(db.String(20), nullable=True)
    gender_probability = db.Column(db.Float, nullable=True)
    sample_size = db.Column(db.Integer, nullable=True)  # count from Genderize API
    age = db.Column(db.Integer, nullable=True)
    age_group = db.Column(db.String(20), nullable=True)
    country_id = db.Column(db.String(10), nullable=True)
    country_probability = db.Column(db.Float, nullable=True)
    # api_responses = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('name', name='uq_profile_name'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'gender': self.gender,
            'gender_probability': self.gender_probability,
            'sample_size': self.sample_size,
            'age': self.age,
            'age_group': self.age_group,
            'country_id': self.country_id,
            'country_probability': self.country_probability,
            # 'api_responses': self.api_responses,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<Profile {self.name}>'
