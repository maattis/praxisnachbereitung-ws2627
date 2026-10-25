"""add_damage_note_to_assignment

Revision ID: 883ea73ba6c0
Revises:
Create Date: 2026-10-25 10:28:54.763518

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "883ea73ba6c0"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add damage_note column to the assignment table."""
    op.add_column("assignment", sa.Column("damage_note", sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove damage_note column from the assignment table."""
    op.drop_column("assignment", "damage_note")
