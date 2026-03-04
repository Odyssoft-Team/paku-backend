# 📱 Guía de Integración — Streaming en Vivo (Frontend)

> Dirigido al desarrollador de la app React Native.  
> Esta guía reemplaza el flujo anterior donde se ingresaba un código de sala manualmente.

---

## ¿Qué cambió?

Antes tenían que ingresar un código de sala a mano en ambos dispositivos para conectarse.  
**Ahora el código de sala lo provee el backend automáticamente**, derivado del UUID de la orden.  
Ninguna de las dos partes escribe nada: la app lo obtiene de una sola llamada autenticada.

---

## Flujo general

```
1. El servicio pasa a estado "in_service"  (lo gestiona el ally/admin, ya existía)
        ↓
2. Ally pulsa "Iniciar transmisión" en su app
   → App llama al nuevo endpoint con el order_id  →  recibe ws_url, ice_servers, role="host"
   → App conecta el WebSocket y genera el WebRTC offer
        ↓
3. Cliente pulsa "Ver transmisión" en su app
   → App llama al nuevo endpoint con el mismo order_id  →  recibe ws_url, ice_servers, role="viewer"
   → App conecta el WebSocket y espera el offer
        ↓
4. Señalización WebRTC ocurre normalmente (sin cambios respecto a lo que ya tenían)
```

---

## 1. Prerequisito — El order_id

Ambas apps (ally y cliente) ya tienen el `order_id` disponible: es el UUID de la orden activa que están viendo en pantalla. **No hay que pedírselo al usuario ni generarlo.**

---

## 2. Nuevo endpoint — Obtener sesión de streaming

### `GET /streaming/orders/{order_id}/session`

**Requiere:** JWT del usuario autenticado en el header `Authorization: Bearer <token>`  
**Disponible solo cuando:** la orden está en estado `in_service`

### Ejemplo de llamada

```js
const response = await fetch(
  `https://api.paku.app/streaming/orders/${orderId}/session`,
  {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${userToken}`,
      'Content-Type': 'application/json',
    },
  }
);

const session = await response.json();
```

### Respuesta exitosa `200 OK`

```json
{
  "room_id": "550e8400-e29b-41d4-a716-446655440000",
  "order_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "aaa-bbb-ccc",
  "ally_id": "ddd-eee-fff",
  "order_status": "in_service",
  "role": "host",
  "ws_url": "wss://stream.dev-qa.site/ws?room=550e8400-e29b-41d4-a716-446655440000",
  "ice_servers": [
    {
      "urls": ["stun:stun.l.google.com:19302"]
    },
    {
      "urls": [
        "turn:stream.dev-qa.site:3478?transport=udp",
        "turn:stream.dev-qa.site:3478?transport=tcp"
      ],
      "username": "webrtc",
      "credential": "webrtc123"
    }
  ]
}
```

### Campos importantes

| Campo | Descripción |
|---|---|
| `role` | `"host"` si quien llama es el **ally** → genera el offer. `"viewer"` si es el **cliente** → espera el offer. |
| `ws_url` | URL completa del WebSocket. Úsala directamente: `new WebSocket(session.ws_url)` |
| `ice_servers` | Configuración ICE/TURN. Pásala directo a `RTCPeerConnection` |
| `room_id` | El código de sala. Ya viene incluido en `ws_url`, pero lo tienes disponible por si lo necesitas |

### Errores posibles

| HTTP | Cuándo ocurre |
|---|---|
| `401` | El token JWT no es válido o no se envió |
| `403` | El usuario autenticado no es el cliente ni el ally de esa orden |
| `404` | La orden no existe |
| `409` | La orden existe pero **no está en `in_service`** (aún no comenzó el servicio o ya terminó) |

---

## 3. Cómo usar la respuesta para iniciar WebRTC

Esto reemplaza el lugar donde antes construían `iceServers` y la URL del WebSocket a mano.

```js
import {
  RTCPeerConnection,
  mediaDevices,
} from 'react-native-webrtc';

async function startStreamingSession(orderId, userToken) {

  // PASO 1 — Obtener sesión del backend
  const response = await fetch(
    `https://api.paku.app/streaming/orders/${orderId}/session`,
    { headers: { Authorization: `Bearer ${userToken}` } }
  );

  if (!response.ok) {
    const error = await response.json();
    // Manejar 401, 403, 404, 409 según corresponda en la UI
    throw new Error(error.detail);
  }

  const session = await response.json();
  // session.role === "host"   → soy el ally, debo generar el offer
  // session.role === "viewer" → soy el cliente, debo esperar el offer

  // PASO 2 — Conectar WebSocket (la URL ya trae el room incluido)
  const ws = new WebSocket(session.ws_url);

  // PASO 3 — Crear RTCPeerConnection con los ice_servers del backend
  const pc = new RTCPeerConnection({
    iceServers: session.ice_servers,  // ← directo de la respuesta, sin hardcodear
  });

  // PASO 4 — Obtener media local
  const stream = await mediaDevices.getUserMedia({ video: true, audio: true });
  stream.getTracks().forEach(track => pc.addTrack(track, stream));

  // PASO 5 — Señalización según rol
  if (session.role === 'host') {
    // Ally: esperar a que el cliente se conecte, luego generar offer
    ws.onopen = async () => {
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      ws.send(JSON.stringify(offer));
    };
  }

  if (session.role === 'viewer') {
    // Cliente: esperar el offer del ally
    ws.onmessage = async (event) => {
      const message = JSON.parse(event.data);

      if (message.type === 'offer') {
        await pc.setRemoteDescription(message);
        const answer = await pc.createAnswer();
        await pc.setLocalDescription(answer);
        ws.send(JSON.stringify(answer));
      }

      if (message.type === 'answer') {
        await pc.setRemoteDescription(message);
      }

      if (message.candidate) {
        await pc.addIceCandidate(message);
      }
    };
  }

  // ICE candidates (aplica para ambos roles)
  pc.onicecandidate = (event) => {
    if (event.candidate) {
      ws.send(JSON.stringify(event.candidate));
    }
  };

  return { pc, ws, session };
}
```

---

## 4. Cuándo llamar al endpoint (recomendación UX)

| Quién | Cuándo llamar |
|---|---|
| **Ally** | Cuando pulsa el botón "Iniciar transmisión". Si la orden no está en `in_service` aún, el backend retorna `409` y la app puede mostrar "El servicio aún no ha comenzado". |
| **Cliente** | Cuando pulsa "Ver transmisión en vivo". Si el ally aún no inició, la conexión WebSocket simplemente esperará hasta que el otro participante entre a la sala. |

> El endpoint **no inicia ni detiene** la transmisión. Solo provee las credenciales para conectarse. El ciclo de vida real de la sala lo gestiona el signaling server.

---

## 5. Lo que NO cambia respecto a la integración anterior

- La librería `react-native-webrtc` es la misma
- El servidor de señalización (`wss://stream.dev-qa.site`) es el mismo
- El flujo WebRTC (offer → answer → ICE candidates) es exactamente igual
- La configuración de estados (`oniceconnectionstatechange`, etc.) es igual
- La lógica de reconexión es igual

**Lo único que cambia es el origen del `room_id` y los `ice_servers`:** antes estaban hardcodeados o se ingresaban a mano, ahora vienen del backend con una sola llamada autenticada.

---

## 6. Resumen en una línea

> Llama a `GET /streaming/orders/{order_id}/session` con el JWT, usa `ws_url` para el WebSocket, `ice_servers` para el `RTCPeerConnection`, y `role` para saber si generas el offer (`host`) o lo esperas (`viewer`). Todo lo demás sigue igual.
