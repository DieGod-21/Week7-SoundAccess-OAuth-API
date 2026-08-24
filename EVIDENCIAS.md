# EVIDENCIAS.md — SoundAccess (Semana 7 + Tarea 3)

Toda la evidencia listada aquí fue generada a partir de la aplicación **real en
ejecución** (`uvicorn app.main:app`), no a partir de inspección de código. Los
tokens, códigos y secretos se muestran truncados/redactados; ningún archivo de
esta carpeta contiene un token utilizable ni un secreto completo.

Las secciones 1–12 corresponden a la entrega original de la Semana 7
(Authorization Code + PKCE, Client Credentials — rama `main`, sin cambios). Las
secciones bajo "Tarea 3" más abajo son aditivas: cubren ROPC (Flujo A) y la
auditoría/comparación de Authorization Code + PKCE (Flujo B) en la rama
`task-3-ropc-pkce-comparison`.

Archivos fuente en `docs/evidence/`:

## 1. Clientes OAuth registrados

- `ev01_registered_clients.txt` — consulta directa a la base de datos: `web-user-client`
  (público, PKCE) y `music-service-client` (confidencial, secreto almacenado como hash
  Argon2id, no en texto plano).

## 2–4. Solicitud de autorización, consentimiento y canje del código (PKCE)

- `ev02_authorize_get.html` — HTML devuelto por `GET /oauth/authorize` (formulario de
  login + consentimiento con los scopes solicitados).
- `ev03_consent_redirect.txt` — respuesta `302` tras autorizar, con el `code` redactado.
- `ev04_token_exchange.txt` — respuesta `200` de `POST /oauth/token` (PKCE validado,
  access token redactado).
- `ev04b_token_claims_decoded.txt` — claims del JWT decodificados **sin exponer la
  firma** (`iss`, `sub`, `aud`, `exp`, `iat`, `jti`, `client_id`, `scope`).
- **Capturas de navegador real** (`docs/evidence/screenshots/`, generadas con Playwright
  contra la aplicación corriendo en `127.0.0.1:8000`):
  - `01_client_home.png` — pantalla inicial del cliente SoundAccess Web Player.
  - `02_authorize_login_consent.png` — página de login + consentimiento servida por el
    Servidor de Autorización.
  - `03_credentials_filled.png` — credenciales de demostración completadas.
  - `04_callback_token_exchanged.png` — callback tras el canje exitoso del código, con el
    JWT decodificado visible en la interfaz.

## 5. Token decodificado de forma segura

Ver `ev04b_token_claims_decoded.txt` y el panel 2 de `04_callback_token_exchanged.png`.
La firma se muestra truncada; el JWT completo nunca se expone en la documentación.

## 6. Respuesta exitosa 200

- `ev06a_catalog_200.json` — `GET /api/catalog/tracks` con token válido.
- `ev06b_me_200.json` — `GET /api/me` con token de usuario y scope `profile:read`.
- Capturas: `05_api_catalog_200.png`, `06_api_me_200.png`.

## 7. Token ausente/inválido → 401

- `ev05a_401_no_token.txt` — sin header `Authorization`.
- `ev05b_401_invalid_token.txt` — token malformado.
- Header `WWW-Authenticate: Bearer realm="soundaccess-api", error="invalid_token"`
  presente en ambos casos.

## 8. Scope insuficiente → 403

- `ev07_403_insufficient_scope.json` — token con `scope=catalog:read` solicitando
  `GET /api/me` (requiere `profile:read`).

## 9. Comportamiento de propiedad de playlists (ownership)

- `ev08a_playlist_created.json` — Ana crea una playlist (`201`).
- `ev08b_cross_user_read.json` — Bruno intenta leer la playlist de Ana → `404` (sin fuga
  de datos: el cuerpo no contiene el nombre ni la descripción de la playlist).
- `ev08c_cross_user_delete.json` — Bruno intenta eliminarla → `404`.
- `ev08d_owner_confirms_intact.json` — Ana confirma que su playlist sigue intacta (`200`).
- Capturas: `07_api_playlist_created_201.png`, `08_api_playlist_read_200.png`.

## 10. Client Credentials (cliente de servicio)

- `ev09a_client_credentials_token.txt` — `music-service-client` obtiene un token con
  `scope=catalog:read`.
- `ev09b_client_credentials_catalog_200.json` — el token de servicio accede al catálogo.
- `ev09c_client_credentials_me_403.json` — el mismo token, válido, es **rechazado con 403**
  al pedir `/api/me` (token de máquina, no de usuario — demuestra la distinción entre
  autenticación y autorización).

## 11. Swagger / OpenAPI

- `ev11_openapi.json` — especificación OpenAPI generada por la aplicación en ejecución
  (7 rutas documentadas, seguridad `BearerJWT`, respuestas 401/403 documentadas).
- Captura: `09_swagger_ui.png` — Swagger UI renderizada (auto-hospedada, sin CDN).

## 12. Resultados de pruebas automatizadas

- `ev10_pytest_results.txt` — 38/38 pruebas pasando (Semana 7 / Task 1), incluyendo los 6
  escenarios obligatorios y las pruebas de endurecimiento de seguridad adicionales.
- `ev_t3_pytest_full_results.txt` — **55/55 pruebas pasando** tras la Tarea 3 (las 38
  originales + 17 nuevas: 2 reescritas en `test_security.py` §"ROPC rejected..." + 16 en
  `test_task3_ropc_pkce.py`), confirmando cero regresiones (§19 más abajo tiene el detalle
  antes/después).

---

# Tarea 3 — ROPC y comparación de flujos (rama `task-3-ropc-pkce-comparison`)

Toda la evidencia de esta sección proviene también de la aplicación **real en ejecución**
(`uvicorn app.main:app`, misma base de datos de desarrollo sembrada por
`scripts/init_db.py`), generada por `scripts/capture_task3_evidence.py` (peticiones HTTP
reales vía `requests`) y `scripts/capture_task3_browser_evidence.py` (navegador real vía
Playwright, solo para B5). Archivos fuente en `docs/evidence/` (prefijo `ev_t3_`).

## Tarea 3 — Flujo A: ROPC (Resource Owner Password Credentials)

### A1 — Solicitud ROPC válida

- `ev_t3_a1_ropc_request_response.txt` — `POST /oauth/token` con `grant_type=password` para
  `alumno.demo`/`legacy-client` → `200`, JWT emitido (access token redactado; contraseña y
  client_secret redactados en la petición mostrada).
- `ev_t3_a1_token_claims_decoded.txt` — claims decodificados: `iss`, `sub` (id de
  `alumno.demo`, distinto de `client_id`), `aud`, `exp`, `iat`, `jti`, `client_id`, `scope`.
- `ev_t3_a1_protected_resources_200.txt` — el mismo token funciona contra `GET /api/me`
  (`200`, perfil de `alumno.demo`) y `GET /api/playlists` (`200`, solo su playlist "Legacy
  Mix").

### A2 — Credenciales o cliente inválidos

- `ev_t3_a2_invalid_credentials_or_client.txt` — cinco casos reales contra el servidor en
  ejecución:
  - contraseña incorrecta → `400 invalid_grant`;
  - usuario inexistente → `400 invalid_grant`, **mismo `error_description`** que el caso
    anterior (verificado explícitamente en el archivo — no hay enumeración de usuarios);
  - `client_secret` incorrecto → `401 invalid_client`;
  - cliente autenticado pero sin `password` en sus grants permitidos
    (`music-service-client`) → `400 unauthorized_client`;
  - campos faltantes → `400 invalid_request`.

### A3 — Fallos del recurso protegido

- `ev_t3_a3_protected_resource_failures.txt` — cuatro casos reales:
  - sin header `Authorization` → `401 invalid_token`;
  - token expirado (forjado con `exp` en el pasado, misma clave real del servidor) →
    `401 invalid_token`;
  - firma alterada (últimos 4 caracteres de la firma reemplazados) → `401 invalid_token`;
  - scope insuficiente (token emitido solo con `playlists.read`, solicitando `/api/me`) →
    `403 insufficient_scope`; el **mismo token** sí funciona contra `/api/playlists`
    (`200`), confirmando que el rechazo es de autorización, no de autenticación.

## Tarea 3 — Flujo B: Authorization Code + PKCE (auditado, sin cambios funcionales)

### B1 — Flujo completo válido

- `ev_t3_b1_pkce_valid_flow.txt` — login, consentimiento, validación de client/scope/state,
  canje del código, y **el nuevo** `GET /api/playlists` (Tarea 3) devolviendo únicamente las
  playlists de `ana`, junto con `GET /api/me` (`200`).

### B2 — `redirect_uri` no registrado

- `ev_t3_b2_invalid_redirect_uri.txt` — `GET /oauth/authorize` con
  `redirect_uri=https://attacker.example.com/steal` → `400`, sin header `location` (nunca
  redirige a un URI no registrado).

### B3 — `code_verifier` incorrecto

- `ev_t3_b3_invalid_code_verifier.txt` — canje con un `code_verifier` que no corresponde al
  `code_challenge` original → `400 invalid_grant`.

### B4 — Reutilización del código de autorización

- `ev_t3_b4_authorization_code_reuse.txt` — primer canje `200`; segundo canje del **mismo**
  código → `400 invalid_grant`.

### B5 — Discrepancia de `state`

- `ev_t3_b5_server_state_echo.txt` — evidencia de servidor: al enviar un `state` con
  caracteres especiales, el `302` de vuelta lo devuelve **exactamente igual**, sin alterar
  (mecanismo que hace significativa la comparación del lado del cliente).
- `ev_t3_b5_browser_state_mismatch_abort.txt` + captura
  `screenshots/10_b5_state_mismatch_abort.png` — **evidencia de navegador real** (Playwright
  sobre Chromium): se completó un login+consentimiento genuino como `ana`; se interceptó la
  redirección real del servidor (sin dejar que el navegador la siguiera) para leer el
  `code`+`state` correctos de esa sesión; se sustituyó **únicamente** el parámetro `state`
  por un valor forjado y se navegó al callback resultante en el **mismo** navegador (misma
  `sessionStorage`, mismo `pkce_verifier` guardado). Resultado observado en la interfaz real:
  *"state inválido (posible CSRF). Flujo abortado."* — y el registro de peticiones de red de
  esa navegación confirma **cero** llamadas a `/oauth/token`: el guard del lado del cliente
  (`frontend/callback.html`, `state !== savedState`) aborta el flujo antes de cualquier
  intento de canje. El `code` se redacta en el archivo de evidencia (nunca se llegó a
  canjear, y de todas formas expira a los 60s).

## Tarea 3 — Swagger / OpenAPI actualizado

- `screenshots/11_swagger_ui_task3_playlists.png` — descripción de la API actualizada,
  mencionando explícitamente ROPC como flujo de comparación gateado a `legacy-client`.
- `screenshots/12_swagger_ui_full_task3.png` — lista completa de endpoints, incluyendo el
  nuevo `GET /api/playlists` ("List the authenticated user's playlists (scope:
  playlist:read; Task 3)").
- `ev_t3_openapi.json` — especificación OpenAPI regenerada desde la aplicación en ejecución:
  7 rutas (mismas que Task 1; `/api/playlists` ahora agrupa GET+POST).

## Tarea 3 — Matriz de evidencia y requisitos

| Requisito | Ubicación en código | Prueba automatizada | Evidencia real | Estado |
|---|---|---|---|---|
| A1 — ROPC válido → 200, JWT correcto, scopes correctos | `app/oauth/router.py::_grant_ropc` | `test_task3_ropc_pkce.py::TestTask3RopcA1ValidRequest` | `ev_t3_a1_*` | PASS |
| A2 — credenciales inválidas → `invalid_grant`, sin enumeración de usuarios | `_grant_ropc` (mismo error para user/pw) | `TestTask3RopcA2InvalidCredentialsOrClient` (5 casos) | `ev_t3_a2_invalid_credentials_or_client.txt` | PASS |
| A2 — cliente no autorizado / no autenticado → `unauthorized_client` / `invalid_client` | `_grant_ropc` | `TestTask3RopcA2...`, `test_security.py::test_ropc_rejected_*` | `ev_t3_a2_invalid_credentials_or_client.txt` | PASS |
| A3 — token ausente/expirado/alterado → 401 | `app/security.py::decode_access_token` | `TestTask3RopcA3ProtectedResourceFailures` | `ev_t3_a3_protected_resource_failures.txt` | PASS |
| A3 — scope insuficiente → 403, mismo token funciona con el scope correcto | `app/api/deps.py::require_scopes` + `SCOPE_ALIASES` | `TestTask3RopcA3ProtectedResourceFailures::test_a3_insufficient_scope_is_403` | `ev_t3_a3_protected_resource_failures.txt` | PASS |
| B1 — flujo PKCE completo, incluye `GET /api/playlists` nuevo | `app/oauth/router.py`, `app/api/router.py::list_playlists` | `TestTask3PkceB1ValidFlow` | `ev_t3_b1_pkce_valid_flow.txt` | PASS |
| B2 — `redirect_uri` no registrado → 400, nunca redirige | `app/oauth/router.py::_validate_authorize_request` | `TestTask3PkceB2InvalidRedirect` | `ev_t3_b2_invalid_redirect_uri.txt` | PASS |
| B3 — `code_verifier` incorrecto → 400 `invalid_grant` | `app/security.py::pkce_verify` | `TestTask3PkceB3InvalidVerifier` | `ev_t3_b3_invalid_code_verifier.txt` | PASS |
| B4 — reutilización del código → 400 `invalid_grant` | `app/models.py::AuthorizationCode.used` | `TestTask3PkceB4CodeReuse` | `ev_t3_b4_authorization_code_reuse.txt` | PASS |
| B5 — `state` se devuelve intacto (servidor) | `app/oauth/router.py::authorize_post` | `TestTask3PkceB5StateMismatch::test_b5_server_echoes_state_unaltered` | `ev_t3_b5_server_state_echo.txt` | PASS |
| B5 — el cliente aborta ante `state` no coincidente, antes de canjear el código | `frontend/callback.html` (`state !== savedState`) | `TestTask3PkceB5StateMismatch::test_b5_client_side_mismatch_guard_present_and_precedes_token_exchange` (contrato de código) | `ev_t3_b5_browser_state_mismatch_abort.txt` + `screenshots/10_b5_state_mismatch_abort.png` (navegador real) | PASS |

Ninguna fila se marca PASS sin que existan a la vez implementación, prueba automatizada y
evidencia real verificable en `docs/evidence/`.

---

### Nota sobre redacción de secretos

Ningún archivo de evidencia (Semana 7 o Tarea 3) contiene: contraseñas en texto plano,
secretos de cliente completos, códigos de autorización completos, ni un `access_token`
completo. Los valores sensibles se truncan a un prefijo/sufijo corto (o se sustituyen por
`<REDACTED>`/`<redacted>`) suficiente para verificar que la operación ocurrió, sin permitir
su reuso.
