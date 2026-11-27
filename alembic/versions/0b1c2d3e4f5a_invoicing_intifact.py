"""facturación electrónica con Intifact (feature 0023, reemplaza a Nubefact 0020)

- invoicing_providers: columnas para Intifact (RUC emisor, secreto del webhook cifrado y su máscara, emisión
  automática y aviso por correo). La fila de Nubefact, si existe, queda sin uso.
- invoicing_series: series de boletas y facturas con correlativo inicial; una activa por tipo.
- invoice_documents: comprobantes emitidos (orden, cliente, montos, estado SUNAT, líneas, anulación). Número único por
  ambiente, tipo y serie.
- invoicing_companies: clientes con RUC para facturas.

Tablas nuevas, sin backfill.

Revision ID: 0b1c2d3e4f5a
Revises: 9a0b1c2d3e4f
Create Date: 2026-11-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0b1c2d3e4f5a"
down_revision: Union[str, None] = "9a0b1c2d3e4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("invoicing_providers", sa.Column("company_ruc", sa.String(11), nullable=True))
    op.add_column("invoicing_providers", sa.Column("webhook_secret_encrypted", sa.Text(), nullable=True))
    op.add_column("invoicing_providers", sa.Column("webhook_secret_mask", sa.String(20), nullable=True))
    op.add_column("invoicing_providers",
                  sa.Column("auto_issue", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("invoicing_providers",
                  sa.Column("email_customer", sa.Boolean(), nullable=False, server_default=sa.true()))

    op.create_table(
        "invoicing_series",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("doc_type", sa.String(2), nullable=False),
        sa.Column("series", sa.String(4), nullable=False, unique=True),
        sa.Column("first_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "invoice_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("doc_type", sa.String(2), nullable=False),
        sa.Column("series", sa.String(4), nullable=False),
        sa.Column("number", sa.String(8), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("customer_doc_type", sa.String(1), nullable=False),
        sa.Column("customer_doc_number", sa.String(20), nullable=False),
        sa.Column("customer_name", sa.String(255), nullable=False),
        sa.Column("customer_address", sa.String(500), nullable=True),
        sa.Column("customer_email", sa.String(255), nullable=True),
        sa.Column("taxable_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("igv", sa.Numeric(12, 2), nullable=False),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="PEN"),
        sa.Column("provider_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="ENCOLADO"),
        sa.Column("response_code", sa.String(10), nullable=True),
        sa.Column("response_description", sa.Text(), nullable=True),
        sa.Column("hash", sa.String(100), nullable=True),
        sa.Column("environment", sa.String(4), nullable=False, server_default="test"),
        sa.Column("lines", sa.JSON(), nullable=True),
        sa.Column("amount_in_words", sa.Text(), nullable=True),
        sa.Column("void_reason", sa.String(250), nullable=True),
        sa.Column("voided_on", sa.Date(), nullable=True),
        sa.Column("issued_by", sa.Uuid(), nullable=True),
        sa.Column("customer_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("environment", "doc_type", "series", "number", name="uq_invoice_documents_number"),
    )
    op.create_index("ix_invoice_documents_order_id", "invoice_documents", ["order_id"])
    op.create_index("ix_invoice_documents_user_id", "invoice_documents", ["user_id"])
    op.create_index("ix_invoice_documents_issue_date", "invoice_documents", ["issue_date"])
    op.create_index("ix_invoice_documents_customer_doc_number", "invoice_documents", ["customer_doc_number"])
    op.create_index("ix_invoice_documents_provider_id", "invoice_documents", ["provider_id"])
    op.create_index("ix_invoice_documents_status", "invoice_documents", ["status"])

    op.create_table(
        "invoicing_companies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("ruc", sa.String(11), nullable=False),
        sa.Column("legal_name", sa.String(300), nullable=False),
        sa.Column("trade_name", sa.String(200), nullable=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_invoicing_companies_ruc", "invoicing_companies", ["ruc"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_invoicing_companies_ruc", table_name="invoicing_companies")
    op.drop_table("invoicing_companies")
    for name in ("status", "provider_id", "customer_doc_number", "issue_date", "user_id", "order_id"):
        op.drop_index(f"ix_invoice_documents_{name}", table_name="invoice_documents")
    op.drop_table("invoice_documents")
    op.drop_table("invoicing_series")
    for column in ("email_customer", "auto_issue", "webhook_secret_mask", "webhook_secret_encrypted", "company_ruc"):
        op.drop_column("invoicing_providers", column)
