"""Facturación electrónica con Intifact (feature 0023): reglas puras, sin base de datos ni red.

Intifact (`https://api-facturacion.intifact.com/api/v1`, docs.intifact.com/docs/facturacion):
- `Authorization: Bearer <api key>`; el ambiente lo decide la key: `fact_test_` (SUNAT beta) o `fact_live_`.
- `/invoice/compute` calcula los importes sin emitir; `/invoice/send` encola el comprobante (estado ENCOLADO).
- `/documents/{id}` trae el estado SUNAT; `/invoice/{id}/pdf|xml|cdr` los archivos.
- `/invoice/cancel` (baja de factura) y `/boleta/cancel` (boleta vía resumen diario).
"""
from __future__ import annotations

import hashlib
import hmac
import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Optional

PROVIDER = "intifact"
DEFAULT_BASE_URL = "https://api-facturacion.intifact.com/api/v1"

# Tipos de comprobante (catálogo SUNAT 01)
BOLETA, FACTURA = "BOLETA", "FACTURA"
TIPO_DOC = {BOLETA: "03", FACTURA: "01"}
NOMBRE_TIPO = {"03": BOLETA, "01": FACTURA}
PREFIJO_SERIE = {"03": "B", "01": "F"}

# Documento de identidad del cliente (catálogo SUNAT 06)
DNI, CE, RUC, PASAPORTE = "1", "4", "6", "7"
NOMBRE_DOC = {DNI: "DNI", CE: "Carné de extranjería", RUC: "RUC", PASAPORTE: "Pasaporte"}
DOC_ANONIMO = "00000000"
NOMBRE_ANONIMO = "CLIENTE VARIOS"
LIMITE_BOLETA_ANONIMA = Decimal("700.00")

# Estados (los que devuelve Intifact / SUNAT). Estos dejan libre la orden para emitir otro comprobante;
# cualquier otro (ENCOLADO, ENVIANDO, ACEPTADO, ANULANDO…) cuenta como vigente.
ACEPTADO, RECHAZADO, ANULANDO, ANULADO, ENCOLADO = "ACEPTADO", "RECHAZADO", "ANULANDO", "ANULADO", "ENCOLADO"
NO_VIGENTES = frozenset({RECHAZADO, ANULADO, "ERROR", "COLA_FALLIDA"})
# Estados en curso: se vuelven a consultar hasta que SUNAT responda.
FINALES = frozenset({ACEPTADO, RECHAZADO, ANULADO, "ERROR", "COLA_FALLIDA"})

# SUNAT acepta la baja (factura) o el resumen con estado anulado (boleta) hasta 7 días después de emitido.
DIAS_PARA_ANULAR = 7

# Momento en que una orden pagada queda lista para emitir (Configuración → Intifact). La emisión manual siempre está
# disponible para las órdenes listas; la automática emite las que no necesitan datos del admin.
TRIGGER_SERVICE = "service"   # al realizarse el servicio: la boleta sale con la fecha del servicio
TRIGGER_PAYMENT = "payment"   # al confirmarse el pago
ISSUE_TRIGGERS = (TRIGGER_SERVICE, TRIGGER_PAYMENT)
DEFAULT_ISSUE_TRIGGER = TRIGGER_SERVICE
# Órdenes por envío en la emisión de varias a la vez
MAX_BATCH_ISSUE = 50


def ready_to_issue(trigger: str, *, order_status: str, parent_status: Optional[str], is_adjustment: bool) -> bool:
    """Si una orden pagada y no cancelada ya se puede emitir. Con `service`, el servicio debe estar realizado (`done`);
    un ajuste por peso, que no tiene servicio propio, cuando su orden original está realizada."""
    if trigger != TRIGGER_SERVICE:
        return True
    return (parent_status if is_adjustment else order_status) == "done"

IGV_RATE = Decimal("0.18")
AFECTACION_GRAVADO = "10"
UNIDAD_SERVICIO = "ZZ"
CENT = Decimal("0.01")

# Campos del cálculo que acepta el envío (los demás de /invoice/compute son informativos).
CAMPOS_RAIZ = (
    "tipoMoneda", "montoOperGravadas", "montoOperExoneradas", "montoOperInafectas", "montoOperGratuitas",
    "montoIgv", "descuentoGlobal", "descuentoGlobalBase", "totalImpuestos", "valorVenta", "subTotal", "montoImpVenta",
)
CAMPOS_ITEM = (
    "unidad", "cantidad", "codProducto", "descripcion", "marca", "tipAfeIgv", "porcentajeIgv", "montoValorUnitario",
    "descuento", "descuentoItem", "montoValorVenta", "montoBaseIgv", "igv", "totalImpuestos", "montoPrecioUnitario",
    "factorIcbper", "codProdSunat",
)


class InvoicingInvalid(Exception):
    """Dato inválido para emitir o configurar. `field` indica cuál (para el formulario)."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


def money(value: Any) -> Decimal:
    return Decimal(str(value if value is not None else 0)).quantize(CENT, rounding=ROUND_HALF_UP)


# ---------- Configuración ----------

def environment_of(api_key: Optional[str]) -> str:
    return "live" if (api_key or "").startswith("fact_live_") else "test"


def check_api_key(value: str) -> str:
    key = value.strip()
    if not re.fullmatch(r"fact_(test|live)_[A-Za-z0-9_\-]+", key):
        raise InvoicingInvalid("api_key", "La API key de Intifact empieza con fact_test_ o fact_live_.")
    return key


def check_ruc(value: str, field: str = "company_ruc") -> str:
    ruc = value.strip()
    if not re.fullmatch(r"(10|15|16|17|20)\d{9}", ruc):
        raise InvoicingInvalid(field, "El RUC tiene 11 dígitos y empieza con 10, 15, 16, 17 o 20.")
    return ruc


def check_secret(value: str) -> str:
    secret = value.strip()
    if len(secret) < 8 or any(c.isspace() for c in secret):
        raise InvoicingInvalid("webhook_secret", "El secreto del webhook es el que muestra el portal de Intifact.")
    return secret


def normalize_series(value: str, tipo_doc: str) -> str:
    series = (value or "").strip().upper()
    prefix = PREFIJO_SERIE[tipo_doc]
    if not re.fullmatch(rf"{prefix}[A-Z0-9]{{3}}", series):
        nombre = "boletas" if tipo_doc == "03" else "facturas"
        raise InvoicingInvalid("series", f"La serie de {nombre} tiene 4 caracteres y empieza con {prefix} "
                                         f"(por ejemplo {prefix}001).")
    return series


# ---------- Cliente del comprobante ----------

def check_customer(tipo: str, doc_type: str, doc_number: str, name: str) -> tuple[str, str, str]:
    """Valida y normaliza (tipo_doc, número, razón social) según el tipo de comprobante."""
    number = re.sub(r"\s", "", doc_number or "").upper()
    name = re.sub(r"\s+", " ", (name or "").strip())
    if not name:
        raise InvoicingInvalid("customer_name", "Falta el nombre o la razón social del cliente.")
    if doc_type not in NOMBRE_DOC:
        raise InvoicingInvalid("customer_doc_type", "Tipo de documento no válido (DNI, CE, RUC o pasaporte).")
    if tipo == FACTURA and doc_type != RUC:
        raise InvoicingInvalid("customer_doc_type", "La factura necesita el RUC del cliente.")
    if doc_type == DNI and not re.fullmatch(r"\d{8}", number):
        raise InvoicingInvalid("customer_doc_number", "El DNI tiene 8 dígitos.")
    if doc_type == RUC:
        check_ruc(number, "customer_doc_number")
    if doc_type in (CE, PASAPORTE) and not re.fullmatch(r"[A-Z0-9]{6,12}", number):
        raise InvoicingInvalid("customer_doc_number", "El documento tiene entre 6 y 12 letras o números.")
    return doc_type, number, name[:255]


def is_anonymous(doc_type: str, doc_number: str) -> bool:
    return doc_type == DNI and doc_number == DOC_ANONIMO


def profile_customer(first_name: str, last_name: str, dni: Optional[str]) -> tuple[str, str, str]:
    """Cliente por defecto de la boleta: el DNI del perfil si es válido; si no, consumidor final."""
    name = f"{first_name or ''} {last_name or ''}".strip()
    number = re.sub(r"\s", "", dni or "")
    if re.fullmatch(r"\d{8}", number) and number != DOC_ANONIMO:
        return DNI, number, name or NOMBRE_ANONIMO
    return DNI, DOC_ANONIMO, name or NOMBRE_ANONIMO


# ---------- Líneas ----------

def order_lines(items_snapshot: Any, total: Any, pet_name: Optional[str] = None) -> list[dict]:
    """Líneas del comprobante a partir de la orden, con precios que incluyen IGV.

    Cada línea del carrito (servicio, adicional o ajuste) es una línea del comprobante. El descuento de campaña se
    reparte en proporción al precio de cada línea, y el redondeo cae en la última, así la suma es exactamente el
    total cobrado.
    """
    lines = [l for l in (items_snapshot or []) if isinstance(l, dict)]
    total = money(total)
    raw = []
    for l in lines:
        qty = Decimal(str(l.get("qty") or 1))
        unit = money(l.get("unit_price"))
        if qty <= 0 or unit <= 0:
            continue
        name = str(l.get("name") or ("Adicional" if l.get("kind") == "service_addon" else "Servicio")).strip()
        if pet_name and l.get("kind") in ("service_base", "price_adjustment"):
            name = f"{name} - {pet_name}"
        raw.append({"description": name[:250], "qty": qty, "gross": money(unit * qty),
                    "code": str(l.get("kind") or "service")[:30].upper()})
    if not raw:
        if total <= 0:
            return []
        raw = [{"description": "Servicio de baño y grooming", "qty": Decimal(1), "gross": total, "code": "SERVICE"}]
    subtotal = sum((r["gross"] for r in raw), Decimal(0))
    if subtotal != total and subtotal > 0:
        factor = total / subtotal
        assigned = Decimal(0)
        for i, r in enumerate(raw):
            r["gross"] = total - assigned if i == len(raw) - 1 else money(r["gross"] * factor)
            assigned += r["gross"]
    out = []
    for r in raw:
        if r["gross"] <= 0:
            continue
        unit_price = money(r["gross"] / r["qty"])
        # Si el reparto deja céntimos que no se dividen exacto entre las unidades, la línea va como 1 unidad.
        qty = r["qty"] if money(unit_price * r["qty"]) == r["gross"] else Decimal(1)
        out.append({
            "descripcion": r["description"], "cantidad": float(qty),
            "valorUnitario": float(r["gross"] if qty == 1 else unit_price),
            "unidad": UNIDAD_SERVICIO, "codProducto": r["code"], "afectacion": AFECTACION_GRAVADO,
        })
    return out


def build_send_body(*, calculo: dict, ruc: str, tipo_doc: str, serie: str, correlativo: str, fecha: str,
                    customer: tuple[str, str, str], address: Optional[str]) -> dict:
    """Cuerpo de /invoice/send con los importes tal cual los calculó /invoice/compute."""
    body = {k: calculo[k] for k in CAMPOS_RAIZ if k in calculo}
    body.setdefault("tipoMoneda", "PEN")
    body.update({
        "empresaRuc": ruc,
        "tipoDoc": tipo_doc,
        "serie": serie,
        "correlativo": correlativo,
        "fechaEmision": fecha,
        "tipoOperacion": "0101",
        "clienteTipoDoc": customer[0],
        "clienteNumDoc": customer[1],
        "clienteRazonSocial": customer[2],
        "detalle": [{k: it[k] for k in CAMPOS_ITEM if k in it} for it in calculo.get("items") or []],
        "leyendas": [{"legendCode": "1000", "legendValue": calculo.get("montoEnLetras") or ""}],
        "formaPago": [{"tipo": "Contado", "monto": calculo.get("montoImpVenta"), "fechaPago": fecha}],
    })
    if address:
        body["clienteDireccion"] = address[:500]
    return body


def preview_lines(items: list[dict], calculo: dict) -> list[dict]:
    """Líneas para mostrar el comprobante (valor sin IGV, precio con IGV, IGV y total por línea)."""
    out = []
    for entrada, item in zip(items, calculo.get("items") or items):
        qty = Decimal(str(item.get("cantidad", entrada["cantidad"])))
        unit_value = item.get("montoValorUnitario")
        unit_price = item.get("montoPrecioUnitario")
        if unit_value is None or unit_price is None:  # Intifact siempre los trae; solo un respaldo
            base = Decimal(str(entrada["valorUnitario"]))
            unit_price, unit_value = base, base / (1 + IGV_RATE)
        out.append({
            "description": item.get("descripcion", entrada["descripcion"]),
            "quantity": float(qty),
            "unit_value": str(money(unit_value)),
            "unit_price": str(money(unit_price)),
            "igv": str(money(item.get("igv", money(Decimal(str(unit_price)) - money(unit_value)) * qty))),
            "total": str(money(Decimal(str(unit_price)) * qty)),
        })
    return out


# ---------- Webhook ----------

WEBHOOK_TOLERANCE_MS = 5 * 60 * 1000
STATUS_BY_EVENT = {
    "document.accepted": ACEPTADO,
    "document.rejected": RECHAZADO,
    "document.queue_failed": "COLA_FALLIDA",
    "document.retried": ENCOLADO,
}


def valid_signature(secret: str, timestamp: str, body: bytes, signature: str) -> bool:
    """X-Facturacion-Signature = HMAC-SHA256 en hex de "{timestamp}.{cuerpo}" con el secreto."""
    expected = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, (signature or "").strip().lower())


def public_pdf_url(base_url: str, ruc: str, tipo_doc: str, serie: str, correlativo: str) -> str:
    """Consulta pública del comprobante (sin API key), para enviarla al cliente."""
    return f"{base_url.rstrip('/')}/public/consultar/{ruc}/{tipo_doc}/{serie}/{correlativo}/pdf"
