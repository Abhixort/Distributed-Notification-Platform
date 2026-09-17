"""Initial schema migration

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-09-17

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Templates Table
    op.create_table(
        'templates',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('description', sa.String(255), nullable=True),
        sa.Column('channel', sa.String(20), nullable=False),
        sa.Column('subject_template', sa.String(255), nullable=True),
        sa.Column('body_template', sa.Text(), nullable=False),
        sa.Column('variables', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_templates_name', 'templates', ['name'])
    op.create_index('ix_templates_channel', 'templates', ['channel'])

    # 2. Notifications Table
    op.create_table(
        'notifications',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('channel', sa.String(20), nullable=False),
        sa.Column('recipient', sa.String(255), nullable=False),
        sa.Column('priority', sa.String(20), nullable=False, server_default='medium'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('subject', sa.String(255), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('template_id', sa.String(36), sa.ForeignKey('templates.id', ondelete='SET NULL'), nullable=True),
        sa.Column('template_data', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('idempotency_key', sa.String(128), nullable=True, unique=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_details', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_notifications_channel', 'notifications', ['channel'])
    op.create_index('ix_notifications_recipient', 'notifications', ['recipient'])
    op.create_index('ix_notifications_status', 'notifications', ['status'])
    op.create_index('ix_notifications_priority', 'notifications', ['priority'])
    op.create_index('ix_notifications_idempotency_key', 'notifications', ['idempotency_key'])
    op.create_index('ix_notifications_status_priority', 'notifications', ['status', 'priority'])
    op.create_index('ix_notifications_scheduled', 'notifications', ['status', 'scheduled_at'])

    # 3. Delivery Logs Table
    op.create_table(
        'delivery_logs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('notification_id', sa.String(36), sa.ForeignKey('notifications.id', ondelete='CASCADE'), nullable=False),
        sa.Column('attempt_number', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('provider_message_id', sa.String(128), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('latency_ms', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_delivery_logs_notification_id', 'delivery_logs', ['notification_id'])

    # 4. API Keys Table
    op.create_table(
        'api_keys',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('key_hash', sa.String(128), nullable=False, unique=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('client_id', sa.String(50), nullable=False),
        sa.Column('rate_limit_capacity', sa.Integer(), nullable=False, server_default='200'),
        sa.Column('rate_limit_refill_rate', sa.Float(), nullable=False, server_default='166.67'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_api_keys_client_id', 'api_keys', ['client_id'])


def downgrade() -> None:
    op.drop_table('api_keys')
    op.drop_table('delivery_logs')
    op.drop_table('notifications')
    op.drop_table('templates')
