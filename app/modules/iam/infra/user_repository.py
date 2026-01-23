from typing import Dict, Optional
from uuid import UUID

from app.modules.iam.domain.user import User, UserRepository


# [TECH]
# In-memory implementation of UserRepository.
# Stores users in dictionaries keyed by id and email.
# Used for local development/testing and for this project skeleton (no DB).
# Flow: persistence layer for IAM use cases (register/login/get/update).
#
# [BUSINESS]
# Almacén de usuarios en memoria.
# Sirve para que el sistema funcione sin base de datos (por ejemplo en demos o prototipos).
# Mantiene una lista de usuarios registrados y permite consultarlos/actualizarlos.
class InMemoryUserRepository(UserRepository):
    def __init__(self) -> None:
        # [TECH]
        # Initializes the internal indices:
        # - _by_id stores full User objects by UUID.
        # - _by_email maps normalized email to UUID for quick lookup.
        #
        # [BUSINESS]
        # Prepara las estructuras internas para guardar usuarios y buscarlos por correo.
        self._by_id: Dict[UUID, User] = {}
        self._by_email: Dict[str, UUID] = {}

    async def get_by_email(self, email: str) -> Optional[User]:
        # [TECH]
        # Retrieves a user by normalized email.
        # Returns None if not found.
        # Flow: used by login and registration uniqueness checks.
        #
        # [BUSINESS]
        # Busca un usuario por correo.
        # Se usa para validar credenciales o evitar correos duplicados.
        user_id = self._by_email.get(email.strip().lower())
        if not user_id:
            return None
        return self._by_id.get(user_id)

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        # [TECH]
        # Retrieves a user by UUID.
        # Returns None if not found.
        # Flow: used by /users/me and profile updates.
        #
        # [BUSINESS]
        # Busca un usuario por su identificador.
        # Se usa para obtener el perfil del usuario.
        return self._by_id.get(user_id)

    async def add(self, user: User) -> None:
        # [TECH]
        # Persists a new user.
        # Raises ValueError("email_exists") if email already indexed.
        # Flow: called during registration.
        #
        # [BUSINESS]
        # Guarda un usuario nuevo.
        # Evita que dos cuentas usen el mismo correo.
        email = user.email.strip().lower()
        if email in self._by_email:
            raise ValueError("email_exists")
        self._by_id[user.id] = user
        self._by_email[email] = user.id

    async def update(self, user: User) -> None:
        # [TECH]
        # Updates an existing user record.
        # Raises ValueError("user_not_found") if the user id does not exist.
        # Flow: called by profile update use case.
        #
        # [BUSINESS]
        # Actualiza la información de un usuario existente.
        # Si el usuario no existe, se informa el error.
        if user.id not in self._by_id:
            raise ValueError("user_not_found")
        self._by_id[user.id] = user
