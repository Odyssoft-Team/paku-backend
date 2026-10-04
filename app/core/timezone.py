from datetime import date, datetime, timedelta, timezone

# Perú no tiene horario de verano: America/Lima es UTC-5 fijo. Se usa para "hoy" y para los rangos
# de días del negocio, sin depender de la zona horaria del servidor (que corre en UTC).
LIMA_TZ = timezone(timedelta(hours=-5))


def today_lima() -> date:
    return datetime.now(LIMA_TZ).date()
