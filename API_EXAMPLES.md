# 🚀 API Examples: Geo + Address Flow

This document shows **real examples** of how to use the Geo and Address APIs in the Paku platform.

---

## 📍 1. Get Available Districts

**Endpoint:** `GET /geo/districts?active=true`

**Purpose:** Get the list of districts where Paku provides services (for UI dropdown).

**Request:**
```bash
curl -X GET "http://localhost:8000/geo/districts?active=true"
```

**Response:**
```json
[
  {
    "id": "150104",
    "name": "Barranco",
    "province_name": "Lima",
    "department_name": "Lima",
    "active": true
  },
  {
    "id": "150113",
    "name": "Jesús María",
    "province_name": "Lima",
    "department_name": "Lima",
    "active": true
  },
  {
    "id": "150116",
    "name": "Lince",
    "province_name": "Lima",
    "department_name": "Lima",
    "active": true
  }
]
```

**Frontend Example (React/React Native):**
```typescript
// Get districts for dropdown
const { data: districts } = await api.get('/geo/districts?active=true');

// Render in UI
<Select placeholder="Selecciona tu distrito">
  {districts.map(d => (
    <Option key={d.id} value={d.id}>
      {d.name}
    </Option>
  ))}
</Select>
```

---

## 📍 2. Get Specific District

**Endpoint:** `GET /geo/districts/{district_id}`

**Purpose:** Get details of a specific district.

**Request:**
```bash
curl -X GET "http://localhost:8000/geo/districts/150104"
```

**Response:**
```json
{
  "id": "150104",
  "name": "Barranco",
  "province_name": "Lima",
  "department_name": "Lima",
  "active": true
}
```

**Error Response (district not found):**
```json
{
  "detail": "District not found"
}
```
Status: `404 Not Found`

---

## 🏠 3. Create User Address

**Endpoint:** `POST /addresses`

**Purpose:** Add a new address to the user's address book.

**Authentication:** Required (Bearer token)

**Request:**
```bash
curl -X POST "http://localhost:8000/addresses" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "district_id": "150104",
    "address_line": "Av. Pedro de Osma 123",
    "lat": -12.1465,
    "lng": -77.0204,
    "reference": "Casa verde, segundo piso",
    "building_number": "123",
    "apartment_number": "201",
    "label": "Casa",
    "type": "home",
    "is_default": true
  }'
```

**Response:**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "district_id": "150104",
  "address_line": "Av. Pedro de Osma 123",
  "lat": -12.1465,
  "lng": -77.0204,
  "reference": "Casa verde, segundo piso",
  "building_number": "123",
  "apartment_number": "201",
  "label": "Casa",
  "type": "home",
  "is_default": true,
  "created_at": "2026-02-09T10:30:00Z"
}
```

**Error Response (invalid district):**
```json
{
  "detail": "District not found or not active"
}
```
Status: `422 Unprocessable Entity`

**Frontend Example:**
```typescript
// User fills form, selects location on map, then submits
const createAddress = async (formData) => {
  try {
    const response = await api.post('/addresses', {
      district_id: formData.selectedDistrict,
      address_line: formData.address,
      lat: formData.coordinates.lat,
      lng: formData.coordinates.lng,
      reference: formData.reference,
      is_default: formData.isDefault,
    });
    
    toast.success('Dirección creada exitosamente');
    return response.data;
  } catch (error) {
    if (error.response?.status === 422) {
      toast.error('El distrito seleccionado no está disponible');
    }
  }
};
```

---

## 🏠 4. List User Addresses

**Endpoint:** `GET /addresses`

**Purpose:** Get all addresses in the user's address book.

**Authentication:** Required

**Request:**
```bash
curl -X GET "http://localhost:8000/addresses" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response:**
```json
[
  {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "district_id": "150104",
    "address_line": "Av. Pedro de Osma 123",
    "lat": -12.1465,
    "lng": -77.0204,
    "reference": "Casa verde, segundo piso",
    "building_number": "123",
    "apartment_number": "201",
    "label": "Casa",
    "type": "home",
    "is_default": true,
    "created_at": "2026-02-09T10:30:00Z"
  },
  {
    "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "district_id": "150113",
    "address_line": "Av. Salaverry 2850",
    "lat": -12.0850,
    "lng": -77.0450,
    "reference": "Edificio azul",
    "building_number": "2850",
    "apartment_number": "305",
    "label": "Trabajo",
    "type": "work",
    "is_default": false,
    "created_at": "2026-02-08T15:20:00Z"
  }
]
```

---

## 🏠 5. Update Address

**Endpoint:** `PUT /addresses/{address_id}`

**Purpose:** Update an existing address.

**Authentication:** Required

**Request:**
```bash
curl -X PUT "http://localhost:8000/addresses/a1b2c3d4-e5f6-7890-abcd-ef1234567890" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reference": "Casa verde, segundo piso, timbre 201",
    "apartment_number": "201-A"
  }'
```

**Response:**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "district_id": "150104",
  "address_line": "Av. Pedro de Osma 123",
  "lat": -12.1465,
  "lng": -77.0204,
  "reference": "Casa verde, segundo piso, timbre 201",
  "building_number": "123",
  "apartment_number": "201-A",
  "label": "Casa",
  "type": "home",
  "is_default": true,
  "created_at": "2026-02-09T10:30:00Z"
}
```

---

## 🏠 6. Set Default Address

**Endpoint:** `PUT /addresses/{address_id}/default`

**Purpose:** Mark an address as the default (suggested for future orders).

**Authentication:** Required

**Request:**
```bash
curl -X PUT "http://localhost:8000/addresses/b2c3d4e5-f6a7-8901-bcde-f12345678901/default" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response:**
Status: `204 No Content`

**Note:** This automatically unsets other addresses as default.

---

## 🏠 7. Delete Address

**Endpoint:** `DELETE /addresses/{address_id}`

**Purpose:** Soft-delete an address (user can't use it, but historical data remains).

**Authentication:** Required

**Request:**
```bash
curl -X DELETE "http://localhost:8000/addresses/a1b2c3d4-e5f6-7890-abcd-ef1234567890" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response:**
Status: `204 No Content`

**Error Response (cannot delete last address):**
```json
{
  "detail": "Cannot delete last address"
}
```
Status: `409 Conflict`

---

## 📦 8. Create Order with Address

**Endpoint:** `POST /orders`

**Purpose:** Create an order for delivery to a specific address.

**Authentication:** Required

**Request:**
```bash
curl -X POST "http://localhost:8000/orders" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "cart_id": "cart-uuid-here",
    "address_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
  }'
```

**Backend Validation:**
1. ✅ Address exists and belongs to user
2. ✅ Address is not deleted
3. ✅ District is active (service coverage)
4. ✅ Creates order with address snapshot

**Response:**
```json
{
  "id": "order-uuid",
  "user_id": "user-uuid",
  "status": "pending",
  "delivery_address_snapshot": {
    "district_id": "150104",
    "address_line": "Av. Pedro de Osma 123",
    "reference": "Casa verde, segundo piso",
    "lat": -12.1465,
    "lng": -77.0204
  },
  "created_at": "2026-02-09T11:00:00Z"
}
```

**Note:** The address is **snapshotted** at order creation time. If the user later edits the address in their address book, the order keeps the original data.

---

## 🎯 Complete Flow Example

Here's the complete user journey:

```typescript
// 1. User opens "Create Address" screen
const districts = await api.get('/geo/districts?active=true');
// Shows: Barranco, Jesús María, Lince

// 2. User selects "Barranco" from dropdown

// 3. User picks location on map (gets lat/lng)
const location = { lat: -12.1465, lng: -77.0204 };

// 4. User fills form and submits
const address = await api.post('/addresses', {
  district_id: '150104',
  address_line: 'Av. Pedro de Osma 123',
  lat: location.lat,
  lng: location.lng,
  reference: 'Casa verde, segundo piso',
  is_default: true,
});
// ✅ Address created

// 5. Later, user creates an order
const order = await api.post('/orders', {
  cart_id: cartId,
  address_id: address.id,
});
// ✅ Order created with delivery to Barranco
```

---

## ⚠️ Common Errors

### Error: "District not found or not active" (422)
**Cause:** District ID doesn't exist in the hardcoded list, or is inactive.

**Solution:**
- Check available districts: `GET /geo/districts?active=true`
- Use one of the IDs returned (150104, 150113, or 150116)

### Error: "Address not found" (404)
**Cause:** Address doesn't exist or doesn't belong to the user.

**Solution:**
- List user addresses: `GET /addresses`
- Use a valid address ID from the list

### Error: "Cannot delete last address" (409)
**Cause:** User is trying to delete their only remaining address.

**Solution:**
- Create another address first
- Then delete the unwanted one

---

## 📝 Notes

1. **District Validation:** All address operations validate that the district exists and is active.

2. **No Default Required:** Unlike previous versions, the "default" address is just a UI helper. Orders MUST explicitly specify `address_id`.

3. **Coordinates Required:** `lat` and `lng` are mandatory (used for delivery routing and ally assignment).

4. **Soft Delete:** Deleted addresses are marked as `deleted_at != null` but remain in the database for historical reference.

5. **Address Snapshots:** Orders store a copy of the address at creation time, so edits to the address book don't affect existing orders.

---

## 🚀 Testing in Swagger

Visit: `http://localhost:8000/docs`

1. **Authorize** with your access token
2. Try `GET /geo/districts` (no auth needed)
3. Try `POST /addresses` with a valid district ID
4. Try `POST /orders` with your new address ID

Enjoy! 🎉
