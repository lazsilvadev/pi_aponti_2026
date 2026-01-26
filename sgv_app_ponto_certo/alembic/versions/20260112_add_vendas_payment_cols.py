"""add payment columns to vendas

Revision ID: 20260112_add_vendas_payment_cols
Revises: 20260112_add_paymentsettings_qrimage
Create Date: 2026-01-12 00:10:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260112_add_vendas_payment_cols"
down_revision = "20260112_add_paymentsettings_qrimage"
branch_labels = None
depends_on = None


def upgrade():
    # adiciona colunas para rastreamento de transações de pagamento
    op.add_column(
        "vendas", sa.Column("transaction_id", sa.String(length=128), nullable=True)
    )
    op.add_column("vendas", sa.Column("acquirer", sa.String(length=100), nullable=True))
    op.add_column(
        "vendas", sa.Column("payment_status", sa.String(length=50), nullable=True)
    )


def downgrade():
    op.drop_column("vendas", "payment_status")
    op.drop_column("vendas", "acquirer")
    op.drop_column("vendas", "transaction_id")
