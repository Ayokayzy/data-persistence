"""add profile query indexes

Revision ID: 3c1f7d8b2a91
Revises: 0bfb89951fbc
Create Date: 2026-04-22 10:00:00.000000
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '3c1f7d8b2a91'
down_revision = '0bfb89951fbc'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('profiles', schema=None) as batch_op:
        batch_op.create_index('ix_profiles_gender', ['gender'], unique=False)
        batch_op.create_index('ix_profiles_country_id', ['country_id'], unique=False)
        batch_op.create_index('ix_profiles_age_group', ['age_group'], unique=False)
        batch_op.create_index('ix_profiles_age', ['age'], unique=False)
        batch_op.create_index('ix_profiles_created_at', ['created_at'], unique=False)


def downgrade():
    with op.batch_alter_table('profiles', schema=None) as batch_op:
        batch_op.drop_index('ix_profiles_created_at')
        batch_op.drop_index('ix_profiles_age')
        batch_op.drop_index('ix_profiles_age_group')
        batch_op.drop_index('ix_profiles_country_id')
        batch_op.drop_index('ix_profiles_gender')
