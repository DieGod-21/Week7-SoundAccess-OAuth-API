# Análisis comparativo: ROPC vs. Authorization Code + PKCE

*SoundAccess — Tarea 3 (comparación de flujos OAuth 2.0)*

Implementar ambos flujos sobre la misma base de código permite compararlos no
en abstracto, sino observando qué cambia realmente en el manejo de
credenciales, en la superficie de ataque y en el grado de control que el
Servidor de Autorización conserva sobre el proceso de login.

La diferencia más evidente es la exposición de la contraseña. En ROPC
(`grant_type=password`), el cliente recibe la contraseña del usuario en texto
plano y la reenvía dentro del cuerpo de `POST /oauth/token`; aunque en
SoundAccess esa contraseña se descarta de inmediato tras `verify_secret()` y
nunca se registra en logs, el cliente sigue siendo, por diseño, un punto por
el que la credencial real pasa. En Authorization Code + PKCE, en cambio, la
contraseña nunca llega al cliente: el usuario se autentica directamente en el
formulario del Servidor de Autorización, y lo único que el cliente maneja es
un `code_verifier` efímero, inútil sin el `authorization_code` correspondiente
y sin el `code_challenge` original.

Esa separación tiene consecuencias prácticas más allá de la exposición
puntual. Al no existir una pantalla de login propia en el flujo ROPC,
tampoco hay dónde insertar un segundo factor de autenticación o un
proveedor de identidad externo sin romper el contrato del cliente; MFA y
login federado son, en la práctica, incompatibles con ROPC. El consentimiento
también desaparece: el usuario entrega sus credenciales confiando
ciegamente en que el cliente solicitará solo los scopes que dice necesitar,
mientras que PKCE conserva una pantalla explícita de autorización por scope.
Frente a CSRF, PKCE se apoya en la verificación de `state` del lado del
cliente —presente y verificada antes de cualquier canje de código en
`frontend/callback.html`—, mientras que ROPC no tiene un mecanismo
equivalente porque no hay redirección que proteger. Y frente a la
intercepción del `authorization_code`, el propio PKCE es la mitigación: sin
el `code_verifier` original, un código interceptado no puede canjearse.

Por estas razones, y en línea con RFC 9700 §2.4, ROPC se mantiene en este
proyecto exclusivamente como referencia legacy, gateada a un único cliente de
laboratorio. Para cualquier integración nueva, Authorization Code + PKCE es
el flujo recomendado.
