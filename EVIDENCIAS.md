# EVIDENCIAS.md — SoundAccess (Semana 7)

Toda la evidencia listada aquí fue generada a partir de la aplicación **real en
ejecución** (`uvicorn app.main:app`), no a partir de inspección de código. Los
tokens, códigos y secretos se muestran truncados/redactados; ningún archivo de
esta carpeta contiene un token utilizable ni un secreto completo.

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

- `ev10_pytest_results.txt` — **38/38 pruebas pasando**, incluyendo los 6 escenarios
  obligatorios y las pruebas de endurecimiento de seguridad adicionales.

---

### Nota sobre redacción de secretos

Ningún archivo de evidencia contiene: contraseñas en texto plano, secretos de cliente
completos, ni un `access_token` completo. Los valores sensibles se truncan a un prefijo/
sufijo corto suficiente para verificar que la operación ocurrió, sin permitir su reuso.
