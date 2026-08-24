# SoundAccess — Music API asegurada con OAuth 2.0 y JWT

**Semana 7 — Práctica: Autenticación y Autorización con OAuth 2.0 / JWT**
**Tarea 3 — Comparación de flujos: ROPC vs. Authorization Code + PKCE**

> **Nombre completo:** Diego Saavedra
> **Carné / ID de estudiante:** [PENDING: STUDENT ID]
> **Sede / Sección:** [PENDING: CAMPUS / SECTION]
> **Tecnología principal:** Python 3.11, FastAPI, SQLAlchemy, SQLite, PyJWT, Argon2
> **Repositorio:** [PENDING: REPOSITORY URL — aún no se ha publicado este proyecto en GitHub/GitLab; no hay `git remote` configurado]

---

## 1. Descripción general

SoundAccess es una API de catálogo musical protegida mediante **OAuth 2.0** (RFC 6749) y
**JWT** (RFC 7519 / RFC 9068), construida como práctica académica. Implementa dos flujos
reales de OAuth —**Authorization Code con PKCE (S256)** y **Client Credentials**— sobre un
Servidor de Autorización y un Servidor de Recursos separados lógicamente, más un cliente de
demostración (SoundAccess Web Player) que ejecuta el flujo completo desde el navegador.

No usa branding, logotipos ni contenido de Spotify: "SoundAccess", los artistas y las
canciones del catálogo son ficticios.

## 2. Arquitectura

El proyecto separa tres roles lógicos (ver `docs/diagrams/component_diagram.mmd`):

| Rol | Responsabilidad | Ubicación |
|---|---|---|
| **Cliente OAuth** | Inicia el flujo, gestiona PKCE, consume la API | `frontend/` |
| **Servidor de Autorización** | Login, consentimiento, emisión de `authorization_code`, `client_credentials`, emisión de JWT | `app/oauth/` |
| **Servidor de Recursos** | Valida JWT, aplica scopes, expone el catálogo/perfil/playlists | `app/api/` |

Los tres roles corren dentro del mismo proceso FastAPI para simplificar la demostración
local, pero están organizados en módulos independientes con responsabilidades y
dependencias propias, de modo que el Servidor de Autorización podría desplegarse por
separado sin reescribir el Servidor de Recursos.

Diagramas editables (Mermaid) con exportación visual en `docs/diagrams/`:
- `component_diagram.mmd` / `.png` — componentes y flujo de datos.
- `auth-code-pkce.mmd` / `.png` — secuencia completa Authorization Code + PKCE.
- `ropc.mmd` / `.png` — secuencia completa ROPC (Task 3, ver §10-bis).

> **Tarea 3 — comparación de flujos.** Este proyecto fue extendido (sin
> reescribirse) para agregar el grant **ROPC** (`grant_type=password`, RFC
> 6749 §4.3) como flujo legacy de comparación frente a Authorization Code +
> PKCE. Todo el trabajo vive en la rama `task-3-ropc-pkce-comparison`; `main`
> conserva intacta la entrega original (Semana 7). Ver §11-bis, §13, §16-bis,
> `docs/task3_gap_analysis.md` y `docs/comparative_analysis_ropc_vs_pkce.md`.

## 3. Tecnologías

- **Python 3.11**, **FastAPI** — framework ASGI y documentación OpenAPI automática.
- **SQLAlchemy 2.0** — ORM (capa de persistencia agnóstica al motor SQL).
- **SQLite** — base de datos local de desarrollo (persistencia real, no producción).
- **PyJWT** — firma y validación de JWT (algoritmo fijado explícitamente; ver §12).
- **argon2-cffi** — hashing de contraseñas de usuario y de secretos de clientes (Argon2id).
- **Pytest + httpx (TestClient)** — pruebas automatizadas.
- **Swagger UI (auto-hospedado)** — documentación interactiva sin dependencia de CDN.

## 4. Prerrequisitos

- Python 3.11 o superior.
- `pip`.
- (Opcional) Node.js, solo si se desea regenerar los PNG de los diagramas con
  `@mermaid-js/mermaid-cli`.

## 5. Instalación

```bash
cd Week7_SoundAccess_OAuth_API
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 6. Variables de entorno

Copiar `.env.example` a `.env` y completar los valores. **Nunca** comprometer `.env` a Git
(ya está en `.gitignore`).

| Variable | Descripción |
|---|---|
| `SOUNDACCESS_JWT_SECRET` | Clave HMAC para firmar los JWT. Generar con `python -c "import secrets; print(secrets.token_urlsafe(64))"`. |
| `SOUNDACCESS_JWT_ISSUER` / `SOUNDACCESS_JWT_AUDIENCE` | Claims `iss`/`aud` esperados. |
| `SOUNDACCESS_ACCESS_TOKEN_MINUTES` | Vida del access token (por defecto 15). |
| `SOUNDACCESS_AUTH_CODE_SECONDS` | Vida del código de autorización (por defecto 60). |
| `SOUNDACCESS_DATABASE_URL` | Cadena de conexión SQLAlchemy (SQLite por defecto). |
| `SOUNDACCESS_CORS_ORIGINS` | Orígenes permitidos, separados por coma (sin comodín `*`). |
| `SOUNDACCESS_SEED_USER_PASSWORD` | Contraseña para los usuarios de demostración al sembrar la base. |
| `SOUNDACCESS_SEED_SERVICE_SECRET` | Secreto del cliente de servicio al sembrar la base. |
| `SOUNDACCESS_SEED_LEGACY_CLIENT_SECRET` | Secreto del cliente legacy ROPC (`legacy-client`) al sembrar la base. *(Tarea 3)* |
| `SOUNDACCESS_CLIENT_REGISTRATION_KEY` | Clave administrativa requerida por `POST /oauth/clients`. |

## 7. Inicialización de la base de datos y siembra (seed)

```bash
python -m scripts.init_db
```

Crea las tablas (si no existen) y siembra datos de desarrollo **una sola vez**
(es idempotente: si ya hay usuarios, no vuelve a sembrar):

- 3 usuarios: `ana`, `bruno`, `alumno.demo` (contraseña: `SOUNDACCESS_SEED_USER_PASSWORD`).
- 1 cliente público `web-user-client` (Authorization Code + PKCE).
- 1 cliente confidencial `music-service-client` (Client Credentials).
- 1 cliente confidencial `legacy-client` (ROPC — solo comparación, Tarea 3).
- 8 canciones ficticias y 3 playlists de ejemplo (la tercera, propiedad de
  `alumno.demo`, sirve para ejercitar el flujo ROPC).

`SOUNDACCESS_SEED_USER_PASSWORD`, `SOUNDACCESS_SEED_SERVICE_SECRET` y
`SOUNDACCESS_SEED_LEGACY_CLIENT_SECRET` son **obligatorias** para sembrar: no existe un
valor de respaldo (`fallback`) en el código. Si alguna falta o está vacía en `.env`,
`python -m scripts.init_db` falla de inmediato con un `SeedConfigurationError` que indica
exactamente cuál variable falta, en lugar de sembrar silenciosamente con una credencial
conocida/predecible.

## 8. Ejecutar la aplicación

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- Cliente de demostración: <http://127.0.0.1:8000/client>
- Swagger UI: <http://127.0.0.1:8000/docs>
- OpenAPI JSON: <http://127.0.0.1:8000/openapi.json>

## 9. Usuarios y clientes de demostración

| Usuario | Rol | Contraseña |
|---|---|---|
| `ana` | Usuario final | valor de `SOUNDACCESS_SEED_USER_PASSWORD` |
| `bruno` | Usuario final (para probar aislamiento entre usuarios) | valor de `SOUNDACCESS_SEED_USER_PASSWORD` |
| `alumno.demo` | Usuario final, exclusivo para ejercitar ROPC *(Tarea 3)* | valor de `SOUNDACCESS_SEED_USER_PASSWORD` |

| Cliente | Tipo | Grant | Scopes permitidos |
|---|---|---|---|
| `web-user-client` | Público | `authorization_code` (+PKCE S256) | `catalog:read profile:read playlist:read playlist:write` |
| `music-service-client` | Confidencial | `client_credentials` | `catalog:read` |
| `legacy-client` *(Tarea 3)* | Confidencial | `password` (ROPC) | `profile.read playlists.read` |

`legacy-client` **no** puede registrarse mediante `POST /oauth/clients` — el
validador de ese endpoint solo acepta `authorization_code` y
`client_credentials` como `allowed_grant_types` (ver `app/schemas.py`). El
grant `password` únicamente existe para el cliente sembrado por
`scripts/init_db.py`, deliberadamente, para que ROPC nunca pueda
auto-aprovisionarse (ver §10-bis).

El registro de nuevos clientes (`POST /oauth/clients`) es controlado: requiere el header
`X-Registration-Key` con el valor de `SOUNDACCESS_CLIENT_REGISTRATION_KEY`. No existe un
endpoint público sin autenticación para crear clientes privilegiados.

## 10. Flujo Authorization Code + PKCE (S256)

1. El cliente genera `code_verifier` (aleatorio) y `code_challenge = BASE64URL(SHA256(code_verifier))`.
2. `GET /oauth/authorize` con `client_id`, `redirect_uri`, `response_type=code`, `scope`,
   `state`, `code_challenge`, `code_challenge_method=S256` → formulario de login y consentimiento.
3. El usuario se autentica y autoriza (o deniega) los scopes solicitados.
4. El servidor crea un `authorization_code` de un solo uso (60s de vida), ligado al cliente,
   al usuario, al `redirect_uri` exacto y al `code_challenge`, y redirige a
   `redirect_uri?code=...&state=...`.
5. El cliente valida que `state` coincide (anti-CSRF) y canjea el código en
   `POST /oauth/token` junto con `code_verifier`.
6. El servidor recalcula `SHA256(code_verifier)` y lo compara con el `code_challenge`
   almacenado; si coincide, invalida el código y emite un JWT de acceso.

`code_challenge_method=plain` **no** es aceptado; solo `S256`.

## 11. Flujo Client Credentials

`POST /oauth/token` con `grant_type=client_credentials`, `client_id`, `client_secret` y
`scope` (opcional). El servidor autentica al cliente confidencial (Argon2id contra el hash
almacenado), valida que el scope solicitado esté dentro de lo permitido, y emite un JWT cuyo
`sub` es el propio `client_id` (identidad de máquina, no de usuario). Este token **no** puede
acceder a `/api/me` ni a playlists privadas (devuelve 403: es un token válido pero sin
autorización para recursos personales).

## 11-bis. Flujo ROPC — Resource Owner Password Credentials *(Tarea 3, solo comparación)*

> **ROPC no es una recomendación de arquitectura.** Se implementa aquí
> exclusivamente para comparación técnica controlada contra Authorization
> Code + PKCE, tal como pide la Tarea 3. Ver el análisis completo en
> `docs/comparative_analysis_ropc_vs_pkce.md`.

`POST /oauth/token` con `grant_type=password` (RFC 6749 §4.3):

```
grant_type=password&username=alumno.demo&password=<demo-password>&client_id=legacy-client&client_secret=<demo-secret>&scope=profile.read playlists.read
```

Diagrama de secuencia: `docs/diagrams/ropc.mmd` / `.png`.

**Por qué está restringido a un único cliente sembrado.** El grant `password`
solo se acepta si el cliente autenticado tiene `"password"` en su
`allowed_grant_types` — en este proyecto, únicamente `legacy-client`, un
cliente confidencial creado por `scripts/init_db.py` (nunca a través de
`POST /oauth/clients`, cuyo validador de schema rechaza `"password"` como
grant registrable). Esto es lo que impide que **cualquier cliente arbitrario**
use ROPC.

**Validación y manejo de errores** (`app/oauth/router.py::_grant_ropc`):

| Situación | HTTP | `error` | Nota |
|---|---|---|---|
| Falta `client_id`, `client_secret`, `username` o `password` | 400 | `invalid_request` | |
| `client_id` desconocido o `client_secret` incorrecto | 401 | `invalid_client` | Mismo error para ambos casos (no revela cuál falló). |
| Cliente autenticado pero sin `password` en sus grants permitidos | 400 | `unauthorized_client` | Así se rechaza ROPC para "clientes arbitrarios". |
| `scope` solicitado excede lo permitido para el cliente | 400 | `invalid_scope` | |
| Usuario inexistente **o** contraseña incorrecta | 400 | `invalid_grant` | Mismo error/mensaje en ambos casos — no permite enumerar usuarios. |
| Credenciales válidas | 200 | — | Emite JWT reutilizando `app/security.py::create_access_token` (misma vida ≤15 min, mismos claims que los demás grants). |

**Manejo de la contraseña.** La contraseña llega solo en el cuerpo del
`POST /oauth/token` (nunca en la URL ni en query string), se usa una única
vez como variable local para `verify_secret(password, user.password_hash)`
dentro de `_grant_ropc`, y se descarta al retornar la función: no se
almacena, no se registra en logs (`logger.info` solo registra causas
genéricas de fallo de JWT, nunca contraseñas — ver `app/api/deps.py`), y no
aparece en la respuesta ni en ningún claim del JWT.

**JWT emitido por ROPC.** Reutiliza exactamente la misma infraestructura de
firma/validación que Authorization Code y Client Credentials (§12): mismo
algoritmo fijado explícitamente, mismos claims obligatorios, mismo `iss`/
`aud`, misma vida corta. El `sub` es el `id` del usuario (`alumno.demo`), no
el `client_id` — igual que en Authorization Code, y a diferencia de Client
Credentials. Un token ROPC con firma alterada, `alg=none`, `iss`/`aud`
incorrectos o expirado es rechazado con 401 exactamente igual que cualquier
otro token (`app/security.py::decode_access_token` no distingue el grant de
origen).

**Scopes con notación distinta (compatibilidad, no permisos nuevos).** El enunciado de la
Tarea 3 especifica los scopes ROPC con notación de punto (`profile.read`, `playlists.read`)
en vez de los scopes con dos puntos ya usados y probados en la Tarea 1 (`profile:read`,
`playlist:read`). Para no arriesgar una regresión sobre el contrato ya probado de la Tarea 1
**no se renombraron** los scopes existentes ni se creó un permiso nuevo: en su lugar,
`app/api/deps.py::SCOPE_ALIASES` define un mapeo de **compatibilidad** que existe
exclusivamente para que el enunciado de la Tarea 3 pueda usar la notación de scope que
especifica, sin romper la implementación ya existente de SoundAccess. `profile.read` y
`playlists.read` **no son permisos distintos**: en el punto donde se verifica la
autorización (`require_scopes`), se tratan como el mismo permiso que `profile:read` y
`playlist:read` respectivamente — conceden acceso exactamente al mismo recurso protegido,
ni más ni menos. El claim `scope` del JWT sigue conteniendo literalmente lo que el enunciado
espera (`profile.read playlists.read`); solo la *comparación* en `require_scopes` es
consciente del alias. Detalle completo y justificación en `docs/task3_gap_analysis.md`.

## 12. JWT — estructura y validación

Claims emitidos: `iss`, `sub`, `aud`, `exp`, `iat`, `jti`, `client_id`, `scope`.

Validación en cada request protegida (`app/security.py::decode_access_token`):
- Algoritmo permitido **explícito** (`HS256`, vía `algorithms=[...]` en `pyjwt.decode`), lo
  que rechaza automáticamente `alg=none` y cualquier sustitución de algoritmo.
- Firma, `iss`, `aud`, `exp`, `iat` y presencia de todos los claims requeridos.
- Los tokens solo se aceptan en el header `Authorization: Bearer <token>`; nunca en query
  string ni en el cuerpo.
- Vida corta: 15 minutos por defecto (`SOUNDACCESS_ACCESS_TOKEN_MINUTES`).

## 13. Scopes

| Scope | Efecto | Alias equivalente *(Tarea 3, solo ROPC)* |
|---|---|---|
| `catalog:read` | Leer el catálogo público de canciones. | — |
| `profile:read` | Leer el perfil del usuario autenticado (solo tokens de usuario). | `profile.read` |
| `playlist:read` | Leer las playlists propias. | `playlists.read` |
| `playlist:write` | Crear/eliminar playlists propias. | — |

Los scopes se aplican en el Servidor de Recursos (`app/api/deps.py::require_scopes`), no
solo se muestran en el token. Los alias de la columna derecha (§11-bis) solo aplican al
comparar scopes en `require_scopes`; el cliente `legacy-client` únicamente puede emitir
tokens con `profile.read`/`playlists.read` (nunca con la notación de dos puntos).

## 14. Endpoints protegidos

| Método | Ruta | Scope | Comportamiento |
|---|---|---|---|
| GET | `/api/catalog/tracks` | `catalog:read` | Lista canciones ficticias. |
| GET | `/api/me` | `profile:read` | Perfil del usuario (rechaza tokens de servicio → 403). |
| POST | `/api/playlists` | `playlist:write` | Crea una playlist del usuario autenticado. |
| GET | `/api/playlists` | `playlist:read` | *(Tarea 3)* Lista **solo** las playlists del usuario autenticado. |
| GET | `/api/playlists/{id}` | `playlist:read` | Solo si el usuario es el dueño (si no, 404). |
| DELETE | `/api/playlists/{id}` | `playlist:write` | Solo si el usuario es el dueño (si no, 404). |

**401** = no se pudo autenticar (token ausente/malformado/inválido/expirado/`iss`/`aud`
incorrectos). **403** = token válido pero sin autorización suficiente (scope faltante o
token de servicio sobre un recurso personal). **404** en vez de 403 para playlists ajenas,
para no revelar si el recurso existe.

## 15. Pruebas automatizadas

```bash
pytest -v
```

55 pruebas: los 6 escenarios obligatorios (`tests/test_scenarios.py`), pruebas de
endurecimiento (`tests/test_security.py`) — PKCE inválido, código reutilizado, código
expirado, `redirect_uri` no coincide, secreto de cliente incorrecto, escalamiento de scope,
`alg=none`, claims faltantes, token en query string, inyección tipo SQL, payload inválido,
etc. — y, desde la Tarea 3, `tests/test_task3_ropc_pkce.py` con los escenarios A1-A3 (ROPC)
y B1-B5 (Authorization Code + PKCE), nombrados según los IDs del propio enunciado:

| ID | Escenario | Resultado esperado |
|---|---|---|
| A1 | ROPC con credenciales válidas | 200, JWT válido, scopes correctos, funciona en `/api/me` y `/api/playlists` |
| A2 | ROPC con credenciales/cliente inválidos | `invalid_grant` / `invalid_client` / `unauthorized_client` / `invalid_request` según el caso |
| A3 | Recurso protegido con token ausente/expirado/alterado/con scope insuficiente | 401 (autenticación) o 403 (autorización) |
| B1 | Flujo PKCE completo (login, consentimiento, scopes, `state`, `redirect_uri`) | 200, JWT funcional |
| B2 | `redirect_uri` no registrado | 400, nunca redirige |
| B3 | `code_verifier` incorrecto | 400 `invalid_grant` |
| B4 | Reutilización del mismo `authorization_code` | 400 `invalid_grant` en el segundo intento |
| B5 | Discrepancia de `state` | Servidor devuelve el `state` recibido sin alterar; el cliente aborta el intercambio antes de llamar a `/oauth/token` (verificado como contrato de código en `frontend/callback.html`) |

Ejecutar solo la suite de la Tarea 3: `pytest tests/test_task3_ropc_pkce.py -v`.

## 16. Controles de seguridad implementados

- Contraseñas y secretos de cliente: **Argon2id**, nunca en texto plano.
- Códigos de autorización: hash SHA-256 almacenado (no el valor crudo), un solo uso,
  expiración corta, ligados a cliente + usuario + `redirect_uri` + PKCE.
- `redirect_uri` validado por **coincidencia exacta** contra la lista blanca del cliente;
  ante un valor no registrado, el servidor **nunca redirige** (previene open redirect).
- Algoritmo JWT fijado explícitamente; `alg=none` y sustitución de algoritmo rechazados.
- CORS restringido a orígenes locales explícitos (sin comodín).
- Sin trazas de pila expuestas al cliente (manejador global de excepciones).
- Sin secretos en logs (verificado manualmente, ver `docs/report`).
- Validación de entrada con Pydantic en todos los endpoints (incluye formato de
  `client_id`, `redirect_uri`, scopes, IDs de recursos).
- *(Tarea 3)* Grant ROPC (`password`) implementado **solo** como comparación legacy
  controlada: gateado a un único cliente confidencial sembrado
  (`legacy-client`), nunca auto-registrable, contraseña nunca almacenada ni
  registrada en logs, mismo endurecimiento de JWT que los demás grants. Ver
  §11-bis y `docs/comparative_analysis_ropc_vs_pkce.md`.

## 16-bis. Comparación de flujos: ROPC vs. Authorization Code + PKCE

| Aspecto | ROPC (`password`) | Authorization Code + PKCE |
|---|---|---|
| Exposición de la contraseña al cliente | El cliente ve y transmite la contraseña en texto plano dentro del cuerpo del `POST /oauth/token`. | El cliente nunca ve la contraseña; solo el Servidor de Autorización la procesa, en su propio formulario de login. |
| Superficie de robo de credenciales | Cualquier cliente autorizado para `password` es un punto de fuga potencial de contraseñas reales. | El code_verifier no tiene valor sin el code_challenge original ni el `authorization_code`; interceptar uno solo no basta. |
| Compatibilidad con MFA / login federado | Incompatible: no hay paso intermedio para un segundo factor o un proveedor externo. | Compatible: el login ocurre en el Servidor de Autorización, que puede añadir MFA o federación sin cambiar al cliente. |
| Consentimiento explícito del usuario | No hay pantalla de consentimiento; el usuario confía "a ciegas" en el cliente. | Pantalla de login + consentimiento explícita, con scopes visibles antes de autorizar. |
| Idoneidad para producción/nuevas integraciones | No recomendado (RFC 9700 §2.4); solo aceptable como puente temporal y controlado. | Flujo recomendado para clientes públicos y confidenciales modernos. |

Análisis extendido (250-400 palabras) en `docs/comparative_analysis_ropc_vs_pkce.md`.

## 16-ter. Controles de seguridad: librería vs. implementación explícita

| Control | Origen |
|---|---|
| Hashing de contraseñas/secretos (Argon2id) | Librería (`argon2-cffi`), invocada desde `app/security.py`. |
| Firma/verificación de JWT, rechazo de `alg=none` | Librería (`PyJWT`), configurada explícitamente con `algorithms=[...]` fijo — el rechazo de `alg=none` es un efecto de **cómo se llama** a la librería, no automático. |
| Validación de `iss`/`aud`/`exp` del JWT | Librería (`PyJWT`, parámetros `issuer`/`audience` en `decode`). |
| Un solo uso y expiración del `authorization_code` | Implementación explícita del proyecto (`app/oauth/router.py`, columna `used` + `expires_at` en `AuthorizationCode`). |
| Comparación exacta de `redirect_uri` (anti open-redirect) | Implementación explícita (comparación de string exacta contra la lista blanca del cliente). |
| PKCE S256 (generación y verificación) | Implementación explícita (`hashlib.sha256` + `base64.urlsafe_b64encode`, RFC 7636 en `app/oauth/router.py`); el rechazo de `plain` es una decisión explícita del proyecto. |
| Verificación de `state` (anti-CSRF) | Implementación explícita, del lado del **cliente** (`frontend/callback.html`), como exige RFC 6749 §10.12 — el servidor solo lo devuelve sin alterar. |
| Alcance/scopes por endpoint | Implementación explícita (`app/api/deps.py::require_scopes`), incluidos los alias de la Tarea 3. |
| Gateo del grant ROPC a un único cliente autorizado | Implementación explícita (`app/oauth/router.py::_grant_ropc`), no una capacidad genérica de la librería OAuth. |
| Validación de entrada (formatos, longitudes) | Librería (Pydantic v2), con validadores explícitos del proyecto para reglas de negocio (scopes válidos, formato de `client_id`, etc.). |

## 17. Swagger / OpenAPI

`GET /docs` sirve una Swagger UI **auto-hospedada** (los assets de `swagger-ui-dist` están
vendorizados en `app/static/swagger-ui/`, no se cargan desde un CDN), de modo que la
documentación funciona sin acceso a Internet. Todos los endpoints `/api/*` están marcados
con seguridad `BearerJWT` y documentan explícitamente las respuestas 401/403.

## 18. Solución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| `pydantic_settings.ValidationError` al iniciar | Falta `.env` o falta una variable requerida | Copiar `.env.example` a `.env` y completar valores |
| `sqlite3.OperationalError: no such table` | Base de datos no inicializada | Ejecutar `python -m scripts.init_db` |
| 401 en todos los endpoints `/api/*` | Token ausente/expirado/mal copiado | Repetir el flujo de autorización; revisar `Authorization: Bearer <token>` |
| Swagger UI en blanco | Solo ocurre si `app/static/swagger-ui/` falta | Los assets están versionados en el repo; verificar que no se hayan excluido |
| `ModuleNotFoundError` | Entorno virtual no activado o dependencias no instaladas | `pip install -r requirements.txt` |

## 19. Estructura del repositorio

```text
Week7_SoundAccess_OAuth_API/
├── app/
│   ├── oauth/         # Servidor de Autorización (/oauth/*)
│   ├── api/            # Servidor de Recursos (/api/*)
│   ├── static/          # Swagger UI auto-hospedado
│   ├── templates/     # Login + consentimiento (Jinja2)
│   ├── models.py, schemas.py, security.py, config.py, database.py, seed.py, main.py
├── frontend/           # Cliente OAuth de demostración (PKCE en el navegador)
├── scripts/             # init_db.py, capture_browser_evidence.py, capture_task3_evidence.py
├── tests/                 # 55 pruebas (pytest), incluye test_task3_ropc_pkce.py
├── docs/
│   ├── diagrams/       # Mermaid (.mmd) + PNG: component_diagram, auth-code-pkce, ropc (Tarea 3)
│   ├── evidence/        # EVIDENCIAS.md + capturas + salidas reales
│   ├── report/          # Informe académico de la Semana 7 (heredado; no forma parte de los
│   │                     # entregables de la Tarea 3, ver nota más abajo)
│   ├── task3_gap_analysis.md                 # Auditoría de brechas previa a la Tarea 3
│   └── comparative_analysis_ropc_vs_pkce.md  # Análisis comparativo (Tarea 3)
├── .env.example
├── requirements.txt
├── README.md
└── EVIDENCIAS.md
```

**Nota sobre `docs/report/`.** El informe académico (`Informe_Academico_SoundAccess.docx`/
`.pdf`) documenta la entrega original de la Semana 7 (Authorization Code + PKCE, Client
Credentials). Los entregables exigidos por la Tarea 3 son este `README.md`, los dos
diagramas editables (`ropc.mmd`, `auth-code-pkce.mmd`), la colección/script de pruebas,
`EVIDENCIAS.md` y el análisis comparativo — **no** un informe académico nuevo. Por eso el
informe existente se conserva sin modificar y no debe interpretarse como el informe de la
Tarea 3.

## 20. Información del repositorio

- **URL del repositorio:** [PENDING: REPOSITORY URL — el proyecto aún vive solo localmente;
  no tiene un `git remote` configurado. Completar con la URL una vez publicado en
  GitHub/GitLab.]
- **Historial de Git:** commits incrementales por fase (ver `git log`); no hay un único
  commit final gigante.
- **Rama de la Tarea 3:** `task-3-ropc-pkce-comparison`, creada desde `main` (que conserva
  intacta la entrega de la Semana 7). Todo el trabajo de ROPC/PKCE-comparativo vive en esa
  rama, con commits incrementales propios (ver `git log task-3-ropc-pkce-comparison`).
