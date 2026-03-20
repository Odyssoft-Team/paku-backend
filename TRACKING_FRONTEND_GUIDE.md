# 🗺️ Guía de Integración Frontend — Tracking en tiempo casi real

> **Fecha:** 20 de marzo de 2026
> **Base URL:** `https://<tu-dominio>` (sin prefijo `/api/v1`)
> **Autenticación:** `Authorization: Bearer <access_token>` en todos los endpoints.

---

## ⚙️ Cómo funciona el flujo (conceptual)

```
Ally app    → [1] POST /orders/{id}/depart          (estado → on_the_way)
            → [2] POST /tracking/orders/{id}/location  (cada 5s, mientras conduce)

Cliente app → [3] GET /tracking/orders/{id}/current   (polling cada 5s)
            → [4] Mueve el pin del ally en el mapa con los datos recibidos

Ally app    → [5] POST /orders/{id}/arrive           (estado → in_service)
            → [6] POST /tracking/orders/{id}/location  (puede seguir enviando)

Cliente app → [7] GET /tracking/orders/{id}/current   (sigue funcionando en in_service)
            → [8] Al detectar order_status == "in_service", cerrar el mapa
```

La posición se almacena **en memoria** en el backend (no en base de datos). Si el backend se reinicia, el ally simplemente envía su siguiente posición y el tracking se reanuda automáticamente.

---

## 🔒 Reglas de acceso

| Endpoint | Quién puede usarlo |
|---|---|
| `POST .../location` | Solo **ally** asignado a esa orden |
| `GET .../current` | **Cliente** dueño de la orden, **ally** asignado, **admin** |
| `GET .../route` | **Cliente** dueño de la orden, **ally** asignado, **admin** |

---

## 📐 Estados en que el tracking está activo

| Estado de la orden | Ally puede reportar | Cliente puede leer |
|---|---|---|
| `created` | ❌ | ❌ |
| `accepted` | ❌ | ❌ |
| `on_the_way` | ✅ | ✅ |
| `in_service` | ✅ | ✅ |
| `done` | ❌ | ❌ |
| `cancelled` | ❌ | ❌ |

---

## 📡 Endpoints

### `POST /tracking/orders/{order_id}/location`
**Ally reporta su posición actual**

```http
POST /tracking/orders/<order_uuid>/location
Authorization: Bearer <ally_token>
Content-Type: application/json

{
  "lat": -12.0931,
  "lng": -77.0465,
  "accuracy_m": 8.5         // opcional — precisión GPS del dispositivo
}
```

**Respuesta `201`:**
```json
{
  "order_id": "<uuid>",
  "lat": -12.0931,
  "lng": -77.0465,
  "recorded_at": "2026-03-20T14:32:10.123Z"
}
```

> ⚠️ **Frecuencia recomendada:** cada **5 segundos** mientras el ally esté en movimiento.
> Si el GPS no cambió significativamente (< 10 metros), el cliente puede omitir el envío.

---

### `GET /tracking/orders/{order_id}/current`
**Cliente consulta la última posición conocida**

```http
GET /tracking/orders/<order_uuid>/current
Authorization: Bearer <user_token>
```

**Respuesta `200`:**
```json
{
  "order_id": "<uuid>",
  "order_status": "on_the_way",
  "ally_location": {
    "lat": -12.0931,
    "lng": -77.0465,
    "accuracy_m": 8.5,
    "recorded_at": "2026-03-20T14:32:10.123Z"
  },
  "destination": {
    "lat": -12.1100,
    "lng": -77.0320,
    "accuracy_m": null,
    "recorded_at": null
  },
  "staleness_seconds": 3
}
```

> ℹ️ `ally_location` puede ser `null` si el ally aún no envió su primera posición desde que
> cambió a `on_the_way`. Muestra un estado de espera en la UI.
>
> ℹ️ `staleness_seconds` indica la antigüedad del último dato de posición. Si supera ~30s,
> puedes mostrar un aviso de "señal débil" o "actualizando...".

---

### `GET /tracking/orders/{order_id}/route`
**Ruta y ETA calculados por Google Routes API**

> ⚠️ Este endpoint puede devolver **HTTP 501** si la API key de Google no está configurada
> en el backend. Trátalo como opcional/degradable en el frontend.

```http
GET /tracking/orders/<order_uuid>/route
Authorization: Bearer <user_token>
```

**Respuesta `200`:**
```json
{
  "order_id": "<uuid>",
  "ally_location": {
    "lat": -12.0931,
    "lng": -77.0465,
    "accuracy_m": 8.5,
    "recorded_at": "2026-03-20T14:32:10.123Z"
  },
  "destination": {
    "lat": -12.1100,
    "lng": -77.0320,
    "accuracy_m": null,
    "recorded_at": null
  },
  "eta_seconds": 420,
  "eta_display": "7 min",
  "polyline": "encodedPolylineString...",
  "distance_meters": 1800
}
```

> Si `ally_location` es `null` (ally aún no reportó posición), los campos `eta_seconds`,
> `eta_display`, `polyline` y `distance_meters` también serán `null`.

---

## 💡 Ejemplo en código — App del ally (React Native / TypeScript)

```typescript
import * as Location from 'expo-location';

async function startTrackingReports(orderId: string, token: string): Promise<() => void> {
  // Solicitar permisos de ubicación en foreground
  const { status } = await Location.requestForegroundPermissionsAsync();
  if (status !== 'granted') throw new Error('Location permission denied');

  const interval = setInterval(async () => {
    try {
      const loc = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High });
      await fetch(`${BASE_URL}/tracking/orders/${orderId}/location`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          lat: loc.coords.latitude,
          lng: loc.coords.longitude,
          accuracy_m: loc.coords.accuracy ?? undefined,
        }),
      });
    } catch (err) {
      // Silenciar errores individuales — el próximo ciclo reintentará
      console.warn('Tracking report failed:', err);
    }
  }, 5000); // cada 5 segundos

  // Devolver función de limpieza para detener el intervalo
  return () => clearInterval(interval);
}

// Uso en componente:
// const stopTracking = await startTrackingReports(order.id, token);
// ... al llegar: stopTracking();
```

---

## 💡 Ejemplo en código — App del cliente (React Native / TypeScript)

```typescript
import MapView, { Marker, Polyline } from 'react-native-maps';
import { decode } from '@mapbox/polyline';   // npm i @mapbox/polyline

function useAllyTracking(orderId: string, token: string) {
  const [allyLocation, setAllyLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [orderStatus, setOrderStatus] = useState<string>('on_the_way');
  const [staleness, setStaleness] = useState<number | null>(null);

  useEffect(() => {
    let active = true;

    async function poll() {
      while (active) {
        try {
          const res = await fetch(`${BASE_URL}/tracking/orders/${orderId}/current`, {
            headers: { 'Authorization': `Bearer ${token}` },
          });

          if (res.ok) {
            const data = await res.json();
            setOrderStatus(data.order_status);
            setStaleness(data.staleness_seconds);

            if (data.ally_location) {
              setAllyLocation({ lat: data.ally_location.lat, lng: data.ally_location.lng });
            }

            // Detener el tracking cuando el servicio ya no está activo
            if (!['on_the_way', 'in_service'].includes(data.order_status)) {
              break;
            }
          }
        } catch (err) {
          console.warn('Tracking poll failed:', err);
        }

        // Esperar 5 segundos antes del próximo poll
        await new Promise(resolve => setTimeout(resolve, 5000));
      }
    }

    poll();
    return () => { active = false; };
  }, [orderId, token]);

  return { allyLocation, orderStatus, staleness };
}

// Uso en el componente del mapa:
function TrackingMap({ orderId, destination }) {
  const { allyLocation, orderStatus, staleness } = useAllyTracking(orderId, token);

  return (
    <MapView style={{ flex: 1 }}>
      {/* Destino siempre visible */}
      <Marker coordinate={{ latitude: destination.lat, longitude: destination.lng }} title="Tu domicilio" />

      {/* Pin del ally — solo si hay posición */}
      {allyLocation && (
        <Marker
          coordinate={{ latitude: allyLocation.lat, longitude: allyLocation.lng }}
          title="Tu groomer"
          // Usar ícono de camioneta/vehículo aquí
        />
      )}

      {/* Aviso de señal débil */}
      {staleness !== null && staleness > 30 && (
        <Text style={styles.staleWarning}>Actualizando ubicación...</Text>
      )}
    </MapView>
  );
}
```

---

## 💡 Ejemplo — Mostrar ruta (polyline + ETA)

```typescript
async function fetchRoute(orderId: string, token: string) {
  const res = await fetch(`${BASE_URL}/tracking/orders/${orderId}/route`, {
    headers: { 'Authorization': `Bearer ${token}` },
  });

  // El endpoint puede devolver 501 si Google Routes no está configurado
  if (res.status === 501) return null;
  if (!res.ok) return null;

  const data = await res.json();
  return data;
}

// En el componente del mapa:
const routeData = await fetchRoute(orderId, token);

if (routeData?.polyline) {
  // Decodificar encoded polyline → array de coordenadas
  const coords = decode(routeData.polyline).map(([lat, lng]) => ({ latitude: lat, longitude: lng }));
  // <Polyline coordinates={coords} strokeColor="#4285F4" strokeWidth={3} />
}

if (routeData?.eta_display) {
  // Mostrar "7 min" en la UI
}
```

---

## ❌ Errores comunes

| Código | Causa | Solución |
|---|---|---|
| `401 Unauthorized` | Token expirado o inválido | Renovar token |
| `403 tracking_forbidden` | No eres participante de esta orden o no eres el ally asignado | Verificar que la orden pertenece al usuario autenticado |
| `404 Order not found` | UUID de orden inválido | Verificar que la orden existe |
| `409 tracking_not_active` | La orden no está en `on_the_way` ni `in_service` | Solo reportar/leer cuando la orden esté en tracking activo |
| `409 tracking_not_available` | Igual que el anterior, en lectura | Ídem |
| `422` | `delivery_address_snapshot` sin coordenadas | Error de datos en la orden — notificar al admin |
| `501 routes_not_configured` | Google Routes API key no configurada | Ignorar el endpoint `/route` — usar solo `/current` |
| `502 routes_api_error` | Google Routes no respondió o devolvió error | Reintentar con backoff; mostrar ETA como "N/A" |

---

## 📋 Resumen de endpoints

| Endpoint | Método | Requiere auth | Rol mínimo |
|---|---|---|---|
| `/tracking/orders/{id}/location` | `POST` | ✅ | `ally` |
| `/tracking/orders/{id}/current` | `GET` | ✅ | `user` / `ally` / `admin` |
| `/tracking/orders/{id}/route` | `GET` | ✅ | `user` / `ally` / `admin` |

---

## 📌 Reglas de diseño UX recomendadas

1. **Iniciar el polling** cuando el cliente detecte que su orden cambió a `on_the_way` (escuchando la notificación push o via polling de `/orders/{id}`).
2. **Detener el polling** cuando `order_status` en la respuesta de `/current` sea `done`, `cancelled`, o cualquier valor fuera de `{on_the_way, in_service}`.
3. **Mostrar placeholder de "ally en camino"** mientras `ally_location` sea `null` (el ally aún no reportó posición).
4. **No usar `/route` en cada poll** — es costoso (llama a Google). Úsalo una vez al abrir el mapa y refresca cada 30s o cuando el usuario lo solicite.
5. **Animar el movimiento del pin** suavemente con interpolación entre la posición anterior y la nueva, en lugar de saltos bruscos.
