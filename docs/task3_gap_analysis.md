# Task 3 — Análisis de brechas contra la implementación existente

Auditoría realizada antes de escribir código, comparando SoundAccess (Semana 7 /
Task 1, rama `main`) contra los requisitos de Task 3 (rama
`task-3-ropc-pkce-comparison`).

## Ya implementado correctamente (sin cambios)

| Requisito | Ubicación | Nota |
|---|---|---|
| Autenticación de usuario (login) | `app/oauth/router.py`, `app/templates/authorize.html` | Argon2id, sin exponer contraseña al cliente OAuth |
| Clientes OAuth registrados | `app/models.py::OAuthClient`, `app/seed.py` | `allowed_grant_types` ya sirve como mecanismo de autorización por-cliente y por-grant |
| Endpoint de token | `app/oauth/router.py::token` | Despachador por `grant_type`; se añade la rama `password` |
| Endpoint de autorización | `app/oauth/router.py::authorize_get/post` | Valida client_id, redirect_uri exacta, scope, response_type, PKCE method |
| JWT (emisión/validación) | `app/security.py` | Claims completos, algoritmo fijado, iss/aud/exp validados |
| Scopes | `app/api/deps.py::require_scopes` | Aplicados en el Servidor de Recursos, no solo en el token |
| API protegida | `app/api/router.py` | `/api/catalog/tracks`, `/api/me`, `/api/playlists` (POST/GET id/DELETE) |
| Authorization Code flow | `app/oauth/router.py` | Completo |
| PKCE S256 | `app/security.py::pkce_verify` | `plain` explícitamente rechazado |
| state (lado cliente) | `frontend/index.html`, `frontend/callback.html` | Generado, guardado en `sessionStorage`, comparado antes de canjear el código |
| redirect_uri exacta | `app/oauth/router.py::_validate_authorize_request` | Comparación de cadena exacta contra lista blanca; sin redirección en caso de fallo |
| Expiración del código | `app/config.py` (`auth_code_seconds=60`) | Ya ≤120s exigido por Task 3; sin cambio |
| Un solo uso del código | `app/models.py::AuthorizationCode.used` | Ya implementado y probado |
| Pruebas existentes | `tests/test_scenarios.py`, `tests/test_security.py` | 38 pruebas, todas deben seguir pasando (regresión) |
| Base de datos | `app/models.py` | SQLite + SQLAlchemy 2.0, se extiende sin reemplazar |
| Documentación | `README.md`, `EVIDENCIAS.md`, `docs/report/` | Se actualiza, no se reemplaza |

## Parcialmente implementado / requiere extensión

| Requisito | Estado actual | Acción |
|---|---|---|
| Prueba automática explícita de `state` incorrecto | La lógica de defensa existe (cliente), pero no hay una prueba automatizada dedicada | Se añade una prueba de contrato (verifica que la lógica de comparación siga presente en `frontend/callback.html`) + evidencia real con Playwright forzando un `state` alterado |
| Trazabilidad B1-B5 con nombres explícitos | La cobertura funcional ya existe pero repartida en pruebas de Task 1 sin la nomenclatura A1-A3/B1-B5 | Se añaden pruebas nuevas con esos nombres exactos en `tests/test_task3_ropc_pkce.py`, sin eliminar las pruebas originales |

## Faltante (requiere código nuevo)

| Requisito | Detalle | Diseño elegido |
|---|---|---|
| Grant ROPC (`grant_type=password`) | No implementado (explícitamente rechazado en Task 1, por diseño correcto en ese momento) | Nueva función `_grant_ropc` en `app/oauth/router.py`, habilitada **solo** para clientes con `password` en `allowed_grant_types` |
| Cliente legado `legacy-client` | No existe | Se añade en `app/seed.py`: confidencial, `allowed_grant_types="password"`, secreto Argon2id vía `SOUNDACCESS_SEED_LEGACY_CLIENT_SECRET` |
| Usuario `alumno.demo` | No existe (solo `ana`/`bruno`) | Se añade en `app/seed.py`, contraseña reutilizando `SOUNDACCESS_SEED_USER_PASSWORD` |
| Endpoint `GET /api/playlists` (listar) | No existe (solo `GET /api/playlists/{id}`) | Se añade en `app/api/router.py`, devuelve solo las playlists del usuario autenticado |
| Scopes `profile.read` / `playlists.read` | No existen; Task 1 usa `profile:read` / `playlist:read` (dos puntos, singular) | **Decisión de diseño documentada abajo** |
| Diagrama Mermaid de ROPC | No existe | `docs/diagrams/ropc.mmd` (+ PNG) |
| Diagrama de Authorization Code + PKCE para Task 3 | Ya existe y sigue siendo exacto | Renombrado a `docs/diagrams/auth-code-pkce.mmd` (+ PNG) para que ambos diagramas de Task 3 usen nombres explícitos; contenido sin cambios, sin duplicar |
| Análisis comparativo (250–400 palabras) | No existe | `docs/comparative_analysis_ropc_vs_pkce.md` |
| Matriz de requisitos Task 3 | No existe | Se añade a `EVIDENCIAS.md` |

## Decisión de diseño: nomenclatura de scopes ROPC

El enunciado de Task 3 ejemplifica el request ROPC con `scope=profile.read
playlists.read` (con punto, y "playlists" en plural), mientras que Task 1 ya
estableció y probó `profile:read` / `playlist:read` (con dos puntos, singular)
en toda la base de código, el cliente de demostración y 38 pruebas existentes.

Renombrar los scopes existentes rompería la compatibilidad hacia atrás y
violaría la regla explícita de Task 3 de **no romper el comportamiento
existente** (Sección 36 — Regression Check).

Se optó por **añadir** `profile.read` y `playlists.read` como scopes nuevos,
válidos exclusivamente para el flujo ROPC/`legacy-client` y para el nuevo
endpoint `GET /api/playlists`, y se configuró el Servidor de Recursos
(`app/api/deps.py`) para tratarlos como **alias equivalentes** de
`profile:read` / `playlist:read` al momento de autorizar el acceso — el
claim `scope` del JWT conserva literalmente el valor solicitado (para que la
demostración ROPC coincida con el enunciado), pero un token emitido por
cualquiera de los dos flujos puede acceder a los mismos recursos si posee el
permiso equivalente. Esto evita duplicar la lógica de autorización y evita
que un token de Authorization Code+PKCE quede arbitrariamente bloqueado del
nuevo endpoint por una diferencia puramente léxica de nombres.

## Conclusión de la auditoría

El flujo B (Authorization Code + PKCE) **no requiere cambios funcionales**:
ya satisface every requisito explícito de la Sección 15–23 de Task 3. El
trabajo real de Task 3 es (1) añadir el flujo ROPC de forma acotada y
auditada, (2) añadir el endpoint de listado de playlists, y (3) documentar y
evidenciar ambos flujos con la nomenclatura A1-A3/B1-B5 exigida.
