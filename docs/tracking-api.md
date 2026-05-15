# Tracking API — Guía de integración para Frontend

Seguimiento en tiempo real del groomer (ally) en camino al domicilio del cliente.
Funciona similar a Rappi/Uber: el ally envía su GPS periódicamente y el cliente
ve su posición en el mapa con ETA actualizado.

---

## Índice

1. [Cómo funciona](#cómo-funciona)
2. [Estados de la orden y tracking](#estados-de-la-orden-y-tracking)
3. [Autenticación](#autenticación)
4. [Endpoints](#endpoints)
   - [Ally: reportar posición](#1-post-trackingordersorder_idlocation)
   - [Cliente: obtener posición actual](#2-get-trackingordersorder_idcurrent)
   - [Cliente: ruta y ETA](#3-get-trackingordersorder_idroute)
5. [Flujos recomendados](#flujos-recomendados)
6. [Ejemplos completos en React Native / Expo](#ejemplos-completos-en-react-native--expo)
7. [Manejo de errores](#manejo-de-errores)
8. [Preguntas frecuentes](#preguntas-frecuentes)

---

## Cómo funciona

```
[App Ally]  →  POST /location (cada 10s)  →  [Backend]  →  PostgreSQL
                                                                ↓
[App Cliente]  ←  GET /current (cada 10s)  ←  [Backend]  ←  PostgreSQL
```

1. El **ally** reporta su lat/lng cada **10 segundos** al backend.
2. El **backend** guarda la última posición en PostgreSQL (upsert — siempre 1 fila por orden).
3. El **cliente** hace polling cada 10 segundos para obtener la posición actualizada.
4. Opcionalmente el cliente llama a `/route` para obtener la **polyline dibujable** y el **ETA**.

---

## Estados de la orden y tracking

| Estado de la orden | ¿Ally puede reportar? | ¿Cliente puede ver? |
|---|---|---|
| `created` | ❌ | ❌ |
| `accepted` | ❌ | ❌ |
| `on_the_way` | ✅ **Activo** | ✅ **Activo** |
| `in_service` | ✅ (ya llegó, pero el mapa puede seguir abierto) | ✅ |
| `done` | ❌ | ❌ |
| `cancelled` | ❌ | ❌ |

> Fuera de `on_the_way` e `in_service` el backend devuelve `409 Conflict`.

---

## Autenticación

Todos los endpoints requieren el token JWT en el header:

```
Authorization: Bearer <access_token>
```

| Endpoint | Quién puede llamarlo |
|---|---|
| `POST /location` | Solo el **ally** asignado a la orden (`role: "ally"`) |
| `GET /current` | Cliente dueño, ally asignado o admin |
| `GET /route` | Cliente dueño, ally asignado o admin |

---

## Endpoints

### Base URL

```
https://<tu-dominio>/tracking
```

---

### 1. `POST /tracking/orders/{order_id}/location`

**Lo llama el app del ALLY.** Envía la posición GPS actual. Llamar cada **10 segundos**.

#### Request

```
POST /tracking/orders/3fa85f64-5717-4562-b3fc-2c963f66afa6/location
Authorization: Bearer eyJ...  (token del ally)
Content-Type: application/json
```

```json
{
  "lat": -12.046374,
  "lng": -77.042793,
  "accuracy_m": 8.5
}
```

#### Parámetros del body

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `lat` | `float` | ✅ | Latitud WGS-84. Rango: -90 a 90 |
| `lng` | `float` | ✅ | Longitud WGS-84. Rango: -180 a 180 |
| `accuracy_m` | `float` | ❌ | Precisión GPS en metros. Viene de `Location.accuracy` en Expo |

#### Respuesta exitosa `201 Created`

```json
{
  "order_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "lat": -12.046374,
  "lng": -77.042793,
  "recorded_at": "2026-05-15T15:00:10.000000+00:00"
}
```

---

### 2. `GET /tracking/orders/{order_id}/current`

**Lo llama el app del CLIENTE.** Devuelve la última posición del ally y las coordenadas del destino. Hacer polling cada **10 segundos**.

#### Request

```
GET /tracking/orders/3fa85f64-5717-4562-b3fc-2c963f66afa6/current
Authorization: Bearer eyJ...
```

#### Respuesta exitosa `200 OK`

```json
{
  "order_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "order_status": "on_the_way",
  "ally_location": {
    "lat": -12.046374,
    "lng": -77.042793,
    "accuracy_m": 8.5,
    "recorded_at": "2026-05-15T15:00:10.000000+00:00"
  },
  "destination": {
    "lat": -12.051200,
    "lng": -77.039800,
    "accuracy_m": null,
    "recorded_at": null
  },
  "staleness_seconds": 4
}
```

#### Campos clave

| Campo | Descripción |
|---|---|
| `ally_location` | `null` si el ally aún no envió su primera posición |
| `destination` | Coordenadas del domicilio del cliente (fijas, desde la orden) |
| `staleness_seconds` | Segundos desde el último reporte del ally. Si supera ~30s, mostrar aviso "Actualizando ubicación..." |

---

### 3. `GET /tracking/orders/{order_id}/route`

**Lo llama el app del CLIENTE.** Devuelve la polyline dibujable en el mapa y el ETA calculado por Google Routes API en tiempo real.

> ℹ️ Este endpoint tiene un costo por llamada en Google Routes API. Úsalo con menos frecuencia que `/current` (cada 30s es suficiente).

#### Request

```
GET /tracking/orders/3fa85f64-5717-4562-b3fc-2c963f66afa6/route
Authorization: Bearer eyJ...
```

#### Respuesta exitosa `200 OK`

```json
{
  "order_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "ally_location": {
    "lat": -12.046374,
    "lng": -77.042793,
    "accuracy_m": 8.5,
    "recorded_at": "2026-05-15T15:00:10.000000+00:00"
  },
  "destination": {
    "lat": -12.051200,
    "lng": -77.039800,
    "accuracy_m": null,
    "recorded_at": null
  },
  "eta_seconds": 420,
  "eta_display": "7 min",
  "polyline": "q`~rLpkacJdAuC...",
  "distance_meters": 1240
}
```

#### Campos clave

| Campo | Puede ser `null`? | Descripción |
|---|---|---|
| `eta_seconds` | ✅ | ETA en segundos. Usar para lógica interna. |
| `eta_display` | ✅ | ETA formateado para mostrar al usuario. Ej: `"7 min"`, `"1 h 2 min"` |
| `polyline` | ✅ | Encoded polyline para dibujar en el mapa con Google Maps SDK o Mapbox |
| `distance_meters` | ✅ | Distancia restante en metros |

> Todos los campos pueden ser `null` si el ally aún no reportó su posición (no hay origen).

---

## Flujos recomendados

### App del Ally — reportar posición

```
Al cambiar orden a on_the_way:
  1. Solicitar permisos de ubicación (foreground + background)
  2. Iniciar LocationSubscription con intervalo de 10 segundos
  3. Por cada actualización → POST /tracking/orders/{id}/location
  4. Al cambiar a in_service o done/cancelled → detener el subscription
```

### App del Cliente — ver el mapa

```
Al detectar que order_status = on_the_way:
  1. Mostrar pantalla de mapa
  2. GET /current (para posición inicial)
  3. Cada 10s → GET /current (actualizar marcador del ally)
  4. Cada 30s → GET /route (actualizar polyline y ETA)
  5. Al detectar order_status = in_service → cambiar UI ("¡Ya llegó!")
  6. Al cerrar el mapa → cancelar los intervalos
```

---

## Ejemplos completos en React Native / Expo

### App del Ally — `useLocationReporter.ts`

```typescript
// hooks/useLocationReporter.ts
import { useEffect, useRef } from "react";
import * as Location from "expo-location";

const BASE_URL = process.env.EXPO_PUBLIC_API_URL;
const REPORT_INTERVAL_MS = 10_000; // 10 segundos

export function useLocationReporter(
  orderId: string,
  accessToken: string,
  active: boolean  // true cuando order_status === "on_the_way" || "in_service"
) {
  const subRef = useRef<Location.LocationSubscription | null>(null);

  useEffect(() => {
    if (!active) {
      subRef.current?.remove();
      subRef.current = null;
      return;
    }

    let mounted = true;

    const start = async () => {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== "granted") {
        console.warn("Permiso de ubicación denegado");
        return;
      }

      subRef.current = await Location.watchPositionAsync(
        {
          accuracy: Location.Accuracy.High,
          timeInterval: REPORT_INTERVAL_MS,
          distanceInterval: 10, // mínimo 10m de movimiento para reportar
        },
        async (loc) => {
          if (!mounted) return;
          try {
            await fetch(`${BASE_URL}/tracking/orders/${orderId}/location`, {
              method: "POST",
              headers: {
                Authorization: `Bearer ${accessToken}`,
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                lat: loc.coords.latitude,
                lng: loc.coords.longitude,
                accuracy_m: loc.coords.accuracy ?? undefined,
              }),
            });
          } catch {
            // best-effort — no interrumpir al ally si hay error de red momentáneo
          }
        }
      );
    };

    start();

    return () => {
      mounted = false;
      subRef.current?.remove();
      subRef.current = null;
    };
  }, [orderId, accessToken, active]);
}
```

---

### App del Cliente — `useAllyTracking.ts`

```typescript
// hooks/useAllyTracking.ts
import { useEffect, useRef, useState } from "react";

const BASE_URL = process.env.EXPO_PUBLIC_API_URL;

export interface LocationPoint {
  lat: number;
  lng: number;
  accuracy_m: number | null;
  recorded_at: string | null;
}

export interface TrackingState {
  allyLocation: LocationPoint | null;
  destination: LocationPoint | null;
  stalenessSeconds: number | null;
  etaDisplay: string | null;
  polyline: string | null;
  loading: boolean;
}

export function useAllyTracking(
  orderId: string,
  accessToken: string,
  active: boolean  // true cuando order_status === "on_the_way" || "in_service"
) {
  const [state, setState] = useState<TrackingState>({
    allyLocation: null,
    destination: null,
    stalenessSeconds: null,
    etaDisplay: null,
    polyline: null,
    loading: true,
  });

  const headers = { Authorization: `Bearer ${accessToken}` };

  useEffect(() => {
    if (!active) return;

    let cancelled = false;

    // Polling de posición cada 10 segundos
    const fetchCurrent = async () => {
      try {
        const res = await fetch(
          `${BASE_URL}/tracking/orders/${orderId}/current`,
          { headers }
        );
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled) {
          setState((prev) => ({
            ...prev,
            allyLocation: data.ally_location,
            destination: data.destination,
            stalenessSeconds: data.staleness_seconds,
            loading: false,
          }));
        }
      } catch {
        if (!cancelled) setState((prev) => ({ ...prev, loading: false }));
      }
    };

    // Polling de ruta/ETA cada 30 segundos (costo por llamada a Google Routes)
    const fetchRoute = async () => {
      try {
        const res = await fetch(
          `${BASE_URL}/tracking/orders/${orderId}/route`,
          { headers }
        );
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled) {
          setState((prev) => ({
            ...prev,
            etaDisplay: data.eta_display,
            polyline: data.polyline,
          }));
        }
      } catch {}
    };

    fetchCurrent();
    fetchRoute();

    const currentInterval = setInterval(fetchCurrent, 10_000);
    const routeInterval = setInterval(fetchRoute, 30_000);

    return () => {
      cancelled = true;
      clearInterval(currentInterval);
      clearInterval(routeInterval);
    };
  }, [orderId, accessToken, active]);

  return state;
}
```

---

### Pantalla del mapa — `TrackingMapScreen.tsx`

```tsx
// screens/TrackingMapScreen.tsx
import React from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import MapView, { Marker, Polyline } from "react-native-maps";
import { decodePolyline } from "../utils/polyline"; // ver nota abajo
import { useAllyTracking } from "../hooks/useAllyTracking";

interface Props {
  orderId: string;
  accessToken: string;
  orderStatus: string;
}

export default function TrackingMapScreen({ orderId, accessToken, orderStatus }: Props) {
  const active = orderStatus === "on_the_way" || orderStatus === "in_service";
  const { allyLocation, destination, stalenessSeconds, etaDisplay, polyline, loading } =
    useAllyTracking(orderId, accessToken, active);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#4F46E5" />
        <Text style={styles.loadingText}>Localizando al groomer...</Text>
      </View>
    );
  }

  const routeCoords = polyline ? decodePolyline(polyline) : [];

  return (
    <View style={styles.container}>
      {/* Banner ETA */}
      {etaDisplay && (
        <View style={styles.etaBanner}>
          <Text style={styles.etaText}>🐾 Tu groomer llega en {etaDisplay}</Text>
        </View>
      )}

      {/* Aviso de datos desactualizados */}
      {stalenessSeconds !== null && stalenessSeconds > 30 && (
        <View style={styles.staleBanner}>
          <Text style={styles.staleText}>Actualizando ubicación...</Text>
        </View>
      )}

      <MapView
        style={styles.map}
        initialRegion={
          destination
            ? {
                latitude: destination.lat,
                longitude: destination.lng,
                latitudeDelta: 0.02,
                longitudeDelta: 0.02,
              }
            : undefined
        }
      >
        {/* Marcador del ally */}
        {allyLocation && (
          <Marker
            coordinate={{ latitude: allyLocation.lat, longitude: allyLocation.lng }}
            title="Tu groomer"
            pinColor="#4F46E5"
          />
        )}

        {/* Marcador del destino (domicilio del cliente) */}
        {destination && (
          <Marker
            coordinate={{ latitude: destination.lat, longitude: destination.lng }}
            title="Tu domicilio"
            pinColor="#22C55E"
          />
        )}

        {/* Ruta dibujada */}
        {routeCoords.length > 0 && (
          <Polyline
            coordinates={routeCoords}
            strokeColor="#4F46E5"
            strokeWidth={4}
          />
        )}
      </MapView>
    </View>
  );
}

const styles = StyleSheet.create({
  container:    { flex: 1 },
  map:          { flex: 1 },
  center:       { flex: 1, justifyContent: "center", alignItems: "center" },
  loadingText:  { marginTop: 12, color: "#6b7280" },
  etaBanner:    { backgroundColor: "#4F46E5", padding: 14, alignItems: "center" },
  etaText:      { color: "#fff", fontWeight: "700", fontSize: 16 },
  staleBanner:  { backgroundColor: "#fef3c7", padding: 8, alignItems: "center" },
  staleText:    { color: "#92400e", fontSize: 13 },
});
```

> **Nota sobre `decodePolyline`:** el campo `polyline` devuelto por el backend es un
> [Encoded Polyline de Google](https://developers.google.com/maps/documentation/utilities/polylinealgorithm).
> Puedes decodificarlo con el paquete `@mapbox/polyline` o `@googlemaps/polyline-codec`:
>
> ```bash
> npx expo install @mapbox/polyline
> ```
>
> ```typescript
> // utils/polyline.ts
> import polyline from "@mapbox/polyline";
>
> export function decodePolyline(encoded: string) {
>   return polyline.decode(encoded).map(([lat, lng]) => ({ latitude: lat, longitude: lng }));
> }
> ```

---

## Manejo de errores

| Código | Causa | Acción recomendada |
|---|---|---|
| `401 Unauthorized` | Token expirado | Refrescar token o redirigir a login |
| `403 Forbidden` | El ally no es el asignado a la orden | No iniciar el reporter |
| `404 Not Found` | Orden inexistente | Mostrar error y redirigir |
| `409 Conflict` | La orden no está en `on_the_way` ni `in_service` | Detener el polling/reporter silenciosamente |
| `501 Not Implemented` | `GOOGLE_ROUTES_API_KEY` no configurada (solo `/route`) | Ocultar la polyline y ETA, mostrar solo el marcador |
| `502 Bad Gateway` | Google Routes falló | Mantener la polyline anterior, reintentar en el siguiente ciclo |

---

## Preguntas frecuentes

**¿Qué pasa si el ally no tiene señal por unos segundos?**
El cliente simplemente muestra la última posición conocida. El campo `staleness_seconds` te dice cuántos segundos tienen esos datos. Si supera 30s, muestra "Actualizando ubicación...".

**¿Necesito Google Maps SDK para mostrar el mapa?**
No es obligatorio. Puedes usar `react-native-maps` (incluye Google Maps en Android y Apple Maps en iOS). Para la polyline, cualquier proveedor que acepte coordenadas lat/lng funciona.

**¿Debo pedir permisos de ubicación en background?**
Para el **ally** solo se necesitan permisos `foreground` mientras tiene la app abierta. Si quieres que reporte en background, solicita `background` permissions y usa `expo-task-manager`. Para el **cliente** no se necesita ningún permiso de ubicación.

**¿Qué tan preciso es el ETA?**
Viene de Google Routes API con `TRAFFIC_AWARE`, es decir, considera el tráfico en tiempo real. Es el mismo cálculo que usa Google Maps. La precisión es muy alta.

**¿El `/route` tiene costo extra?**
Sí. Google Routes API cobra por request. Por eso se recomienda llamarlo cada **30 segundos** (no cada 10s como `/current`). La posición del marcador se actualiza con `/current` a 10s; la ruta y ETA se actualizan con `/route` a 30s.

**¿Qué pasa al finalizar el servicio (`done`)?**
El backend rechaza nuevos reportes de posición con `409`. El cliente detecta `order_status = "done"` en el polling y debe cerrar el mapa y cancelar los intervalos.
