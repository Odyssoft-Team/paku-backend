# Chat API — Guía de integración para Frontend

Módulo de mensajería en tiempo real (polling) entre el **usuario** y el **ally (groomer)**
durante una orden activa.

---

## Índice

1. [Conceptos clave](#conceptos-clave)
2. [Autenticación](#autenticación)
3. [Endpoints](#endpoints)
   - [Enviar mensaje](#1-post-chatordersorder_idmessages)
   - [Obtener mensajes (polling)](#2-get-chatordersorder_idmessages)
   - [Contador de no leídos](#3-get-chatordersorder_idunread-count)
4. [Flujo de polling recomendado](#flujo-de-polling-recomendado)
5. [Ejemplos completos en React Native / Expo](#ejemplos-completos-en-react-native--expo)
6. [Manejo de errores](#manejo-de-errores)
7. [Preguntas frecuentes](#preguntas-frecuentes)

---

## Conceptos clave

| Concepto | Explicación |
|---|---|
| **Canal de chat** | Siempre está ligado a una `order_id`. No existe chat fuera de una orden. |
| **sender_role** | `"user"` si lo envía el cliente, `"ally"` si lo envía el groomer. |
| **Polling** | El cliente consulta periódicamente si hay mensajes nuevos usando el parámetro `since`. |
| **Cursor (`since`)** | Es el `created_at` del último mensaje que ya tienes. El servidor devuelve solo lo que vino después. |
| **is_read** | Se marca `true` automáticamente cuando el destinatario hace GET a los mensajes. |

---

## Autenticación

Todos los endpoints requieren el token JWT del usuario en el header:

```
Authorization: Bearer <access_token>
```

El backend determina automáticamente si eres el usuario o el ally según el token.
Si no eres dueño de la orden ni el ally asignado, recibirás `403 Forbidden`.

---

## Endpoints

### Base URL

```
https://<tu-dominio>/chat
```

---

### 1. `POST /chat/orders/{order_id}/messages`

Envía un nuevo mensaje en la conversación de la orden.

#### Request

```
POST /chat/orders/3fa85f64-5717-4562-b3fc-2c963f66afa6/messages
Authorization: Bearer eyJ...
Content-Type: application/json
```

```json
{
  "body": "Hola, ya voy en camino 🐾"
}
```

#### Respuesta exitosa `201 Created`

```json
{
  "id": "a1b2c3d4-0000-0000-0000-000000000001",
  "order_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "sender_id": "abc12345-0000-0000-0000-000000000099",
  "sender_role": "ally",
  "body": "Hola, ya voy en camino 🐾",
  "is_read": false,
  "created_at": "2026-05-15T14:32:10.123456+00:00"
}
```

#### Validaciones

| Campo | Regla |
|---|---|
| `body` | Requerido. Mínimo 1 carácter, máximo 2000. |

---

### 2. `GET /chat/orders/{order_id}/messages`

Obtiene los mensajes de la orden. Es el endpoint de **polling**.

#### Parámetros de query

| Parámetro | Tipo | Requerido | Descripción |
|---|---|---|---|
| `since` | `string` ISO-8601 | No | Cursor. Devuelve solo mensajes **posteriores** a este timestamp. |
| `limit` | `integer` | No | Cantidad máxima de mensajes. Default: `50`, máx: `100`. |

#### Primera carga (sin cursor)

```
GET /chat/orders/3fa85f64-5717-4562-b3fc-2c963f66afa6/messages
Authorization: Bearer eyJ...
```

#### Polling con cursor

```
GET /chat/orders/3fa85f64-5717-4562-b3fc-2c963f66afa6/messages?since=2026-05-15T14:32:10.123456%2B00:00
Authorization: Bearer eyJ...
```

> ⚠️ El valor de `since` debe ir **URL-encoded**. El `+` del timezone se convierte en `%2B`.

#### Respuesta exitosa `200 OK`

```json
[
  {
    "id": "a1b2c3d4-0000-0000-0000-000000000001",
    "order_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "sender_id": "abc12345-0000-0000-0000-000000000099",
    "sender_role": "ally",
    "body": "Hola, ya voy en camino 🐾",
    "is_read": true,
    "created_at": "2026-05-15T14:32:10.123456+00:00"
  },
  {
    "id": "a1b2c3d4-0000-0000-0000-000000000002",
    "order_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "sender_id": "user9999-0000-0000-0000-000000000001",
    "sender_role": "user",
    "body": "Perfecto, te espero 👍",
    "is_read": false,
    "created_at": "2026-05-15T14:33:01.456789+00:00"
  }
]
```

> Si no hay mensajes nuevos, el servidor devuelve `[]`. Esto es lo esperado durante el polling normal.

#### Efecto secundario automático

Al hacer GET, el backend marca como leídos todos los mensajes del **otro** participante dirigidos a ti. No necesitas hacer ninguna llamada extra para marcar como leídos.

---

### 3. `GET /chat/orders/{order_id}/unread-count`

Devuelve cuántos mensajes no leídos tienes en la orden. Útil para mostrar el **badge** de notificación sin traer el historial completo.

#### Request

```
GET /chat/orders/3fa85f64-5717-4562-b3fc-2c963f66afa6/unread-count
Authorization: Bearer eyJ...
```

#### Respuesta exitosa `200 OK`

```json
{
  "unread_count": 3
}
```

---

## Flujo de polling recomendado

```
┌─────────────────────────────────────────────────────────┐
│  Al abrir la pantalla de chat                           │
│                                                         │
│  1. GET /messages  (sin since)                         │
│  2. Guardar el created_at del último mensaje → cursor  │
│  3. Mostrar historial                                   │
│                                                         │
│  Cada 3 segundos mientras la pantalla esté activa:     │
│                                                         │
│  4. GET /messages?since=<cursor>                       │
│  5. Si response.length > 0:                            │
│     → Agregar mensajes nuevos al final                 │
│     → Actualizar cursor con el created_at del último   │
│  6. Si response = [] → no hacer nada                   │
│                                                         │
│  Al cerrar la pantalla:                                 │
│  7. Cancelar el intervalo de polling                   │
└─────────────────────────────────────────────────────────┘
```

---

## Ejemplos completos en React Native / Expo

### Hook `useChat` — lógica de polling encapsulada

```typescript
// hooks/useChat.ts
import { useEffect, useRef, useState, useCallback } from "react";

const BASE_URL = process.env.EXPO_PUBLIC_API_URL; // ej: https://api.pakuspa.com
const POLL_INTERVAL_MS = 3000;

export interface ChatMessage {
  id: string;
  order_id: string;
  sender_id: string;
  sender_role: "user" | "ally" | "admin";
  body: string;
  is_read: boolean;
  created_at: string; // ISO-8601
}

export function useChat(orderId: string, accessToken: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);
  const cursorRef = useRef<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const headers = {
    Authorization: `Bearer ${accessToken}`,
    "Content-Type": "application/json",
  };

  // Carga inicial + arranca el polling
  useEffect(() => {
    let cancelled = false;

    const fetchInitial = async () => {
      try {
        const res = await fetch(
          `${BASE_URL}/chat/orders/${orderId}/messages`,
          { headers }
        );
        if (!res.ok) throw new Error(`Error ${res.status}`);
        const data: ChatMessage[] = await res.json();
        if (!cancelled) {
          setMessages(data);
          if (data.length > 0) {
            cursorRef.current = data[data.length - 1].created_at;
          }
        }
      } catch (e: any) {
        if (!cancelled) setError(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchInitial();

    // Polling cada 3 segundos
    intervalRef.current = setInterval(async () => {
      try {
        const since = cursorRef.current;
        const url = since
          ? `${BASE_URL}/chat/orders/${orderId}/messages?since=${encodeURIComponent(since)}`
          : `${BASE_URL}/chat/orders/${orderId}/messages`;

        const res = await fetch(url, { headers });
        if (!res.ok) return; // silencioso en polling — no romper la UI
        const data: ChatMessage[] = await res.json();

        if (!cancelled && data.length > 0) {
          setMessages((prev) => [...prev, ...data]);
          cursorRef.current = data[data.length - 1].created_at;
        }
      } catch {
        // best-effort — el polling no debe romper la UI
      }
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [orderId, accessToken]);

  // Enviar mensaje
  const sendMessage = useCallback(
    async (body: string): Promise<ChatMessage | null> => {
      try {
        const res = await fetch(
          `${BASE_URL}/chat/orders/${orderId}/messages`,
          {
            method: "POST",
            headers,
            body: JSON.stringify({ body }),
          }
        );
        if (!res.ok) throw new Error(`Error ${res.status}`);
        const newMsg: ChatMessage = await res.json();

        // Agregar optimistamente y actualizar cursor
        setMessages((prev) => [...prev, newMsg]);
        cursorRef.current = newMsg.created_at;

        return newMsg;
      } catch (e: any) {
        setError(e.message);
        return null;
      }
    },
    [orderId, accessToken]
  );

  return { messages, loading, error, sendMessage };
}
```

---

### Pantalla de chat `ChatScreen`

```tsx
// screens/ChatScreen.tsx
import React, { useRef, useState } from "react";
import {
  FlatList,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { useChat, ChatMessage } from "../hooks/useChat";

interface Props {
  orderId: string;
  currentUserId: string;
  accessToken: string;
}

export default function ChatScreen({ orderId, currentUserId, accessToken }: Props) {
  const { messages, loading, sendMessage } = useChat(orderId, accessToken);
  const [input, setInput] = useState("");
  const listRef = useRef<FlatList>(null);

  const handleSend = async () => {
    const text = input.trim();
    if (!text) return;
    setInput("");
    await sendMessage(text);
    listRef.current?.scrollToEnd({ animated: true });
  };

  const renderItem = ({ item }: { item: ChatMessage }) => {
    const isMe = item.sender_id === currentUserId;
    return (
      <View style={[styles.bubble, isMe ? styles.bubbleMe : styles.bubbleThem]}>
        <Text style={styles.bubbleText}>{item.body}</Text>
        <Text style={styles.bubbleTime}>
          {new Date(item.created_at).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </Text>
      </View>
    );
  };

  if (loading) return <Text style={styles.loading}>Cargando mensajes...</Text>;

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      <FlatList
        ref={listRef}
        data={messages}
        keyExtractor={(item) => item.id}
        renderItem={renderItem}
        onContentSizeChange={() => listRef.current?.scrollToEnd()}
        contentContainerStyle={styles.list}
      />
      <View style={styles.inputRow}>
        <TextInput
          style={styles.input}
          value={input}
          onChangeText={setInput}
          placeholder="Escribe un mensaje..."
          multiline
          maxLength={2000}
        />
        <TouchableOpacity style={styles.sendBtn} onPress={handleSend}>
          <Text style={styles.sendText}>Enviar</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container:   { flex: 1, backgroundColor: "#f5f5f5" },
  list:        { padding: 12 },
  loading:     { textAlign: "center", marginTop: 40 },
  bubble:      { maxWidth: "75%", borderRadius: 16, padding: 10, marginBottom: 8 },
  bubbleMe:    { backgroundColor: "#4F46E5", alignSelf: "flex-end" },
  bubbleThem:  { backgroundColor: "#ffffff", alignSelf: "flex-start", borderWidth: 1, borderColor: "#e5e7eb" },
  bubbleText:  { fontSize: 15, color: "#111" },
  bubbleTime:  { fontSize: 11, color: "#9ca3af", marginTop: 4, textAlign: "right" },
  inputRow:    { flexDirection: "row", padding: 8, backgroundColor: "#fff", borderTopWidth: 1, borderColor: "#e5e7eb" },
  input:       { flex: 1, backgroundColor: "#f3f4f6", borderRadius: 20, paddingHorizontal: 16, paddingVertical: 8, fontSize: 15, maxHeight: 100 },
  sendBtn:     { justifyContent: "center", paddingHorizontal: 16 },
  sendText:    { color: "#4F46E5", fontWeight: "700" },
});
```

---

### Badge de mensajes no leídos

```tsx
// Ejemplo: mostrar badge en la tarjeta de la orden
import { useEffect, useState } from "react";

function useUnreadCount(orderId: string, accessToken: string) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    const fetch_ = async () => {
      const res = await fetch(
        `${process.env.EXPO_PUBLIC_API_URL}/chat/orders/${orderId}/unread-count`,
        { headers: { Authorization: `Bearer ${accessToken}` } }
      );
      if (res.ok) {
        const { unread_count } = await res.json();
        setCount(unread_count);
      }
    };

    fetch_();
    const id = setInterval(fetch_, 10_000); // badge se refresca cada 10s
    return () => clearInterval(id);
  }, [orderId, accessToken]);

  return count;
}
```

---

## Manejo de errores

| Código | Causa | Acción recomendada |
|---|---|---|
| `401 Unauthorized` | Token expirado o inválido | Redirigir a login / refrescar token |
| `403 Forbidden` | No eres dueño de la orden ni el ally | No mostrar el chat |
| `404 Not Found` | La orden no existe | Mostrar error "Orden no encontrada" |
| `422 Unprocessable Entity` | Mensaje vacío o supera 2000 caracteres | Validar antes de enviar |
| `500 Internal Server Error` | Error del servidor | Reintentar con backoff exponencial |

---

## Preguntas frecuentes

**¿El chat funciona aunque la orden no esté `in_service`?**
Sí. El acceso al chat no está restringido al estado de la orden — funciona en cualquier estado activo. La restricción de `in_service` solo aplica al módulo de streaming (video).

**¿Qué pasa si cierro la app mientras hay mensajes no leídos?**
Recibirás una **push notification** cuando llegue un mensaje nuevo. El backend la envía automáticamente al destinatario cada vez que alguien manda un mensaje.

**¿El polling consume mucha batería?**
Un `setInterval` de 3s con una petición HTTP ligera tiene impacto mínimo. Si quieres ser más conservador, puedes aumentarlo a 5s cuando la app está en segundo plano usando `AppState` de React Native.

```typescript
import { AppState } from "react-native";

// Reducir frecuencia en background
AppState.addEventListener("change", (state) => {
  if (state === "background") {
    // Cambiar a 10s o pausar el polling
  } else if (state === "active") {
    // Volver a 3s
  }
});
```

**¿Puedo mostrar "escribiendo..."?**
No hay soporte nativo para eso en esta versión. Si se necesita en el futuro, requiere WebSocket + Redis (se puede agregar sin cambios de DB).

**¿Hay límite de mensajes por orden?**
No hay límite en la base de datos. El parámetro `limit` (default 50) solo aplica a cada llamada de polling.
