"""add country_name to profiles

Revision ID: a4e2b8c3d1f9
Revises: 3c1f7d8b2a91
Create Date: 2026-04-22 11:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'a4e2b8c3d1f9'
down_revision = '3c1f7d8b2a91'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('country_name', sa.String(length=100), nullable=True))


def downgrade():
    with op.batch_alter_table('profiles', schema=None) as batch_op:
        batch_op.drop_column('country_name')
