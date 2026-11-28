# PAKU + HCVET — Integración del ecosistema de historias clínicas veterinarias

## 1. Contexto y objetivo general

Actualmente contamos con dos productos independientes:

### Paku

Plataforma de servicios para mascotas que administra:

- Usuarios y clientes.
- Mascotas.
- Servicios de baño y grooming.
- Reservas.
- Groomers.
- Preferencias y características operativas de las mascotas.
- Direcciones de atención.
- Pagos y facturación.
- Información comercial y analítica.
- Registros y eventos relacionados con las mascotas.

### HCVet

Motor de historias clínicas veterinarias que debe funcionar como un servicio independiente, integrable con diferentes plataformas y establecimientos.

En el futuro podrá ser utilizado por:

- Paku.
- Clínicas veterinarias.
- Consultorios veterinarios.
- Empresas de grooming.
- Crematorios de mascotas, como Dulce Recuerdo.
- Hospitales veterinarios.
- Otras plataformas de servicios para mascotas.

HCVet no debe convertirse en un sistema centralizado de autenticación o administración comercial de clientes.

Su propósito principal es mantener una identidad única de cada mascota y consolidar su historial clínico y eventos relevantes, independientemente del establecimiento o plataforma en donde se originaron.

Paku será uno de los primeros consumidores de HCVet, pero HCVet no deberá tener dependencias funcionales ni técnicas específicas de Paku.

---

## 2. Revisión de los sistemas existentes

Revisa el código fuente, modelos, endpoints, migraciones, documentación, pruebas y reglas de negocio de:

### Paku

- `paku-backend`.
- Módulos de autenticación, registro y usuarios.
- Registro convencional mediante correo y contraseña.
- Autenticación mediante Google, Facebook y otros proveedores existentes.
- Flujo de completado de perfil.
- Módulo Pet.
- Módulo Pet-records.
- Gestión de direcciones.
- Gestión de peso de mascotas.
- Reglas de negocio relacionadas con reservas y cobros.
- Scheduler y mecanismos de ejecución de tareas asíncronas.
- Aplicaciones móviles, web y administración que consuman estos módulos.

### HCVet

- `hcvet-backend`.
- Modelo de propietarios.
- Modelo de mascotas.
- Modelo de eventos clínicos.
- Registro y actualización de propietarios.
- Registro, actualización y consulta de mascotas.
- Registro y consulta de eventos.
- Autenticación de establecimientos y plataformas.
- API Keys.
- Consentimientos y permisos.
- Auditoría.
- Idempotencia.
- Anulación y corrección de eventos.
- Documentación de dominio y fases pendientes.

### Datos Perú

Revisa `datosperu-backend` y sus contratos de integración para la consulta de información mediante DNI.

Si alguno de los repositorios no está disponible, indícalo expresamente. No inventes contratos, funcionalidades ni estructuras de datos que no hayas podido verificar.

Contrasta las funcionalidades existentes con los requerimientos de este documento.

Identifica qué componentes pueden reutilizarse, cuáles requieren modificaciones y cuáles necesitan nuevas implementaciones.

---

## 3. Principios de arquitectura

### 3.1. Paku controla sus propios usuarios

Paku debe mantener el control de toda la información de sus usuarios y clientes.

Esto incluye:

- Identificadores internos.
- Credenciales y métodos de autenticación.
- DNI.
- Nombres y apellidos.
- Correo electrónico.
- Teléfono.
- Sexo y fecha de nacimiento, cuando corresponda.
- Direcciones.
- Preferencias.
- Datos comerciales.
- Datos de comportamiento.
- Información necesaria para reportes y analítica.
- Historial de servicios y reservas.

Paku no deberá consultar HCVet constantemente para obtener estos datos.

HCVet tampoco deberá convertirse en una dependencia para autenticar usuarios, gestionar direcciones, consultar clientes o realizar operaciones comerciales dentro de Paku.

### 3.2. HCVet mantiene un registro básico de propietarios

HCVet necesita almacenar información básica de los propietarios para identificar y relacionar correctamente a las mascotas.

Podrá almacenar, según las necesidades reales de su dominio:

- Identificador interno del propietario.
- DNI.
- Nombres.
- Apellidos.
- Correo electrónico.
- Teléfono.
- Distrito, si corresponde.
- Consentimientos y autorizaciones.
- Referencias a plataformas vinculadas.
- Información de auditoría.

Esta información podrá ser proporcionada y actualizada por plataformas autorizadas.

No es necesario enviar a HCVet todas las direcciones, preferencias, información comercial ni datos adicionales que almacena Paku.

### 3.3. Propietario no equivale a cuenta de usuario

Esta es una decisión arquitectónica importante.

HCVet no será una plataforma de acceso directo para los propietarios de mascotas.

Los propietarios interactuarán con HCVet a través de las plataformas integradas.

Por lo tanto:

- Un propietario registrado en HCVet no necesita una cuenta convencional con contraseña.
- No se deben generar contraseñas aleatorias por cada usuario de Paku.
- Paku no debe almacenar credenciales individuales de HCVet.
- No debe existir un segundo proceso de inicio de sesión para utilizar HCVet desde Paku.
- Las plataformas autorizadas deberán actuar en representación del propietario dentro de los permisos concedidos.

El propietario debe existir como entidad del dominio, independientemente de los mecanismos de autenticación.

Si actualmente HCVet requiere una cuenta con correo y contraseña para activar un propietario, analiza cómo desacoplar ambos conceptos sin romper las funcionalidades existentes ni eliminar mecanismos de autenticación de forma prematura.

### 3.4. Responsabilidad sobre la información

Utiliza la siguiente distribución como criterio funcional:

| Información | Sistema responsable |
|---|---|
| Autenticación de usuarios Paku | Paku |
| Datos personales del cliente Paku | Paku |
| Direcciones y datos comerciales | Paku |
| Preferencias del cliente | Paku |
| Identificación compartida del propietario | DNI y referencia HCVet |
| Registro básico del propietario en el ecosistema | HCVet |
| Identidad única de la mascota | HCVet |
| Datos generales de la mascota vinculada | HCVet |
| Preferencias de grooming | Paku |
| Historia clínica | HCVet |
| Vacunas y tratamientos | HCVet |
| Historial de pesos | HCVet |
| Peso utilizado para cotización y facturación | Paku |
| Reservas y servicios | Paku |
| Pagos y facturación | Paku |
| Analítica comercial | Paku |
| Eventos clínicos y de grooming compartidos | HCVet |

Se permiten copias locales, referencias, cachés y proyecciones de lectura cuando exista una necesidad operativa justificada.

Lo que debemos evitar es mantener dos fuentes independientes y contradictorias de información clínica.

Define la fuente de verdad a nivel de entidad y, cuando sea necesario, a nivel de campo.

---

## 4. Nuevo flujo de registro de usuarios en Paku

### 4.1. Métodos de registro

El flujo debe funcionar independientemente del método utilizado para crear la cuenta:

- Google.
- Facebook.
- Correo electrónico y contraseña.
- Apple u otros proveedores, si se encuentran implementados.

Todos deberán converger en un proceso de completado de perfil.

### 4.2. DNI obligatorio para completar el perfil

Actualmente el DNI puede ser opcional en algunos flujos de Paku.

El nuevo requerimiento es que el usuario proporcione su DNI para completar su perfil.

Revisa cómo afecta esta decisión a:

- Registro de nuevos usuarios.
- Usuarios existentes.
- Inicio de sesión social.
- Completado de perfil.
- Reservas.
- Edición de datos personales.
- Validaciones existentes en backend y frontend.

No confundas completar el perfil con iniciar sesión. Los usuarios existentes deben poder autenticarse y acceder al proceso de regularización de sus datos.

### 4.3. Consulta de DNI

Agregar junto al campo DNI un botón denominado «Consultar DNI» o equivalente, respetando el diseño actual de Paku.

El flujo esperado es:

1. El usuario ingresa su DNI.
2. Presiona el botón de consulta.
3. El frontend realiza una solicitud a Paku Backend.
4. Paku Backend consume `datosperu-backend`.
5. Datos Perú realiza la consulta utilizando el proveedor configurado.
6. Se obtienen los nombres y apellidos asociados al documento.
7. Paku autocompleta los campos correspondientes.
8. El usuario completa los demás datos requeridos.
9. Se finaliza el registro o completado de perfil.

No integrar directamente proveedores RENIEC o similares desde los frontends de Paku.

Utilizar el servicio centralizado de Datos Perú y respetar su configuración de proveedor activo, evitando consultar simultáneamente varios proveedores o generar consumos innecesarios.

Considerar:

- Validación de formato del DNI.
- DNI inexistente.
- Servicio temporalmente no disponible.
- Timeout.
- Errores del proveedor.
- Consultas repetidas.
- Control de consumo.
- Caché existente, si corresponde.
- Rate limiting.
- Estados de carga y mensajes de error.
- Protección de datos personales.
- Prevención de consultas masivas o abusivas.

La consulta debe estar limitada al flujo legítimo de identificación del usuario. No debe convertirse en un buscador público de personas.

### 4.4. Google y Facebook

Los nombres obtenidos desde Google o Facebook no necesariamente coinciden con los nombres legales del propietario.

Cuando el usuario consulte su DNI:

- Los nombres y apellidos obtenidos mediante Datos Perú tendrán prioridad sobre los del proveedor social para el perfil de identidad.
- La identidad de autenticación continuará vinculada a Google, Facebook o el proveedor correspondiente.
- No se deberá modificar incorrectamente el identificador de autenticación social.
- No se deberá sustituir automáticamente el correo electrónico autenticado.

Analiza si es conveniente distinguir entre nombre legal y nombre de visualización.

Considera también que el DNI puede estar asociado a una cuenta Paku existente. No permitas crear cuentas duplicadas o fusionarlas automáticamente sin verificar la titularidad.

### 4.5. Verificación de identidad

Obtener nombres y apellidos mediante una consulta de DNI no demuestra por sí mismo que la persona sea titular de ese documento.

Identifica un mecanismo proporcional de verificación para vincular propietarios y mascotas previamente existentes en HCVet.

Evalúa la reutilización de mecanismos de verificación existentes en Paku, validación mediante contactos previamente verificados u otras alternativas seguras.

La experiencia debe ser sencilla, pero no debe permitir que una persona registre un DNI ajeno y acceda a las mascotas de otro propietario.

No implementar un mecanismo definitivo sin documentar previamente sus implicaciones.

---

## 5. Autenticación y autorización entre Paku y HCVet

### 5.1. Comunicación entre servicios

La comunicación con HCVet debe realizarse desde Paku Backend.

Flujo general:

`Paku Frontend → Paku Backend → HCVet Backend`

Los frontends de Paku no deben conocer ni almacenar las credenciales privadas de HCVet.

Reutiliza el mecanismo de API Keys existente en HCVet cuando sea viable.

Si requiere una extensión para permitir integraciones de plataformas que actúan en representación de propietarios, plantea su implementación mediante una especificación.

No crear una cuenta HCVet con contraseña por cada usuario Paku.

### 5.2. Autorización delegada

Paku deberá poder actuar en representación de sus usuarios ante HCVet.

Distinguir tres niveles:

- Autenticación de la plataforma consumidora.
- Identificación del propietario.
- Autorización para ejecutar determinadas operaciones sobre ese propietario y sus mascotas.

La API Key identifica a Paku como plataforma autorizada.

El DNI permite localizar al propietario.

La autorización delegada determina qué información y operaciones están permitidas.

La posesión de una API Key no debe otorgar acceso ilimitado a todos los propietarios o mascotas de HCVet.

HCVet debe comprobar los permisos sobre cada recurso solicitado.

### 5.3. Permisos

Analiza la necesidad de permisos diferenciados para:

- Registrar propietarios.
- Consultar datos básicos de propietarios.
- Actualizar datos básicos.
- Registrar mascotas.
- Consultar mascotas.
- Modificar datos generales de mascotas.
- Consultar historias clínicas.
- Registrar eventos.
- Corregir o anular eventos.
- Registrar eventos de grooming.
- Consultar información clínica relevante para un servicio.

No todas las plataformas necesitan los mismos permisos.

Por ejemplo, un crematorio podría necesitar permisos distintos de una clínica veterinaria o una empresa de grooming.

Evita implementar un sistema innecesariamente complejo de autorización si los mecanismos actuales pueden extenderse de manera segura.

### 5.4. Seguridad

Considerar:

- Almacenamiento seguro de API Keys.
- Rotación y revocación de credenciales.
- Identificación de la plataforma o establecimiento.
- Permisos por propietario y recurso.
- Auditoría de consultas y modificaciones.
- Prevención de acceso horizontal no autorizado.
- Rate limiting.
- Protección de información personal en logs.
- Comunicación segura entre backends.

Nunca incorporar credenciales reales a documentos, código fuente, repositorios o pruebas.

---

## 6. Consentimiento del propietario

La integración con HCVet debe resultar sencilla para el usuario.

Durante el registro, completado de perfil o vinculación, según el flujo que resulte más apropiado, Paku deberá informar al usuario sobre la integración y solicitar las autorizaciones necesarias.

Revisa los mecanismos existentes en HCVet:

- `permite_indexacion_veterinaria`.
- `permite_uso_comercial`.
- Activación del propietario.
- Permisos de acceso de establecimientos.

Determina qué consentimientos pueden reutilizarse y cuáles necesitan ajustes.

Diferenciar:

- Autorización para compartir información veterinaria.
- Autorización para consultar la historia clínica.
- Autorización para registrar eventos.
- Autorización para uso comercial de datos.

No asumir que todos estos permisos son equivalentes.

No marcar los consentimientos por defecto.

Registrar fecha, plataforma de origen, finalidad, versión de los términos y estado de la autorización, según corresponda.

Considerar la revocación y sus efectos sobre accesos posteriores, sin asumir que revocar un permiso implica eliminar automáticamente todo el historial existente.

Como criterio recomendado, el usuario no debería perder la posibilidad de utilizar los servicios comerciales de Paku por rechazar el uso comercial de sus datos o una integración clínica opcional.

Identifica qué operaciones requieren necesariamente HCVet y cuáles podrían funcionar de forma independiente.

Los textos legales definitivos deberán ser revisados y aprobados antes de utilizarse en producción.

---

## 7. Registro y vinculación de propietarios

Una vez completado el perfil de Paku y obtenidas las autorizaciones necesarias:

1. Paku conserva todos los datos del usuario en su propia base de datos.
2. Paku consulta HCVet utilizando el DNI del propietario mediante una operación autorizada.
3. HCVet determina si el propietario ya existe.
4. Si no existe, se registra con los datos básicos necesarios.
5. Si existe, se verifica la identidad y se vincula con la cuenta de Paku.
6. HCVet devuelve el identificador único del propietario.
7. Paku almacena la referencia correspondiente.

Este proceso debe realizarse sin generar contraseñas individuales de HCVet.

Debe ser idempotente y evitar duplicados, incluso cuando existan solicitudes concurrentes desde diferentes plataformas.

### 7.1. Propietarios previamente registrados

Puede ocurrir que un usuario se registre inicialmente en Paku y posteriormente en otra plataforma que también utiliza HCVet.

También puede ocurrir el caso inverso.

La nueva plataforma debería poder recuperar los datos básicos permitidos del propietario, previa verificación y autorización, para facilitar su registro.

No se deben crear múltiples propietarios HCVet para un mismo DNI.

El objetivo es evitar que el usuario tenga que registrar repetidamente toda su información y sus mascotas.

### 7.2. Actualización de datos

Paku administra sus datos personales de manera independiente.

Si el usuario modifica su teléfono, correo u otro dato relevante, Paku podrá notificar a HCVet cuando corresponda.

HCVet no deberá actualizar automáticamente todos los datos de Paku por el simple hecho de que otra plataforma haya modificado información del propietario.

Diseña una política de actualización que considere:

- Datos legales de identidad.
- Datos de contacto.
- Datos verificados y no verificados.
- Plataforma de origen.
- Fecha de actualización.
- Conflictos entre plataformas.
- Auditoría.

Evitar que una plataforma sobrescriba información reciente y verificada con datos antiguos.

No implementar una sincronización bidireccional indiscriminada de todos los campos.

---

## 8. Integración del módulo Pet

### 8.1. Identidad única de la mascota

Cada mascota debe tener un identificador único generado por HCVet.

El DNI del propietario será un criterio de búsqueda que permitirá localizar a sus mascotas.

No utilizar el DNI como identificador de la mascota, ya que un propietario puede tener varias mascotas.

Tampoco considerar el nombre de la mascota como identificador único.

El identificador de HCVet debe mantenerse durante toda la vida de la mascota, incluso cuando cambie de propietario o establecimiento de atención.

### 8.2. Registro de nueva mascota desde Paku

Flujo esperado:

1. El usuario accede al módulo de mascotas.
2. Completa los datos generales requeridos.
3. Paku verifica la vinculación y autorización del propietario.
4. Paku solicita a HCVet registrar la mascota.
5. HCVet genera y devuelve el identificador único.
6. Paku almacena la referencia HCVet.
7. Paku conserva los datos operativos específicos de grooming.

Mantener los identificadores internos existentes de Paku cuando sean necesarios para reservas, pagos, relaciones históricas y compatibilidad con los frontends.

No reemplazar indiscriminadamente los IDs internos de Paku por los IDs de HCVet.

### 8.3. Mascotas previamente registradas en HCVet

Cuando el usuario se vincule con HCVet, Paku debe poder consultar las mascotas asociadas al propietario autorizado.

El usuario deberá poder incorporar una mascota existente a Paku sin crearla nuevamente en HCVet.

Evaluar una experiencia de usuario que permita:

- Visualizar las mascotas disponibles.
- Identificar las que ya están vinculadas a Paku.
- Incorporar mascotas existentes.
- Registrar una nueva mascota.
- Completar únicamente los datos específicos requeridos por Paku.

Si existen posibles duplicados, no fusionarlos automáticamente mediante coincidencias débiles como nombre, raza o especie.

Definir un mecanismo de revisión y resolución de duplicados.

### 8.4. Datos generales de la mascota

Revisa y compara los campos existentes en Pet de Paku y el modelo de mascotas de HCVet.

Considerar:

- Nombre.
- Especie.
- Raza.
- Sexo.
- Fecha de nacimiento.
- Edad aproximada.
- Color.
- Esterilización.
- Microchip, si corresponde.
- Estado de la mascota.
- Propietario principal.
- Historial de propietarios, si existe.

Genera una matriz de mapeo que indique:

- Campo en Paku.
- Campo en HCVet.
- Tipo de dato.
- Obligatoriedad.
- Sistema responsable.
- Transformación necesaria.
- Tratamiento de valores nulos.
- Compatibilidad con datos existentes.

No obligar a los usuarios a inventar información que desconocen, como una fecha exacta de nacimiento.

Evalúa si determinadas reglas de obligatoriedad en HCVet deben flexibilizarse.

### 8.5. Datos específicos de grooming

Paku deberá conservar los datos necesarios para sus propios servicios.

Por ejemplo:

- Preferencias de champú.
- Perfume.
- Corte.
- Secado.
- Uñas.
- Características del pelaje.
- Instrucciones especiales.
- Comportamiento durante el grooming.
- Requerimientos operativos.
- Información necesaria para determinar tarifas.

Clasificar los campos relacionados con alergias, enfermedades, reactividad, mordidas, vacunas y condiciones especiales.

Determinar cuáles corresponden al historial clínico, cuáles son operativos y cuáles necesitan una proyección local para la seguridad del servicio.

### 8.6. Actualización y desvinculación

Cuando el usuario modifique datos generales de una mascota vinculada, Paku deberá actualizar HCVet mediante una operación autorizada.

Las modificaciones realizadas en otras plataformas deberán poder visualizarse posteriormente desde Paku.

Diferenciar entre:

- Actualizar una mascota.
- Desvincular una mascota de Paku.
- Transferir su propietario.
- Registrar el fallecimiento.
- Eliminar o anular información incorrecta.

Eliminar o desvincular una mascota de Paku no debe eliminar automáticamente su identidad ni su historia clínica en HCVet.

---

## 9. Integración del módulo Pet-records

### 9.1. Objetivo

HCVet debe convertirse en el sistema responsable del historial clínico compartido.

Paku deberá actuar como consumidor y registrador autorizado de eventos.

El usuario seguirá interactuando con el módulo Pet-records de Paku, pero internamente los eventos compartidos se consultarán y registrarán mediante HCVet.

Conservar, cuando sea viable, los contratos actuales de Paku con sus frontends, evitando cambios innecesarios.

### 9.2. Registro de eventos

Flujo esperado:

1. El usuario, groomer o personal autorizado registra un evento desde Paku.
2. Paku valida los datos y permisos.
3. Paku transforma el evento al formato requerido por HCVet.
4. HCVet registra el evento.
5. HCVet devuelve su identificador.
6. Paku conserva la referencia y la información operativa necesaria.
7. El evento queda disponible para futuras consultas autorizadas.

### 9.3. Mapeo de eventos

Revisar los tipos existentes en ambos sistemas.

Utilizar como punto de partida el siguiente mapeo, sujeto a validación contra el código:

| Paku | HCVet |
|---|---|
| `check_up` | `consulta` |
| `vaccine` | `vacuna` |
| `deworming` | `desparasitacion` |
| `medication` | `tratamiento` |
| `bath` | `bano_grooming` |
| `grooming` | `bano_grooming` |
| `disease_condition` | `enfermedad` |
| `surgery` | `cirugia` |
| `study_test` | `diagnostico` |
| `nutrition` | Evaluar tipo específico |
| `note` | Evaluar tipo específico |
| `weight_record` | Módulo o endpoint de pesos |

No perder información al transformar eventos.

Si HCVet requiere nuevos tipos o campos, documentar el cambio de dominio y generar la especificación correspondiente.

No utilizar indiscriminadamente un tipo genérico `otro` para resolver incompatibilidades sin analizar sus consecuencias sobre consultas, reportes e integraciones futuras.

### 9.4. Procedencia y autoría

Cada evento deberá identificar, según corresponda:

- Mascota.
- Plataforma de origen.
- Establecimiento.
- Autor.
- Tipo de registrante.
- Fecha del evento.
- Fecha de registro.
- Profesional responsable.
- Datos clínicos.
- Identificador externo de origen.
- Estado del evento.

Diferenciar eventos registrados por:

- Propietario.
- Groomer.
- Médico veterinario.
- Personal administrativo.
- Plataforma automatizada.

Una vacuna declarada por el propietario no debe presentarse como si hubiese sido certificada por un médico veterinario.

Registrar a un propietario mediante la autorización delegada de Paku tampoco debe provocar que todos sus eventos aparezcan incorrectamente como registrados por el establecimiento Paku.

### 9.5. Consulta de historial consolidado

Paku deberá poder consultar los eventos registrados en HCVet, incluyendo los originados en otras plataformas o establecimientos, siempre que exista autorización.

Ejemplo:

- El propietario registra una vacuna desde Paku.
- Una veterinaria registra una consulta médica desde su propio sistema.
- Otro establecimiento registra una desparasitación.
- Paku registra un baño y un nuevo peso.

Todos los eventos deberán poder formar parte del historial consolidado de la misma mascota.

Evaluar:

- Paginación.
- Orden cronológico.
- Filtros por tipo.
- Filtros por fechas.
- Procedencia.
- Rendimiento.
- Caché.
- Actualización de información.
- Estados de carga y errores.

Si se utiliza una copia local del historial, deberá tratarse como una proyección de lectura y no como una segunda historia clínica independiente.

### 9.6. Corrección y anulación

Revisar los mecanismos existentes de anulación, corrección y borrado lógico.

Paku no deberá eliminar físicamente eventos de HCVet de manera indiscriminada.

Definir:

- Quién puede corregir un evento.
- Quién puede anularlo.
- Motivo de la corrección o anulación.
- Conservación del historial de cambios.
- Tratamiento de eventos originados en otros establecimientos.
- Actualización del estado en Paku.

Si HCVet todavía no cuenta con estas funcionalidades, identificar sus dependencias y determinar qué fases de integración pueden avanzar sin ellas.

No habilitar operaciones que puedan generar inconsistencias o pérdida de información.

---

## 10. Tratamiento especial del peso de la mascota

El peso tiene implicaciones clínicas y comerciales.

HCVet deberá conservar el historial de pesos de la mascota.

Paku necesita disponer del peso operativo para:

- Determinar tarifas.
- Cotizar servicios.
- Validar reservas.
- Aplicar diferencias de precio.
- Registrar información del servicio.

Paku podrá mantener una copia local del peso operativo y registrar los nuevos pesos en HCVet.

Sin embargo:

- Una actualización externa de peso no debe generar automáticamente un cobro.
- Una modificación clínica no debe alterar una reserva ya cotizada.
- Una sincronización o reintento no debe duplicar cobros.
- Se debe conservar el peso utilizado para calcular cada servicio.
- Se deben respetar las reglas comerciales existentes de Paku.

Revisa específicamente los efectos secundarios actuales del tipo `weight_record`.

Distinguir entre registrar un peso clínico, actualizar el peso operativo y ejecutar una regla comercial.

---

## 11. Disponibilidad, sincronización e idempotencia

Paku no debe quedar completamente inoperativo si HCVet presenta una interrupción temporal.

Analiza una arquitectura que permita registrar operaciones pendientes de sincronización cuando sea funcionalmente seguro.

Reutilizar el scheduler, mecanismos de persistencia y ejecución asíncrona existentes en Paku cuando resulten apropiados.

Evaluar la conveniencia de un patrón transactional outbox u otro mecanismo equivalente que garantice la persistencia de las operaciones pendientes.

Considerar los siguientes estados de referencia:

- `pending`.
- `syncing`.
- `synced`.
- `failed`.
- `conflict`.

Los nombres podrán adaptarse a las convenciones del proyecto.

Cada operación de sincronización deberá poder identificar:

- Entidad afectada.
- Tipo de operación.
- Identificador interno.
- Identificador externo, cuando exista.
- Clave de idempotencia.
- Número de intentos.
- Último error.
- Fecha de creación.
- Última sincronización.

Implementar posteriormente:

- Reintentos automáticos con límites.
- Prevención de solicitudes duplicadas.
- Recuperación ante fallos parciales.
- Reconciliación.
- Identificación de errores permanentes.
- Resolución de conflictos.
- Auditoría.

Las operaciones de escritura deben ser idempotentes.

Si HCVet registra una mascota o evento, pero Paku no recibe la respuesta por un timeout, repetir la solicitud no debe generar una nueva mascota o un evento duplicado.

Diferenciar los fallos temporales de los errores de validación, autenticación y autorización.

No reintentar indefinidamente operaciones que han sido rechazadas por falta de permisos.

Si existen operaciones clínicas pendientes, el frontend no deberá mostrarlas como sincronizadas o confirmadas por HCVet.

Define también el comportamiento cuando una nueva mascota todavía no cuenta con su identificador externo y existen eventos dependientes pendientes de sincronización.

Evitar dependencias circulares y escrituras dobles no controladas.

---

## 12. Migración de información existente

Actualmente Paku puede tener usuarios, mascotas, registros y relaciones operativas existentes.

La integración no debe provocar pérdida de información ni romper reservas, pagos, reportes o relaciones actuales.

### 12.1. Usuarios

Identificar:

- Usuarios con DNI.
- Usuarios sin DNI.
- DNI inválidos.
- DNI duplicados.
- Usuarios provenientes de autenticación social.
- Perfiles incompletos.
- Propietarios previamente registrados en HCVet.
- Usuarios sin autorización para compartir sus datos.

Diseñar un proceso progresivo de regularización y vinculación.

No eliminar cuentas existentes ni asumir consentimientos.

### 12.2. Mascotas

Diseñar la vinculación de mascotas existentes con HCVet.

Considerar coincidencias, duplicados, campos obligatorios faltantes y conflictos.

Conservar los identificadores internos y relaciones existentes en Paku.

### 12.3. Eventos

Diseñar la migración del historial existente de Paku hacia HCVet cuando exista autorización y sea posible preservar correctamente su significado.

Mantener:

- Fecha original.
- Autoría original.
- Tipo de evento.
- Información clínica.
- Procedencia.
- Identificador de origen.
- Estado del registro.

La migración debe ser idempotente, por lotes, auditable y ejecutable inicialmente en modo de simulación o dry-run.

No duplicar eventos ya migrados.

No ejecutar reglas comerciales de cobro durante la migración histórica de pesos.

### 12.4. Estrategia de despliegue

Evaluar:

- Migraciones compatibles con versiones existentes.
- Feature flags.
- Activación progresiva.
- Compatibilidad entre backend y frontend.
- Backups.
- Reversión.
- Despliegue por ambientes.
- Pruebas con datos controlados.

No ejecutar migraciones sobre producción ni enviar información real de usuarios a HCVet durante esta etapa de análisis.

---

## 13. Frontends involucrados

Revisar qué aplicaciones existentes requieren modificaciones.

Considerar, según corresponda:

- App Paku Cliente.
- App Paku Pro o Groomer.
- Paku Web.
- Paku Admin.
- Otras aplicaciones que consuman Users, Pet o Pet-records.

Los cambios funcionales previstos incluyen:

- DNI obligatorio para completar el perfil.
- Botón de consulta DNI.
- Autocompletado de nombres y apellidos.
- Consentimiento para la integración.
- Vinculación de propietario.
- Incorporación de mascotas existentes.
- Adaptación de formularios de mascotas.
- Visualización de historial consolidado.
- Identificación de la procedencia de eventos.
- Estados de sincronización.
- Manejo de errores.

Mantener el diseño y los componentes existentes.

No realizar rediseños generales ni cambios visuales que no sean necesarios para esta integración.

El backend debe ser responsable de las validaciones y permisos, independientemente de las restricciones implementadas en el frontend.

---

## 14. Compatibilidad y límites del alcance

La integración no debe convertirse en una reconstrucción completa de Paku ni de HCVet.

Priorizar:

- Reutilización de módulos existentes.
- Compatibilidad con las APIs actuales.
- Cambios incrementales.
- Separación de responsabilidades.
- Pruebas automatizadas.
- Mantenimiento de las reglas comerciales existentes.
- Reducción de dependencias innecesarias.

HCVet no debe incorporar reglas particulares de reservas, pagos, tarifas o grooming propias de Paku.

Paku no debe desarrollar nuevamente funcionalidades clínicas que correspondan al dominio de HCVet.

No compartir directamente las tablas o bases de datos de ambos sistemas para evitar consumir sus APIs.

La integración deberá realizarse mediante contratos definidos entre servicios.

No introducir nuevos servicios de infraestructura, frameworks o dependencias importantes sin justificar su necesidad.

---

## 15. Plan de pruebas

El plan deberá incluir pruebas unitarias, de integración, regresión, seguridad y escenarios end-to-end.

Como mínimo, considerar:

### Registro e identidad

- Registro mediante correo electrónico.
- Registro mediante Google.
- Registro mediante Facebook.
- Completado de perfil con DNI.
- Consulta de DNI exitosa.
- Consulta de DNI inválida.
- Servicio Datos Perú no disponible.
- DNI asociado a otra cuenta Paku.
- Usuario existente sin DNI.
- Propietario existente en HCVet.
- Intento de vinculación utilizando un DNI ajeno.

### Autorización

- API Key válida.
- API Key inválida o revocada.
- Propietario autorizado.
- Propietario no autorizado.
- Consentimiento revocado.
- Plataforma con permisos insuficientes.
- Intento de acceder a mascotas de otro propietario.

### Mascotas

- Registro de nueva mascota.
- Incorporación de mascota existente.
- Prevención de duplicados.
- Actualización de datos.
- Datos obligatorios faltantes.
- Cambio de propietario.
- Desvinculación de Paku sin eliminar historial clínico.

### Eventos

- Registro de eventos desde Paku.
- Consulta de eventos originados en otras plataformas.
- Mapeo correcto de tipos y campos.
- Identificación del autor.
- Corrección y anulación.
- Registro de peso.
- Prevención de cobros duplicados.
- Migración de eventos históricos.

### Resiliencia

- HCVet no disponible.
- Timeout después de registrar un evento.
- Reintentos.
- Idempotencia.
- Solicitudes concurrentes.
- Recuperación de sincronizaciones pendientes.
- Conflictos de datos.
- Reinicio del servicio con operaciones pendientes.

Todas las pruebas deberán ejecutarse utilizando ambientes controlados y datos de prueba.

---

## 16. Plan de implementación por fases

Utiliza la siguiente organización como referencia. Ajusta el orden según las dependencias reales que identifiques en los repositorios.

### Fase 0 — Análisis y especificación

- [ ] Revisar todos los repositorios involucrados.
- [ ] Identificar funcionalidades existentes y pendientes.
- [ ] Elaborar matriz de responsabilidades y fuentes de verdad.
- [ ] Elaborar matriz de mapeo de propietarios.
- [ ] Elaborar matriz de mapeo de mascotas.
- [ ] Elaborar matriz de mapeo de eventos.
- [ ] Definir arquitectura de integración.
- [ ] Identificar dependencias y riesgos.
- [ ] Elaborar especificaciones SDD.
- [ ] Elaborar plan de implementación.
- [ ] Elaborar checklist de tareas.

### Fase 1 — HCVet: propietarios y autorización

- [ ] Desacoplar propietario de cuenta de autenticación cuando corresponda.
- [ ] Implementar o adaptar autorización delegada.
- [ ] Adaptar autenticación de plataformas.
- [ ] Implementar registro idempotente de propietarios.
- [ ] Implementar consulta autorizada por DNI.
- [ ] Implementar vinculación con plataformas.
- [ ] Implementar actualización controlada de datos básicos.
- [ ] Adaptar consentimientos y permisos.
- [ ] Implementar auditoría.
- [ ] Ejecutar pruebas.

### Fase 2 — HCVet: mascotas y eventos

- [ ] Adaptar consulta de mascotas por propietario autorizado.
- [ ] Adaptar registro y actualización de mascotas.
- [ ] Validar identidad única de mascotas.
- [ ] Implementar prevención de duplicados.
- [ ] Revisar tipos y campos de eventos.
- [ ] Adaptar registro de eventos mediante autorización delegada.
- [ ] Implementar procedencia y autoría.
- [ ] Implementar o completar idempotencia.
- [ ] Adaptar consulta consolidada y paginación.
- [ ] Resolver dependencias de corrección y anulación.
- [ ] Ejecutar pruebas.

### Fase 3 — Paku: registro de usuarios

- [ ] Adaptar obligatoriedad del DNI.
- [ ] Integrar Datos Perú desde backend.
- [ ] Adaptar registro convencional.
- [ ] Adaptar registro social.
- [ ] Adaptar completado de perfil.
- [ ] Implementar autocompletado de nombres y apellidos.
- [ ] Adaptar formularios frontend.
- [ ] Implementar consentimientos.
- [ ] Implementar cliente de integración con HCVet.
- [ ] Implementar registro y vinculación de propietarios.
- [ ] Adaptar actualización de datos.
- [ ] Implementar regularización de usuarios existentes.
- [ ] Ejecutar pruebas.

### Fase 4 — Paku: integración Pet

- [ ] Incorporar referencia de mascota HCVet.
- [ ] Adaptar modelos y migraciones.
- [ ] Implementar consulta de mascotas existentes.
- [ ] Implementar incorporación de mascotas existentes.
- [ ] Integrar registro de mascotas.
- [ ] Integrar actualización de mascotas.
- [ ] Separar datos generales y operativos.
- [ ] Implementar estados de sincronización.
- [ ] Adaptar los frontends involucrados.
- [ ] Ejecutar pruebas.

### Fase 5 — Paku: integración Pet-records

- [ ] Implementar mapeo de eventos.
- [ ] Integrar registro de eventos en HCVet.
- [ ] Integrar consulta de historial consolidado.
- [ ] Conservar procedencia y autoría.
- [ ] Implementar tratamiento diferenciado del peso.
- [ ] Adaptar corrección y anulación.
- [ ] Implementar proyección local si resulta necesaria.
- [ ] Adaptar los frontends involucrados.
- [ ] Ejecutar pruebas.

### Fase 6 — Sincronización y resiliencia

- [ ] Implementar persistencia de operaciones pendientes.
- [ ] Implementar reintentos.
- [ ] Implementar claves de idempotencia.
- [ ] Implementar reconciliación.
- [ ] Implementar resolución de conflictos.
- [ ] Implementar observabilidad.
- [ ] Implementar gestión de errores permanentes.
- [ ] Ejecutar pruebas de interrupción y recuperación.

Los mecanismos esenciales de idempotencia y persistencia deberán adelantarse a las fases que los necesiten. Esta fase representa su consolidación, no significa que deban posponerse hasta el final.

### Fase 7 — Migración y cierre

- [ ] Preparar migración de usuarios existentes.
- [ ] Preparar migración y vinculación de mascotas existentes.
- [ ] Preparar migración de historiales.
- [ ] Ejecutar dry-run.
- [ ] Revisar resultados y conflictos.
- [ ] Ejecutar pruebas de regresión.
- [ ] Preparar estrategia de despliegue.
- [ ] Preparar estrategia de rollback.
- [ ] Actualizar documentación.
- [ ] Validar criterios de aceptación.

---

## 17. Gestión de tareas y continuidad entre sesiones

El archivo `PAKU-HCVET-TASKS.md` deberá permitir ejecutar tareas individualmente.

Utilizar identificadores como:

- `HCV-001`.
- `HCV-002`.
- `PAKU-USERS-001`.
- `PAKU-PET-001`.
- `PAKU-RECORDS-001`.
- `INT-001`.
- `MIG-001`.
- `QA-001`.

Cada tarea deberá tener:

- Identificador.
- Nombre.
- Repositorio.
- Módulo.
- Objetivo.
- Alcance.
- Dependencias.
- Prioridad.
- Archivos o componentes involucrados.
- Criterios de aceptación.
- Pruebas requeridas.
- Estado.
- Riesgos o consideraciones.
- Referencia a la especificación correspondiente.

Evitar tareas demasiado grandes como «Integrar completamente HCVet con Paku».

Dividirlas en unidades de trabajo acotadas, verificables y que puedan ejecutarse en sesiones independientes.

Utilizar estados equivalentes a:

- Pendiente.
- En progreso.
- Completada.
- Bloqueada.

Una tarea solo se considerará completada cuando su implementación, criterios de aceptación y pruebas correspondientes hayan sido satisfechos.

En futuras sesiones, al ejecutar una tarea:

1. Leer los documentos de requerimientos, implementación y tareas.
2. Verificar sus dependencias.
3. Trabajar únicamente dentro del alcance autorizado.
4. Implementar o actualizar pruebas.
5. Ejecutar las validaciones correspondientes.
6. Actualizar el estado de la tarea.
7. Documentar decisiones y modificaciones.
8. Registrar los bloqueos encontrados.
9. Indicar cuál es la siguiente tarea recomendada.
10. Detenerse antes de iniciar otra tarea no solicitada.

No marcar tareas como completadas si únicamente se ha implementado una parte o no se han podido ejecutar las pruebas correspondientes.

No realizar commits, push, despliegues ni modificaciones de producción sin autorización.

---

## 18. Entregables de esta primera ejecución

Al finalizar el análisis, necesito que me entregues:

### A. Diagnóstico actual

Describe cómo funcionan actualmente Paku y HCVet respecto a propietarios, usuarios, mascotas y eventos.

Referencia los archivos, modelos, endpoints, servicios y reglas de negocio concretos que sustentan el diagnóstico.

### B. Análisis del gap

Presenta una tabla con:

- Requerimiento.
- Estado actual.
- Cambio necesario.
- Repositorio afectado.
- Complejidad: baja, media o alta.
- Dependencias.
- Riesgos.

Diferencia claramente lo existente, lo parcialmente implementado y lo que todavía no existe.

### C. Arquitectura propuesta

Presenta:

- Diagrama de integración.
- Flujo de registro de usuario.
- Flujo de consulta DNI.
- Flujo de vinculación del propietario.
- Flujo de incorporación de mascotas existentes.
- Flujo de registro de nuevas mascotas.
- Flujo de registro y consulta de eventos.
- Mecanismo de autorización delegada.
- Estrategia de sincronización.

Utiliza diagramas Mermaid en la documentación cuando ayuden a explicar los flujos.

### D. Contratos de integración

Presenta los endpoints existentes que pueden reutilizarse y los endpoints nuevos o modificados que serían necesarios.

Para cada contrato relevante, documentar:

- Método HTTP.
- Ruta.
- Solicitud.
- Respuesta.
- Permisos.
- Validaciones.
- Errores.
- Idempotencia.
- Compatibilidad.

No asumir que los endpoints propuestos ya existen.

### E. Plan de trabajo

Genera el plan organizado por fases, repositorios y dependencias.

Identifica las tareas que pueden ejecutarse en paralelo y las que son bloqueantes.

### F. Checklist de implementación

Genera el archivo de tareas con identificadores individuales y criterios de aceptación.

Debe ser suficientemente detallado para que posteriormente pueda solicitarte, por ejemplo:

- «Ejecuta HCV-001».
- «Continúa con la siguiente tarea pendiente».
- «Ejecuta las siguientes dos tareas de Paku Users».
- «Revisa las tareas completadas de Pet».
- «Continúa con las tareas de integración de Pet-records».

### G. Preguntas y decisiones pendientes

No vuelvas a preguntarme decisiones que ya están establecidas en este documento.

Identifica únicamente preguntas que afecten materialmente la arquitectura, el comportamiento funcional, la seguridad o las reglas de negocio.

Para cada pregunta, explica brevemente:

- Por qué es necesaria.
- Qué alternativas existen.
- Qué recomiendas.
- Qué tareas dependen de ella.

No resuelvas unilateralmente decisiones que contradigan los requerimientos establecidos.

Si existen contradicciones entre este documento y la arquitectura actual, identifícalas y propón cómo resolverlas.

### H. Documentación SDD

Identifica qué documentos de dominio, especificaciones, constituciones, ADRs, planes y contratos necesitan actualizarse.

Respeta el proceso de aprobación definido en cada repositorio.

Distingue los documentos de diagnóstico de las especificaciones aprobadas.

---

## 19. Criterio final de éxito

La integración se considerará funcionalmente exitosa cuando:

1. Un usuario pueda registrarse en Paku mediante correo, Google o Facebook.
2. Pueda completar su perfil consultando su DNI y autocompletando sus nombres y apellidos.
3. Paku mantenga el control sobre sus datos personales y comerciales.
4. El propietario pueda registrarse o vincularse con HCVet sin generar una cuenta con contraseña.
5. HCVet pueda identificar al propietario mediante DNI sin crear duplicados.
6. El usuario pueda incorporar mascotas previamente registradas en HCVet.
7. Una nueva mascota registrada desde Paku obtenga su identidad única en HCVet.
8. Paku pueda registrar eventos clínicos mediante HCVet.
9. Paku pueda consultar eventos registrados por otros establecimientos autorizados.
10. Los eventos conserven su procedencia y autoría.
11. Los servicios comerciales de Paku no se vean afectados innecesariamente por la integración.
12. Las interrupciones y reintentos no generen duplicados ni cobros incorrectos.
13. La información existente pueda migrarse sin perder su integridad.
14. HCVet pueda integrarse con nuevas plataformas sin depender de Paku.

**Comienza guardando este documento, revisando los repositorios y elaborando el diagnóstico y plan de implementación.**

**No comiences todavía la programación de funcionalidades. Al finalizar, indícame qué documentos generaste, qué decisiones quedan pendientes y cuál debería ser la primera tarea de implementación.**
