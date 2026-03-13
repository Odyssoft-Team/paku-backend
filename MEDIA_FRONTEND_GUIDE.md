# 📸 Guía de Integración Frontend — Fotos de Perfil (Users & Pets)

> **Fecha:** 13 de marzo de 2026  
> **Base URL:** `https://<tu-dominio>` (sin prefijo `/api/v1`)  
> **Autenticación:** `Authorization: Bearer <access_token>` en todos los endpoints.

---

## ⚙️ Cómo funciona el flujo (conceptual)

El backend **nunca recibe el archivo directamente**. El flujo es:

```
Frontend → [1] Pide URL firmada al backend
         → [2] Sube el binario DIRECTO a GCS usando esa URL
         → [3] Confirma al backend que la subida fue exitosa
         → [4] Backend persiste el objeto y devuelve URL de lectura
```

Las imágenes viven en **Google Cloud Storage (GCS)**. El bucket es **privado** — no hay URLs públicas. Cada vez que necesites mostrar una imagen debes pedir una **signed read URL** al backend.

---

## 🔒 Restricciones importantes

| Restricción | Detalle |
|---|---|
| Formatos aceptados | `image/jpeg`, `image/png`, `image/webp` |
| Signed URL TTL | Entre 60 y 900 segundos (default: 300 = 5 min) |
| Ownership | Solo puedes subir/leer fotos de tu propio usuario o de tus mascotas |
| `photo_url` / `profile_photo_url` | **No** se aceptan en endpoints generales (register, update profile, update pet). Solo se actualizan vía este flujo. |

---

## 📐 Flujo completo: Foto de perfil de usuario

### Paso 1 — Pedir signed URL de subida

```http
POST /media/signed-upload
Authorization: Bearer <token>
Content-Type: application/json

{
  "entity_type": "user",
  "entity_id": "<user_uuid>",        // debe ser el UUID del usuario autenticado
  "content_type": "image/jpeg"        // o image/png / image/webp
}
```

**Respuesta `201`:**
```json
{
  "upload_url": "https://storage.googleapis.com/...",  // URL firmada para PUT
  "object_name": "users/<uuid>/profile_20260311T120000000000Z.jpg",
  "content_type": "image/jpeg",
  "expires_in": 300
}
```

> ⚠️ Guarda `object_name` — lo necesitarás en los pasos 3 y 4.

---

### Paso 2 — Subir el archivo directamente a GCS

```http
PUT <upload_url>                   // la URL del paso 1 (NO va por el backend)
Content-Type: image/jpeg           // debe coincidir EXACTAMENTE con lo enviado en paso 1
Body: <binary file data>
```

> ⚠️ El header `Content-Type` debe ser idéntico al que enviaste en el paso 1. Si no coincide, GCS rechazará la subida con 403.

**Respuesta esperada:** `200 OK` vacío de GCS.

---

### Paso 3 — Confirmar la foto al backend

```http
POST /media/confirm-profile-photo
Authorization: Bearer <token>
Content-Type: application/json

{
  "entity_type": "user",
  "entity_id": "<user_uuid>",
  "object_name": "users/<uuid>/profile_20260311T120000000000Z.jpg"  // del paso 1
}
```

**Respuesta `200`:**
```json
{
  "object_name": "users/<uuid>/profile_20260311T120000000000Z.jpg",
  "read_url": "https://storage.googleapis.com/...",   // URL firmada para mostrar la imagen
  "expires_in": 300
}
```

✅ En este momento la foto está guardada en BD (`users.profile_photo_url = object_name`).  
✅ La `read_url` devuelta está lista para mostrar directamente en un `<Image>` o `<img>`.

---

## 🐾 Flujo completo: Foto de perfil de mascota

Idéntico al de usuario, cambiando `entity_type` y `entity_id`:

### Paso 1 — Pedir signed URL de subida

```http
POST /media/signed-upload
Authorization: Bearer <token>
Content-Type: application/json

{
  "entity_type": "pet",
  "entity_id": "<pet_uuid>",          // UUID de la mascota (debe ser tuya)
  "content_type": "image/webp"
}
```

**Respuesta `201`:**
```json
{
  "upload_url": "https://storage.googleapis.com/...",
  "object_name": "pets/<uuid>/profile_20260311T120000000000Z.webp",
  "content_type": "image/webp",
  "expires_in": 300
}
```

### Paso 2 — Subir a GCS (igual que usuario)

```http
PUT <upload_url>
Content-Type: image/webp
Body: <binary>
```

### Paso 3 — Confirmar

```http
POST /media/confirm-profile-photo
Authorization: Bearer <token>
Content-Type: application/json

{
  "entity_type": "pet",
  "entity_id": "<pet_uuid>",
  "object_name": "pets/<uuid>/profile_20260311T120000000000Z.webp"
}
```

**Respuesta `200`:**
```json
{
  "object_name": "pets/<uuid>/profile_20260311T120000000000Z.webp",
  "read_url": "https://storage.googleapis.com/...",
  "expires_in": 300
}
```

---

## 🖼️ Cómo mostrar una imagen guardada

Cuando el backend devuelve `profile_photo_url` (usuario) o `photo_url` (mascota) en cualquier response (GET /users/me, GET /pets, etc.), ese valor es un **`object_name`**, no una URL pública.

Para renderizarla debes pedir una signed read URL:

```http
POST /media/signed-read
Authorization: Bearer <token>
Content-Type: application/json

{
  "object_name": "users/<uuid>/profile_20260311T120000000000Z.jpg"
  // o "pets/<uuid>/profile_..."
}
```

**Respuesta `200`:**
```json
{
  "read_url": "https://storage.googleapis.com/...",
  "expires_in": 300
}
```

Usa `read_url` directamente como `src` de la imagen. **Caduca en `expires_in` segundos** — no la guardes en caché permanente.

---

## 💡 Ejemplo en código (React Native / TypeScript)

```typescript
// 1. Selección de imagen (con expo-image-picker u otra librería)
const result = await ImagePicker.launchImageLibraryAsync({
  mediaTypes: ImagePicker.MediaTypeOptions.Images,
  quality: 0.8,
});
if (result.canceled) return;
const asset = result.assets[0];
const contentType = asset.mimeType ?? 'image/jpeg'; // 'image/jpeg' | 'image/png' | 'image/webp'

// 2. Pedir signed upload URL al backend
const signedRes = await fetch(`${BASE_URL}/media/signed-upload`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    entity_type: 'user',        // o 'pet'
    entity_id: currentUser.id,  // o pet.id
    content_type: contentType,
  }),
});
if (!signedRes.ok) throw new Error('Failed to get upload URL');
const { upload_url, object_name } = await signedRes.json();

// 3. Subir binario DIRECTO a GCS (sin token, sin backend)
const fileBlob = await fetch(asset.uri).then(r => r.blob());
const uploadRes = await fetch(upload_url, {
  method: 'PUT',
  headers: { 'Content-Type': contentType },  // ⚠️ debe coincidir exactamente
  body: fileBlob,
});
if (!uploadRes.ok) throw new Error('Failed to upload to GCS');

// 4. Confirmar al backend
const confirmRes = await fetch(`${BASE_URL}/media/confirm-profile-photo`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    entity_type: 'user',        // o 'pet'
    entity_id: currentUser.id,  // o pet.id
    object_name,                // el que devolvió el paso 2 — NO modificar
  }),
});
if (!confirmRes.ok) throw new Error('Failed to confirm photo');
const { read_url } = await confirmRes.json();

// 5. Mostrar la imagen
setProfilePhotoUri(read_url);
```

---

## 🔄 Cómo mostrar foto al cargar perfil

```typescript
async function loadProfilePhoto(objectName: string | null): Promise<string | null> {
  if (!objectName) return null;

  const res = await fetch(`${BASE_URL}/media/signed-read`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ object_name: objectName }),
  });
  if (!res.ok) return null;
  const { read_url } = await res.json();
  return read_url;
}

// Uso:
const user = await getMe(); // GET /users/me → devuelve profile_photo_url (object_name o null)
const photoUri = await loadProfilePhoto(user.profile_photo_url);

// Para mascota:
const pet = await getPet(petId); // GET /pets/{id} → devuelve photo_url (object_name o null)
const petPhotoUri = await loadProfilePhoto(pet.photo_url);
```

---

## ❌ Errores comunes

| Código | Causa | Solución |
|---|---|---|
| `400 Unsupported content_type` | Formato no permitido | Usar solo `image/jpeg`, `image/png`, `image/webp` |
| `400 Invalid object_name` | `object_name` mal formado en confirm o signed-read | Usar exactamente el `object_name` devuelto por `signed-upload` |
| `403 Cannot upload media for another user` | `entity_id` no coincide con el usuario autenticado | Asegúrate de pasar el UUID del usuario actual |
| `403 Cannot upload media for a pet you do not own` | La mascota no pertenece al usuario autenticado | Verificar que `pet.owner_id == current_user.id` |
| `404 Pet not found` | UUID de mascota inválido o inexistente | Verificar que la mascota existe antes de subir |
| `403` de GCS al hacer PUT | `Content-Type` del PUT no coincide con el del paso 1 | Usar exactamente el mismo `content_type` |
| `signed_url` expirada al hacer PUT | Tardaste más de `expires_in` segundos | Pedir nueva signed URL y repetir desde el paso 1 |

---

## 📋 Resumen de endpoints

| Endpoint | Método | Requiere auth | Para qué |
|---|---|---|---|
| `/media/signed-upload` | `POST` | ✅ | Obtener URL firmada para subir imagen a GCS |
| `/media/confirm-profile-photo` | `POST` | ✅ | Confirmar subida y persistir en BD |
| `/media/signed-read` | `POST` | ✅ | Obtener URL firmada para mostrar imagen |

---

## 📌 Reglas de diseño UX recomendadas

1. **Mostrar placeholder** mientras se carga la signed read URL (puede tomar ~200ms).
2. **No cachear** `read_url` más allá de `expires_in - 30` segundos (margen de seguridad).
3. **Comprimir** la imagen en el cliente antes de subir (máx. recomendado: 1MB, formato `webp` preferido).
4. **Feedback visual** durante los 3 pasos: "Subiendo foto..." → spinner hasta que `confirm` responda.
5. Si el usuario o mascota tiene `profile_photo_url`/`photo_url` en `null`, mostrar avatar por defecto.
