# SoundAccess — Music API asegurada con OAuth 2.0 y JWT

**Semana 7 — Práctica: Autenticación y Autorización con OAuth 2.0 / JWT**

> **Nombre completo:** [PENDING: FULL NAME]
> **Carné / ID de estudiante:** [PENDING: STUDENT ID]
> **Sede / Sección:** [PENDING: CAMPUS / SECTION]
> **Tecnología principal:** Python 3.11, FastAPI, SQLAlchemy, SQLite, PyJWT, Argon2
> **Repositorio:** [PENDING: REPOSITORY URL]

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
- `sequence_diagram.mmd` / `.png` — secuencia completa Authorization Code + PKCE.

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
| `SOUNDACCESS_CLIENT_REGISTRATION_KEY` | Clave administrativa requerida por `POST /oauth/clients`. |

## 7. Inicialización de la base de datos y siembra (seed)

```bash
python -m scripts.init_db
```

Crea las tablas (si no existen) y siembra datos de desarrollo **una sola vez**
(es idempotente: si ya hay usuarios, no vuelve a sembrar):

- 2 usuarios: `ana`, `bruno` (contraseña: `SOUNDACCESS_SEED_USER_PASSWORD`).
- 1 cliente público `web-user-client` (Authorization Code + PKCE).
- 1 cliente confidencial `music-service-client` (Client Credentials).
- 8 canciones ficticias y 2 playlists de ejemplo.

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

| Cliente | Tipo | Grant | Scopes permitidos |
|---|---|---|---|
| `web-user-client` | Público | `authorization_code` (+PKCE S256) | `catalog:read profile:read playlist:read playlist:write` |
| `music-service-client` | Confidencial | `client_credentials` | `catalog:read` |

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

| Scope | Efecto |
|---|---|
| `catalog:read` | Leer el catálogo público de canciones. |
| `profile:read` | Leer el perfil del usuario autenticado (solo tokens de usuario). |
| `playlist:read` | Leer las playlists propias. |
| `playlist:write` | Crear/eliminar playlists propias. |

Los scopes se aplican en el Servidor de Recursos (`app/api/deps.py::require_scopes`), no
solo se muestran en el token.

## 14. Endpoints protegidos

| Método | Ruta | Scope | Comportamiento |
|---|---|---|---|
| GET | `/api/catalog/tracks` | `catalog:read` | Lista canciones ficticias. |
| GET | `/api/me` | `profile:read` | Perfil del usuario (rechaza tokens de servicio → 403). |
| POST | `/api/playlists` | `playlist:write` | Crea una playlist del usuario autenticado. |
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

38 pruebas, incluyendo los 6 escenarios obligatorios (`tests/test_scenarios.py`) y pruebas
de endurecimiento adicionales (`tests/test_security.py`): PKCE inválido, código reutilizado,
código expirado, `redirect_uri` no coincide, secreto de cliente incorrecto, escalamiento de
scope, `alg=none`, claims faltantes, token en query string, inyección tipo SQL, payload
inválido, etc.

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
- Sin grant ROPC (`password`) implementado.
- Validación de entrada con Pydantic en todos los endpoints (incluye formato de
  `client_id`, `redirect_uri`, scopes, IDs de recursos).

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
├── scripts/             # init_db.py, capture_browser_evidence.py
├── tests/                 # 38 pruebas (pytest)
├── docs/
│   ├── diagrams/       # Mermaid (.mmd) + PNG
│   ├── evidence/        # EVIDENCIAS.md + capturas + salidas reales
│   └── report/          # Informe académico
├── .env.example
├── requirements.txt
├── README.md
└── EVIDENCIAS.md
```

## 20. Información del repositorio

- **URL del repositorio:** [PENDING: REPOSITORY URL]
- **Historial de Git:** commits incrementales por fase (ver `git log`); no hay un único
  commit final gigante.
