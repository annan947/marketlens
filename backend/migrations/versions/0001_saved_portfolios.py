"""Create versioned saved research portfolios."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001_saved_portfolios'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('saved_portfolios',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('notes', sa.String(2000), nullable=False),
        sa.Column('definition', sa.JSON().with_variant(postgresql.JSONB, 'postgresql'), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table('saved_portfolios')
