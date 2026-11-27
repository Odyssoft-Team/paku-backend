"""Reportes contables de facturación electrónica por mes (feature 0023): lo que se le entrega al contador.

- Resumen de totales (xlsx): cantidad, op. gravada, IGV y total por tipo; y por día.
- Resumen detallado de facturas (xlsx): una fila por factura.
- Compendio de boletas / de facturas (zip): los PDF del mes.
- Registro de ventas electrónico PLE 14.1 (txt): formato SUNAT, 36 campos separados por «|».

Solo cuenta lo emitido en el ambiente actual (prueba o producción). Los rechazados no son comprobantes válidos: no
entran. Los anulados aparecen en cero y con estado 2 en el registro de ventas.
"""
from __future__ import annotations

import io
import re
import zipfile
from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.modules.invoicing.app.config import ActiveIntifact
from app.modules.invoicing.domain.intifact import ANULADO, ANULANDO, ACEPTADO
from app.modules.invoicing.infra.intifact_client import IntifactError
from app.modules.invoicing.infra.models import InvoiceDocumentModel

VALID = (ACEPTADO, ANULANDO, ANULADO)
TYPE_NAME = {"03": "Boleta", "01": "Factura", "07": "Nota de crédito", "08": "Nota de débito"}
ZERO = Decimal("0.00")
REPORTS = ("resumen-totales", "resumen-facturas", "compendio-boletas", "compendio-facturas", "registro-ventas")


@dataclass
class AccountingMonth:
    month: str          # AAAA-MM
    boletas: int
    facturas: int
    voided: int
    total: Decimal      # aceptados (sin anulados)


def month_range(month: str) -> tuple[date, date]:
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month or ""):
        raise HTTPException(status_code=422, detail={"code": "MONTH_INVALID", "message": "El mes va como AAAA-MM."})
    year, m = int(month[:4]), int(month[5:])
    return date(year, m, 1), date(year, m, monthrange(year, m)[1])


def _voided(d: InvoiceDocumentModel) -> bool:
    return d.status == ANULADO


async def _of_month(repo, month: str, environment: str, doc_types=None) -> list[InvoiceDocumentModel]:
    start, end = month_range(month)
    return await repo.documents_between(start, end, environment, VALID, doc_types)


async def months(repo, environment: str) -> list[AccountingMonth]:
    by_month: dict[str, AccountingMonth] = {}
    for d in await repo.documents_in_environment(environment, VALID):
        key = d.issue_date.strftime("%Y-%m")
        m = by_month.setdefault(key, AccountingMonth(month=key, boletas=0, facturas=0, voided=0, total=ZERO))
        if _voided(d):
            m.voided += 1
            continue
        if d.doc_type == "03":
            m.boletas += 1
        else:
            m.facturas += 1
        m.total += Decimal(str(d.total))
    return sorted(by_month.values(), key=lambda m: m.month, reverse=True)


# ---------- Excel ----------

TITLE = Font(bold=True, size=13)
BOLD = Font(bold=True)
HEADER = PatternFill("solid", fgColor="E2E8F0")
SOLES = "#,##0.00"


def _sheet(ws, title: str, subtitle: str, columns: list[str], rows: list[list], money_cols: set[int],
           widths: list[int]) -> None:
    ws.append([title])
    ws["A1"].font = TITLE
    ws.append([subtitle])
    ws.append([])
    ws.append(columns)
    for i in range(1, len(columns) + 1):
        cell = ws.cell(row=4, column=i)
        cell.font, cell.fill = BOLD, HEADER
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for row in rows:
        ws.append(row)
    for n in range(5, ws.max_row + 1):
        for i in money_cols:
            ws.cell(row=n, column=i).number_format = SOLES
    for i, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.freeze_panes = "A5"


def _company(ruc: str, environment: str) -> str:
    return f"Paku · RUC {ruc or '—'}" + (" · MODO PRUEBA (sin valor fiscal)" if environment == "test" else "")


def _xlsx(wb: Workbook) -> bytes:
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


async def summary_totals(repo, month: str, environment: str, ruc: str) -> bytes:
    docs = await _of_month(repo, month, environment)
    by_type: dict[str, list] = {}
    for d in docs:
        name = TYPE_NAME.get(d.doc_type, d.doc_type)
        key = f"{name}s anuladas" if _voided(d) else f"{name}s"
        row = by_type.setdefault(key, [key, 0, ZERO, ZERO, ZERO])
        row[1] += 1
        if not _voided(d):
            row[2] += Decimal(str(d.taxable_amount))
            row[3] += Decimal(str(d.igv))
            row[4] += Decimal(str(d.total))
    rows = sorted(by_type.values(), key=lambda r: ("anulad" in r[0], r[0]))
    valid = [r for r in rows if "anulad" not in r[0]]
    rows.append(["TOTAL", sum(r[1] for r in valid), sum((r[2] for r in valid), ZERO),
                 sum((r[3] for r in valid), ZERO), sum((r[4] for r in valid), ZERO)])
    wb = Workbook()
    ws = wb.active
    ws.title = "Resumen"
    _sheet(ws, f"Resumen de totales · {month}", _company(ruc, environment),
           ["Tipo", "Cantidad", "Op. gravada", "IGV", "Total"], rows, {3, 4, 5}, [28, 12, 16, 14, 16])
    for i in range(1, 6):
        ws.cell(row=ws.max_row, column=i).font = BOLD

    days: dict[date, list] = defaultdict(lambda: [0, 0, ZERO, ZERO, ZERO])
    for d in docs:
        if _voided(d):
            continue
        row = days[d.issue_date]
        row[0 if d.doc_type == "03" else 1] += 1
        row[2] += Decimal(str(d.taxable_amount))
        row[3] += Decimal(str(d.igv))
        row[4] += Decimal(str(d.total))
    daily = wb.create_sheet("Por día")
    _sheet(daily, f"Ventas por día · {month}", _company(ruc, environment),
           ["Fecha", "Boletas", "Facturas", "Op. gravada", "IGV", "Total"],
           [[d.strftime("%d/%m/%Y"), *v] for d, v in sorted(days.items())], {4, 5, 6}, [14, 10, 10, 16, 14, 16])
    return _xlsx(wb)


async def summary_invoices(repo, month: str, environment: str, ruc: str) -> bytes:
    rows = []
    for d in await _of_month(repo, month, environment, ("01",)):
        voided = _voided(d)
        rows.append([
            d.issue_date.strftime("%d/%m/%Y"), f"{d.series}-{d.number}", d.customer_doc_number, d.customer_name,
            ZERO if voided else Decimal(str(d.taxable_amount)), ZERO if voided else Decimal(str(d.igv)),
            ZERO if voided else Decimal(str(d.total)),
            "Anulada" if voided else ("Anulación en curso" if d.status == ANULANDO else "Aceptada"),
        ])
    wb = Workbook()
    ws = wb.active
    ws.title = "Facturas"
    _sheet(ws, f"Resumen detallado de facturas · {month}", _company(ruc, environment),
           ["Fecha", "Número", "RUC", "Razón social", "Op. gravada", "IGV", "Total", "Estado SUNAT"],
           rows, {5, 6, 7}, [12, 14, 14, 44, 14, 12, 14, 18])
    return _xlsx(wb)


async def compendium(repo, intifact: ActiveIntifact, month: str, kind: str) -> bytes:
    """Los PDF del mes en un zip. kind: «boletas» o «facturas»."""
    doc_type = "03" if kind == "boletas" else "01"
    docs = [d for d in await _of_month(repo, month, intifact.environment, (doc_type,)) if d.provider_id]
    if not docs:
        raise HTTPException(status_code=404, detail={"code": "NOTHING_IN_MONTH",
                                                     "message": f"No hay {kind} emitidas en {month}."})
    out = io.BytesIO()
    missing: list[str] = []
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for d in docs:
            name = f"{d.series}-{d.number.zfill(8)}"
            try:
                content, _ = await intifact.client.file(d.provider_id, "pdf", "a4")
                z.writestr(f"{name}{'-ANULADO' if _voided(d) else ''}.pdf", content)
            except IntifactError:
                missing.append(name)
        if missing:
            z.writestr("NO_DESCARGADOS.txt", "No se pudieron descargar (reintenta más tarde):\n" + "\n".join(missing))
    return out.getvalue()


def _amount(value) -> str:
    return f"{Decimal(str(value)):.2f}"


async def sales_register(repo, month: str, environment: str, ruc: str) -> tuple[bytes, str]:
    """Registro de Ventas e Ingresos electrónico (PLE, libro 14.1). Una línea por comprobante.

    Campos (Anexo 2, RS 286-2009/SUNAT y modificatorias, con ICBPER):
    1 periodo · 2 CUO · 3 correlativo del asiento · 4 fecha de emisión · 5 vencimiento · 6 tipo · 7 serie ·
    8 número · 9 número final · 10-11 documento del cliente · 12 razón social · 13 exportación · 14 base gravada ·
    15 dscto. base · 16 IGV · 17 dscto. IGV · 18 exonerada · 19 inafecta · 20 ISC · 21-22 arroz pilado · 23 ICBPER ·
    24 otros tributos · 25 total · 26 moneda · 27 tipo de cambio · 28-31 comprobante modificado (notas) ·
    32 contrato · 33 error tipo 1 · 34 medio de pago · 35 estado (1 del periodo, 2 anulado) · 36 libre.
    """
    start, _ = month_range(month)
    period = f"{start:%Y%m}00"
    lines = []
    for n, d in enumerate(await _of_month(repo, month, environment), start=1):
        voided = _voided(d)
        base, igv, total = (ZERO, ZERO, ZERO) if voided else (d.taxable_amount, d.igv, d.total)
        fields = [
            period, f"{d.series}{d.number.zfill(8)}", f"M{n}", d.issue_date.strftime("%d/%m/%Y"), "",
            d.doc_type, d.series, d.number, "", d.customer_doc_type, d.customer_doc_number,
            d.customer_name.replace("|", " ")[:100], "0.00", _amount(base), "0.00", _amount(igv),
            "0.00", "0.00", "0.00", "0.00", "0.00", "0.00", "0.00", "0.00", _amount(total), "PEN", "1.000",
            "", "", "", "", "", "", "", "2" if voided else "1", "",
        ]
        lines.append("|".join(fields) + "|")
    content = "\r\n".join(lines) + ("\r\n" if lines else "")
    # LE + RUC + AAAAMM00 + 140100 + 00 + operaciones(1) + con información(1/0) + moneda soles(1) + PLE(1)
    name = f"LE{ruc or '00000000000'}{period}140100001{1 if lines else 0}11.txt"
    return content.encode("utf-8"), name
