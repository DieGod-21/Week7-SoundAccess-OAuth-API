// Genera el informe académico de la Semana 7 (SoundAccess — OAuth 2.0 + JWT).
// Estilo restringido/académico: tipografía serif, títulos oscuros (no azules),
// sin banners decorativos, tablas simples, numeración de página.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType,
  Header, Footer, PageNumber, PageBreak, ImageRun, TableOfContents,
  ExternalHyperlink, convertInchesToTwip, VerticalAlign, LevelFormat,
  PositionalTab, PositionalTabAlignment, PositionalTabLeader, TabStopType, TabStopPosition,
} = require("docx");

const ROOT = path.resolve(__dirname, "..", "..");
const DIAG = path.join(ROOT, "docs", "diagrams");

const INK = "1F2430";
const MUTED = "5B6472";
const RULE = "C9CDD3";
const FONT = "Georgia";

const PAGE = { width: 12240, height: 15840 }; // US Letter (DXA)
const MARGIN = convertInchesToTwip(1);

// ---------------------------------------------------------------- helpers --
function para(text, opts = {}) {
  const { bold, italics, size = 22, color = INK, align, spacingAfter = 160, spacingBefore = 0 } = opts;
  return new Paragraph({
    alignment: align,
    spacing: { after: spacingAfter, before: spacingBefore, line: 300 },
    children: [new TextRun({ text, bold, italics, size, color, font: FONT })],
  });
}

function multi(runs, opts = {}) {
  // runs: [{text, bold, italics, color}]
  const { spacingAfter = 160, align } = opts;
  return new Paragraph({
    alignment: align,
    spacing: { after: spacingAfter, line: 300 },
    children: runs.map(r => new TextRun({ size: 22, font: FONT, color: INK, ...r })),
  });
}

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 420, after: 200 },
    border: { bottom: { color: RULE, space: 6, style: BorderStyle.SINGLE, size: 6 } },
    children: [new TextRun({ text, bold: true, size: 30, color: INK, font: FONT })],
  });
}

function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 300, after: 140 },
    children: [new TextRun({ text, bold: true, size: 25, color: INK, font: FONT })],
  });
}

function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 220, after: 100 },
    children: [new TextRun({ text, bold: true, italics: true, size: 23, color: INK, font: FONT })],
  });
}

function bullet(text, level = 0) {
  return new Paragraph({
    numbering: { reference: "report-bullets", level },
    spacing: { after: 100, line: 280 },
    children: [new TextRun({ text, size: 22, color: INK, font: FONT })],
  });
}

function numbered(text, level = 0) {
  return new Paragraph({
    numbering: { reference: "report-numbers", level },
    spacing: { after: 100, line: 280 },
    children: [new TextRun({ text, size: 22, color: INK, font: FONT })],
  });
}

function codeLine(text) {
  return new Paragraph({
    spacing: { after: 40 },
    shading: { type: ShadingType.CLEAR, fill: "F1F2F4" },
    children: [new TextRun({ text, size: 19, font: "Consolas", color: "2B3240" })],
  });
}

function caption(text) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 80, after: 260 },
    children: [new TextRun({ text, italics: true, size: 19, color: MUTED, font: FONT })],
  });
}

function image(file, widthPx, heightPx) {
  const data = fs.readFileSync(path.join(DIAG, file));
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 160, after: 40 },
    children: [new ImageRun({ type: "png", data, transformation: { width: widthPx, height: heightPx } })],
  });
}

function simpleTable(headerRow, rows, colWidthsDXA) {
  const totalWidth = colWidthsDXA.reduce((a, b) => a + b, 0);
  const mkCell = (text, { header = false, width } = {}) => new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: header ? { type: ShadingType.CLEAR, fill: "EFEFEF" } : undefined,
    verticalAlign: VerticalAlign.CENTER,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({
      spacing: { after: 0, line: 260 },
      children: [new TextRun({ text, bold: header, size: 19, color: INK, font: FONT })],
    })],
  });
  return new Table({
    width: { size: totalWidth, type: WidthType.DXA },
    columnWidths: colWidthsDXA,
    rows: [
      new TableRow({ tableHeader: true, children: headerRow.map((t, i) => mkCell(t, { header: true, width: colWidthsDXA[i] })) }),
      ...rows.map(r => new TableRow({ children: r.map((t, i) => mkCell(t, { width: colWidthsDXA[i] })) })),
    ],
  });
}

const pageBreak = () => new Paragraph({ children: [new PageBreak()] });

// Tabla de contenido estática (con líder de puntos), con números de página
// verificados contra la paginación real del documento renderizado. Se usa en
// vez de un campo TableOfContents dinámico porque el flujo de conversión
// headless de LibreOffice usado para verificar el PDF no recalcula ese campo
// de forma fiable; en Word, con updateFields:true, un campo dinámico también
// se habría actualizado solo, pero esta tabla estática es exacta en ambos.
function tocEntry(text, pageNum, { indent = 0, bold = false } = {}) {
  return new Paragraph({
    spacing: { after: 70, line: 260 },
    indent: { left: indent },
    tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX, leader: "dot" }],
    children: [
      new TextRun({ text, bold, size: 21, color: INK, font: FONT }),
      new TextRun({ children: [
        new PositionalTab({ alignment: PositionalTabAlignment.RIGHT, leader: PositionalTabLeader.DOT, relativeTo: "margin" }),
      ], size: 21, color: INK, font: FONT }),
      new TextRun({ text: String(pageNum), size: 21, color: INK, font: FONT }),
    ],
  });
}

const TOC_ENTRIES = [
  ["1. Introducción", 3],
  ["2. Objetivos", 3],
  ["2.1 Objetivo general", 3, 260],
  ["2.2 Objetivos específicos", 3, 260],
  ["3. Marco conceptual", 4],
  ["4. Desarrollo de la actividad", 5],
  ["5. Arquitectura del sistema", 5],
  ["6. Diseño de la base de datos", 6],
  ["7. Implementación de OAuth 2.0", 7],
  ["8. Authorization Code + PKCE", 7],
  ["9. Client Credentials", 8],
  ["10. Implementación de JWT", 9],
  ["11. Scopes y autorización", 9],
  ["12. Recursos protegidos", 9],
  ["13. Pruebas y resultados", 10],
  ["14. Controles de seguridad", 11],
  ["15. Problemas encontrados y soluciones", 11],
  ["16. Conclusiones", 12],
  ["17. Recomendaciones", 12],
  ["18. Referencias", 13],
  ["19. Apéndices", 13],
  ["19.1 Matriz de requisitos, evidencia y estado", 13, 260],
  ["19.2 Diagramas fuente", 14, 260],
];

// ------------------------------------------------------------- cover page --
const coverChildren = [
  new Paragraph({ spacing: { before: 1800, after: 0 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "UNIVERSIDAD", size: 20, color: MUTED, font: FONT, characterSpacing: 20 })] }),
  new Paragraph({ spacing: { before: 40, after: 900 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "[PENDING: NOMBRE DE LA UNIVERSIDAD]", size: 20, color: MUTED, font: FONT })] }),

  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
    children: [new TextRun({ text: "Aseguramiento de una API de Música", bold: true, size: 40, color: INK, font: FONT })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 500 },
    children: [new TextRun({ text: "mediante OAuth 2.0 y JSON Web Tokens: el caso SoundAccess", bold: true, size: 32, color: INK, font: FONT })] }),

  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 },
    children: [new TextRun({ text: "Informe académico — Semana 7", size: 24, italics: true, color: MUTED, font: FONT })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 1400 },
    children: [new TextRun({ text: "Autenticación y Autorización con OAuth 2.0 / JWT", size: 24, italics: true, color: MUTED, font: FONT })] }),

  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 },
    children: [new TextRun({ text: "Presentado por", size: 20, color: MUTED, font: FONT })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 320 },
    children: [new TextRun({ text: "[PENDING: FULL NAME]", bold: true, size: 26, color: INK, font: FONT })] }),

  simpleTableCentered(),

  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 1000, after: 0 },
    children: [new TextRun({ text: "Guatemala, " + new Date().toLocaleDateString("es-GT", { year: "numeric", month: "long" }), size: 20, color: MUTED, font: FONT })] }),
];

function simpleTableCentered() {
  const rows = [
    ["Carné / ID de estudiante", "[PENDING: STUDENT ID]"],
    ["Sede / Sección", "[PENDING: CAMPUS / SECTION]"],
    ["Tecnología principal", "Python · FastAPI · SQLAlchemy · SQLite · PyJWT · Argon2"],
    ["Repositorio", "[PENDING: REPOSITORY URL]"],
  ];
  return new Table({
    alignment: AlignmentType.CENTER,
    width: { size: 7200, type: WidthType.DXA },
    columnWidths: [2800, 4400],
    borders: {
      top: { style: BorderStyle.NONE }, bottom: { style: BorderStyle.NONE },
      left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: RULE },
      insideVertical: { style: BorderStyle.NONE },
    },
    rows: rows.map(([k, v]) => new TableRow({
      children: [
        new TableCell({ width: { size: 2800, type: WidthType.DXA }, margins: { top: 80, bottom: 80, left: 60, right: 60 },
          children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: k, size: 19, color: MUTED, font: FONT })] })] }),
        new TableCell({ width: { size: 4400, type: WidthType.DXA }, margins: { top: 80, bottom: 80, left: 200, right: 60 },
          children: [new Paragraph({ children: [new TextRun({ text: v, size: 19, bold: true, color: INK, font: FONT })] })] }),
      ],
    })),
  });
}

// ------------------------------------------------------------ main content --
const body = [];

body.push(h1("1. Introducción"));
body.push(para(
  "Los servicios de streaming e integraciones musicales modernas rara vez exponen la contraseña de un usuario a las aplicaciones de terceros; en su lugar delegan el acceso mediante un protocolo de autorización. Este informe documenta el diseño, la implementación y la verificación de SoundAccess, una API de catálogo musical construida como práctica académica para aplicar OAuth 2.0 (RFC 6749) y JSON Web Tokens (RFC 7519) en un escenario realista: un cliente de usuario que necesita leer y escribir playlists en nombre de una persona, y un cliente de servicio que sincroniza el catálogo sin intervención humana."
));
body.push(para(
  "El proyecto no es una simulación superficial de OAuth: implementa un servidor de autorización que emite y valida tokens firmados, un servidor de recursos que aplica scopes por endpoint y verifica la propiedad de los recursos, y un cliente de demostración que ejecuta el flujo completo — incluido PKCE — desde el navegador. Todo el desarrollo se realizó con Claude Code como herramienta principal de ingeniería (creación de archivos, pruebas, depuración y control de versiones), bajo la orquestación de Claude Cowork."
));

body.push(h1("2. Objetivos"));
body.push(h2("2.1 Objetivo general"));
body.push(para("Diseñar, implementar y verificar una API de música protegida mediante OAuth 2.0 y JWT, demostrando de forma práctica la diferencia entre autenticación y autorización en un sistema con múltiples tipos de cliente."));
body.push(h2("2.2 Objetivos específicos"));
[
  "Implementar el flujo Authorization Code con PKCE (S256) para un cliente público de usuario final.",
  "Implementar el flujo Client Credentials para un cliente de servicio (machine-to-machine).",
  "Emitir y validar JSON Web Tokens con los claims exigidos por RFC 9068, rechazando algoritmos inseguros.",
  "Aplicar autorización basada en scopes a nivel de Servidor de Recursos, no solo declararla en el token.",
  "Garantizar el aislamiento de recursos entre usuarios (una playlist privada no es accesible por otro usuario, con un token válido).",
  "Cubrir los seis escenarios obligatorios y casos adicionales de endurecimiento con pruebas automatizadas.",
  "Producir documentación técnica, diagramas editables y evidencia real de ejecución.",
].forEach(t => body.push(numbered(t)));

body.push(h1("3. Marco conceptual"));
body.push(para(
  "OAuth 2.0 (RFC 6749) define cuatro roles: el propietario del recurso (resource owner, típicamente una persona), el cliente (client, la aplicación que solicita acceso), el servidor de autorización (authorization server, que autentica y emite tokens) y el servidor de recursos (resource server, que expone la API protegida). El protocolo no transporta contraseñas hacia el cliente: en su lugar, el cliente obtiene un token de acceso de vida corta con un alcance (scope) delimitado."
));
body.push(para(
  "El flujo Authorization Code es el recomendado para clientes que interactúan con un usuario a través de un navegador. Cuando el cliente es público — es decir, no puede guardar un secreto de forma confidencial, como una aplicación web servida al navegador — RFC 7636 introduce PKCE (Proof Key for Code Exchange): el cliente genera un valor aleatorio (code_verifier), deriva un code_challenge = BASE64URL(SHA-256(code_verifier)) y lo envía en la solicitud de autorización; al canjear el código, debe volver a presentar el code_verifier original, que el servidor recalcula y compara. Esto evita que un atacante que intercepte el código de autorización pueda canjearlo sin conocer también el verifier."
));
body.push(para(
  "El flujo Client Credentials (RFC 6749 §4.4) es apropiado para comunicación servicio-a-servicio, sin un usuario presente: el cliente se autentica directamente con su client_id y client_secret y recibe un token que representa al propio cliente, no a una persona."
));
body.push(para(
  "Un JSON Web Token (RFC 7519) es una estructura firmada (en este proyecto, HMAC-SHA256) que transporta claims — pares clave/valor — de forma verificable. RFC 9068 estandariza el perfil de JWT para tokens de acceso de OAuth 2.0, especificando claims como iss (emisor), sub (sujeto), aud (audiencia), exp (expiración), iat (emisión) y client_id. RFC 9700 recopila las mejores prácticas de seguridad vigentes para OAuth 2.0, incluyendo la recomendación de exigir PKCE también en clientes confidenciales y evitar el grant de Resource Owner Password Credentials (ROPC), que expone la contraseña del usuario directamente al cliente."
));
body.push(para(
  "Un punto conceptual central del proyecto es la distinción entre autenticación y autorización: autenticar responde «quién eres» (¿la firma del token es válida?, ¿el emisor y la audiencia son correctos?), mientras que autorizar responde «qué puedes hacer» (¿el token incluye el scope necesario?, ¿el recurso solicitado te pertenece?). Un token perfectamente válido puede, aun así, ser insuficiente para una operación concreta."
));

body.push(h1("4. Desarrollo de la actividad"));
body.push(para(
  "El trabajo se organizó en fases incrementales, cada una cerrada con una batería de verificación antes de avanzar a la siguiente, y con commits de Git independientes por fase (ver Sección 15 y el historial real del repositorio)."
));
[
  "Reconocimiento del entorno: se confirmó la disponibilidad de Python 3.11, Node.js, Git, un navegador Chromium preinstalado y las herramientas de prueba; se protegió el directorio Documents del usuario creando un directorio de proyecto dedicado (Week7_SoundAccess_OAuth_API) sin tocar archivos preexistentes.",
  "Fundamento del proyecto: inicialización de Git, entorno Python, dependencias (FastAPI, SQLAlchemy, PyJWT, argon2-cffi, pytest) y gestión de configuración mediante variables de entorno (.env, nunca comprometido a Git).",
  "Base de datos: modelado de las seis entidades requeridas, hashing de contraseñas y secretos con Argon2id, y un script de siembra idempotente con dos usuarios, dos clientes OAuth y datos ficticios de catálogo.",
  "Identidad y OAuth: registro controlado de clientes, endpoint de autorización con validación estricta de redirect_uri, y los flujos Authorization Code + PKCE y Client Credentials.",
  "JWT y API de recursos: emisión y validación de tokens, dependencias de FastAPI para exigir scopes, y los cinco endpoints protegidos mínimos.",
  "Cliente de demostración: interfaz mínima en HTML/JS que ejecuta PKCE en el navegador (generación de code_verifier, cálculo SHA-256 vía Web Crypto API) y consume la API con el token obtenido.",
  "Pruebas automatizadas: 38 pruebas con pytest, incluidos los seis escenarios obligatorios y pruebas de endurecimiento adicionales.",
  "Documentación y evidencia: diagramas Mermaid editables, captura de evidencia real (peticiones HTTP reales y automatización de navegador con Playwright), README técnico y este informe.",
  "Endurecimiento y verificación final: auditoría de seguridad dirigida, verificación contra la rúbrica y prueba de reproducibilidad desde cero.",
].forEach(t => body.push(numbered(t)));

body.push(h1("5. Arquitectura del sistema"));
body.push(para(
  "El sistema separa tres roles lógicos: el Cliente OAuth (SoundAccess Web Player, servido desde frontend/), el Servidor de Autorización (app/oauth) y el Servidor de Recursos (app/api), además de la base de datos compartida. Por simplicidad de despliegue local, los tres componentes se ejecutan dentro de un mismo proceso FastAPI, pero cada uno vive en un módulo independiente con sus propias dependencias y responsabilidades — el Servidor de Recursos, por ejemplo, no conoce el mecanismo de login; solo valida el JWT que recibe."
));
body.push(image("component_diagram.png", 560, 207));
body.push(caption("Figura 1. Diagrama de componentes (fuente editable en docs/diagrams/component_diagram.mmd)."));

body.push(h1("6. Diseño de la base de datos"));
body.push(para("Se definieron seis entidades con SQLAlchemy 2.0, usando SQLite para el desarrollo local (persistencia real, no una base de datos en memoria) manteniendo la capa de acceso lo suficientemente abstracta para migrar a otro motor relacional si fuera necesario."));
body.push(simpleTable(
  ["Entidad", "Propósito", "Notas de seguridad"],
  [
    ["users", "Usuarios finales de la aplicación", "password_hash con Argon2id; nunca texto plano"],
    ["oauth_clients", "Clientes OAuth registrados", "client_secret_hash (Argon2id) o NULL en clientes públicos"],
    ["authorization_codes", "Códigos de autorización emitidos", "Se guarda solo el hash SHA-256 del código; un solo uso; expira en 60s"],
    ["tracks", "Catálogo musical ficticio", "Sin datos con derechos de autor de terceros"],
    ["playlists", "Playlists de un usuario", "Ligada a owner_id; consultada siempre filtrando por dueño"],
    ["playlist_items", "Canciones dentro de una playlist", "Restricción de unicidad (playlist_id, position)"],
  ],
  [2200, 3600, 3200],
));
body.push(caption("Tabla 1. Entidades principales del modelo de datos."));

body.push(h1("7. Implementación de OAuth 2.0"));
body.push(para(
  "El registro de clientes (POST /oauth/clients) es controlado: exige un header X-Registration-Key con una clave administrativa definida por variable de entorno; no existe una ruta pública que permita crear clientes privilegiados sin autenticación. Se sembraron dos clientes de demostración: web-user-client (público, sin secreto, obligado a usar PKCE) y music-service-client (confidencial, con secreto almacenado como hash Argon2id, restringido al scope catalog:read)."
));
body.push(para(
  "El endpoint de autorización (GET/POST /oauth/authorize) valida el client_id y compara el redirect_uri contra la lista blanca registrada mediante coincidencia exacta de cadena. Si el cliente o el redirect_uri no son válidos, el servidor no redirige — renderiza una página de error local — precisamente para no convertirse en un mecanismo de redirección abierta (open redirect) que un atacante pudiera aprovechar."
));

body.push(h1("8. Authorization Code + PKCE"));
body.push(para("El flujo completo, tal como se implementó y se verificó con Playwright contra la aplicación en ejecución real:"));
body.push(image("auth-code-pkce.png", 520, 512));
body.push(caption("Figura 2. Secuencia completa Authorization Code + PKCE (fuente editable en docs/diagrams/auth-code-pkce.mmd)."));
body.push(para(
  "El código de autorización se almacena únicamente como su hash SHA-256 (nunca en texto plano), tiene una vida de 60 segundos, está ligado al cliente, al usuario, al redirect_uri exacto y al code_challenge, y se marca como usado antes de emitir el token — de modo que un intento de reutilización (replay) es rechazado con invalid_grant. El método code_challenge_method=plain es explícitamente rechazado; solo se acepta S256."
));

body.push(h1("9. Client Credentials"));
body.push(para(
  "El cliente de servicio se autentica con client_id y client_secret; el servidor verifica el secreto contra el hash Argon2id almacenado y valida que el scope solicitado esté dentro de lo permitido para ese cliente. El token resultante tiene sub == client_id (representa al cliente, no a una persona) y, aunque es un token válido, es rechazado con 403 al solicitar /api/me o cualquier playlist privada — la aplicación demuestra explícitamente que autenticación válida no implica acceso ilimitado."
));

body.push(h1("10. Implementación de JWT"));
body.push(para(
  "Los tokens de acceso incluyen los claims iss, sub, aud, exp, iat, jti, client_id y scope. La validación (PyJWT) fija explícitamente el algoritmo permitido mediante el parámetro algorithms=[...], lo que hace que un token con alg=none o con un algoritmo distinto al configurado sea rechazado antes de cualquier verificación de firma — la biblioteca nunca infiere el algoritmo a partir del propio token. Se validan además issuer, audience, expiración, emisión y la presencia de todos los claims requeridos. Los tokens tienen una vida de 15 minutos y solo se aceptan en el header Authorization: Bearer, nunca en la URL."
));

body.push(h1("11. Scopes y autorización"));
body.push(simpleTable(
  ["Scope", "Efecto"],
  [
    ["catalog:read", "Leer el catálogo público de canciones"],
    ["profile:read", "Leer el perfil del usuario autenticado (solo tokens de usuario)"],
    ["playlist:read", "Leer las playlists propias"],
    ["playlist:write", "Crear y eliminar playlists propias"],
  ],
  [2600, 6400],
));
body.push(caption("Tabla 2. Scopes definidos y su efecto."));
body.push(para("Los scopes se comprueban en el Servidor de Recursos mediante una dependencia de FastAPI (require_scopes) aplicada a cada endpoint; no se limitan a figurar en el token."));

body.push(h1("12. Recursos protegidos"));
body.push(simpleTable(
  ["Método", "Ruta", "Scope", "Comportamiento"],
  [
    ["GET", "/api/catalog/tracks", "catalog:read", "Lista el catálogo ficticio"],
    ["GET", "/api/me", "profile:read", "Perfil del usuario (rechaza tokens de servicio)"],
    ["POST", "/api/playlists", "playlist:write", "Crea una playlist del usuario autenticado"],
    ["GET", "/api/playlists/{id}", "playlist:read", "Solo si el usuario es el dueño"],
    ["DELETE", "/api/playlists/{id}", "playlist:write", "Solo si el usuario es el dueño"],
  ],
  [1200, 2800, 2000, 3000],
));
body.push(caption("Tabla 3. Endpoints protegidos mínimos."));
body.push(para(
  "Semántica de errores: 401 cuando la solicitud no pudo autenticarse (token ausente, malformado, firma inválida, expirado, issuer o audience incorrectos); 403 cuando el token es válido pero el sujeto no está autorizado (scope faltante, o un token de servicio sobre un recurso personal); 404 — en vez de 403 — para una playlist ajena, de modo que la respuesta no revele si el recurso existe."
));

body.push(h1("13. Pruebas y resultados"));
body.push(para(
  "Se implementaron 38 pruebas automatizadas con pytest y el TestClient de FastAPI (tests/test_scenarios.py y tests/test_security.py), ejecutadas contra una base de datos SQLite aislada y credenciales sintéticas generadas para la sesión de pruebas. Las 38 pruebas pasan de forma consistente (ver docs/evidence/ev10_pytest_results.txt)."
));
body.push(simpleTable(
  ["Escenario obligatorio", "Resultado"],
  [
    ["1. Authorization Code + PKCE completo", "200 en cada paso, token emitido y consumido"],
    ["2. Client Credentials", "Token emitido; acceso limitado al scope permitido"],
    ["3. Solicitud protegida sin token", "401 en los cinco endpoints protegidos"],
    ["4. Token inválido / expirado / issuer o audience erróneos", "401 en todos los casos"],
    ["5. Token válido sin el scope requerido", "403 insufficient_scope"],
    ["6. Acceso de un usuario a la playlist de otro", "404, sin fuga de datos privados"],
  ],
  [4400, 3600],
));
body.push(caption("Tabla 4. Resultado de los seis escenarios obligatorios."));
body.push(para(
  "Las pruebas adicionales de endurecimiento cubren: PKCE inválido, reutilización de código, código expirado, redirect_uri no coincidente en el canje, secreto de cliente incorrecto, escalamiento de scope en client_credentials, grant ROPC no soportado, alg=none, claims requeridos ausentes, token en query string, registro de clientes sin clave administrativa, y una entrada tipo inyección SQL almacenada de forma inerte gracias al ORM."
));

body.push(h1("14. Controles de seguridad"));
[
  "Contraseñas de usuario y secretos de cliente con Argon2id; nunca en texto plano.",
  "Códigos de autorización almacenados solo como hash SHA-256, de un solo uso y expiración corta.",
  "Validación exacta de redirect_uri; ningún caso reencamina a un origen no registrado (sin open redirect).",
  "Algoritmo de firma JWT fijado explícitamente; alg=none y sustitución de algoritmo rechazados.",
  "CORS restringido a orígenes locales explícitos, sin comodín.",
  "Manejador global de excepciones: ninguna traza de pila se expone al cliente.",
  "Sin grant ROPC (contraseña de usuario nunca llega directamente al cliente).",
  "Documentación Swagger UI auto-hospedada (sin dependencia de un CDN externo).",
  "Revisión manual de logs de desarrollo para confirmar que no se registran contraseñas, secretos ni tokens.",
].forEach(t => body.push(bullet(t)));

body.push(h1("15. Problemas encontrados y soluciones"));
body.push(para("Esta sección describe dificultades reales surgidas durante la implementación, no hipotéticas."));
body.push(h3("15.1 Dependencia faltante para validación de correo electrónico"));
body.push(para("Al definir el esquema ProfileOut con un campo EmailStr, Pydantic requiere el paquete email-validator, que no estaba instalado inicialmente y provocó un error de importación al iniciar la aplicación. Se resolvió instalando pydantic[email] y agregándolo a requirements.txt."));
body.push(h3("15.2 Fuga de detalle interno en el mensaje de error 401"));
body.push(para("La primera versión de la validación de tokens propagaba el texto crudo de la excepción de PyJWT (incluyendo, en un caso, un mensaje de error de decodificación de códec) directamente al cliente. Aunque no era una traza de pila ni exponía secretos, no era una práctica limpia. Se corrigió registrando la causa exacta únicamente en el log del servidor y devolviendo al cliente un mensaje genérico y conforme a RFC 6750."));
body.push(h3("15.3 Swagger UI en blanco por dependencia de un CDN externo"));
body.push(para("La configuración por defecto de FastAPI para /docs carga swagger-ui-bundle.js y swagger-ui.css desde cdn.jsdelivr.net. En el entorno de ejecución utilizado, ese dominio no era accesible, por lo que la página de documentación se renderizaba en blanco. Se resolvió vendorizando los archivos de swagger-ui-dist dentro del propio repositorio (app/static/swagger-ui/) y sirviéndolos con FastAPI StaticFiles, de modo que la documentación interactiva funciona sin acceso a Internet — una mejora relevante para la reproducibilidad exigida en la Sección 33 del plan de trabajo."));
body.push(h3("15.4 Inestabilidad al reiniciar el servidor de desarrollo en la terminal automatizada"));
body.push(para("Al encadenar pkill, la recreación de la base de datos y el arranque de uvicorn en un mismo bloque de comandos, el proceso en segundo plano se interrumpía de forma intermitente. Se resolvió separando cada paso en comandos independientes y arrancando el servidor con setsid/disown para desacoplarlo del proceso padre de la terminal."));

body.push(h1("16. Conclusiones"));
[
  "Implementar los dos flujos de OAuth 2.0 de punta a punta — en vez de solo describirlos — hizo tangible por qué PKCE es indispensable para clientes públicos: sin él, cualquiera que interceptara el código de autorización podría canjearlo.",
  "La distinción entre autenticación y autorización dejó de ser una definición de libro de texto en cuanto el token de client_credentials, siendo perfectamente válido, tuvo que ser rechazado explícitamente al pedir un recurso personal.",
  "Diseñar primero las respuestas de error (401 frente a 403 frente a 404) obligó a pensar en qué información se filtra incluso en una denegación de acceso — la decisión de responder 404 en vez de 403 para una playlist ajena fue una consecuencia directa de ese análisis.",
  "Vendorizar los recursos de Swagger UI resultó una lección práctica sobre reproducibilidad: una demostración que depende de un CDN externo puede fallar en un entorno de evaluación con red restringida, aunque el código en sí sea correcto.",
].forEach(t => body.push(numbered(t)));

body.push(h1("17. Recomendaciones"));
[
  "Incorporar refresh tokens con rotación y revocación para escenarios donde una sesión debe sobrevivir más allá de la vida corta del access token.",
  "Migrar la base de datos a PostgreSQL con Alembic para gestionar migraciones si el proyecto creciera más allá de una demostración local.",
  "Añadir límite de tasa (rate limiting) al endpoint de token y al de autorización para mitigar ataques de fuerza bruta sobre credenciales.",
  "Integrar un análisis de seguridad estático (por ejemplo, bandit) y un escaneo de dependencias en un flujo de integración continua.",
  "Evaluar el uso de claves asimétricas (RS256/ES256) en lugar de HMAC si en el futuro varios servicios necesitaran verificar tokens sin compartir un secreto simétrico.",
].forEach(t => body.push(bullet(t)));

body.push(h1("18. Referencias"));
[
  "IETF. RFC 6749 — The OAuth 2.0 Authorization Framework. https://www.rfc-editor.org/rfc/rfc6749",
  "IETF. RFC 6750 — The OAuth 2.0 Authorization Framework: Bearer Token Usage. https://www.rfc-editor.org/rfc/rfc6750",
  "IETF. RFC 7636 — Proof Key for Code Exchange by OAuth Public Clients (PKCE). https://www.rfc-editor.org/rfc/rfc7636",
  "IETF. RFC 7519 — JSON Web Token (JWT). https://www.rfc-editor.org/rfc/rfc7519",
  "IETF. RFC 9068 — JSON Web Token (JWT) Profile for OAuth 2.0 Access Tokens. https://www.rfc-editor.org/rfc/rfc9068",
  "IETF. RFC 9700 — Best Current Practice for OAuth 2.0 Security. https://www.rfc-editor.org/rfc/rfc9700",
  "FastAPI. Documentación oficial. https://fastapi.tiangolo.com/",
  "SQLAlchemy. Documentación oficial (2.0). https://docs.sqlalchemy.org/en/20/",
  "PyJWT. Documentación oficial. https://pyjwt.readthedocs.io/",
  "argon2-cffi. Documentación oficial. https://argon2-cffi.readthedocs.io/",
  "Pytest. Documentación oficial. https://docs.pytest.org/",
].forEach(t => body.push(bullet(t)));

body.push(h1("19. Apéndices"));
body.push(h2("19.1 Matriz de requisitos, evidencia y estado"));
body.push(simpleTable(
  ["Requisito", "Implementación", "Prueba", "Evidencia", "Estado"],
  [
    ["Authorization Code + PKCE", "app/oauth/router.py", "TestScenario1", "EV-02..EV-04, capturas 01-04", "PASS"],
    ["Client Credentials", "app/oauth/router.py::_grant_client_credentials", "TestScenario2", "EV-09a/b", "PASS"],
    ["401 sin token / inválido", "app/api/deps.py", "TestScenario3, TestScenario4", "EV-05a/b", "PASS"],
    ["403 scope insuficiente", "app/api/deps.py::require_scopes", "TestScenario5", "EV-07", "PASS"],
    ["Aislamiento entre usuarios", "app/api/router.py (ownership)", "TestScenario6", "EV-08a..d", "PASS"],
    ["JWT: claims y validación estricta", "app/security.py", "TestJwtHardening", "EV-04b", "PASS"],
    ["alg=none rechazado", "app/security.py (algorithms=[...])", "test_alg_none_token_rejected", "ev10_pytest_results.txt", "PASS"],
    ["Hash de contraseñas/secretos", "app/security.py (Argon2id)", "-", "EV-01", "PASS"],
    ["Swagger/OpenAPI accesible", "app/main.py (self-hosted)", "-", "EV-11, captura 09", "PASS"],
    ["Pruebas automatizadas (38)", "tests/", "pytest -v", "ev10_pytest_results.txt", "PASS"],
  ],
  [2000, 2200, 1600, 1800, 1000],
));
body.push(caption("Tabla 5. Matriz de trazabilidad requisito → implementación → prueba → evidencia."));

body.push(h2("19.2 Diagramas fuente"));
body.push(para("Las fuentes editables (Mermaid) de ambos diagramas están disponibles en docs/diagrams/component_diagram.mmd y docs/diagrams/auth-code-pkce.mmd, y pueden regenerarse como PNG con @mermaid-js/mermaid-cli."));

// ------------------------------------------------------------------ build --
const doc = new Document({
  creator: "SoundAccess — Semana 7",
  title: "Aseguramiento de una API de Música mediante OAuth 2.0 y JWT: el caso SoundAccess",
  features: { updateFields: true }, // forces Word/LibreOffice to refresh the TOC field on open
  styles: {
    default: {
      document: { run: { font: FONT, size: 22, color: INK } },
    },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, bold: true, size: 30, color: INK }, paragraph: { spacing: { before: 400, after: 200 } } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, bold: true, size: 25, color: INK }, paragraph: { spacing: { before: 300, after: 140 } } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONT, bold: true, italics: true, size: 23, color: INK }, paragraph: { spacing: { before: 220, after: 100 } } },
    ],
  },
  numbering: {
    config: [
      { reference: "report-bullets", levels: [
        { level: 0, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 460, hanging: 260 } } } },
      ]},
      { reference: "report-numbers", levels: [
        { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 460, hanging: 260 } } } },
      ]},
    ],
  },
  sections: [
    {
      properties: {
        page: { size: PAGE, margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN } },
        titlePage: true,
      },
      headers: { default: new Header({ children: [new Paragraph({ children: [] })] }) },
      footers: { default: new Footer({ children: [new Paragraph({ children: [] })] }) },
      children: coverChildren,
    },
    {
      properties: {
        page: { size: PAGE, margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN } },
      },
      headers: { default: new Header({ children: [
        new Paragraph({ alignment: AlignmentType.RIGHT,
          children: [new TextRun({ text: "SoundAccess — Informe académico, Semana 7", size: 16, color: MUTED, font: FONT })] }),
      ] }) },
      footers: { default: new Footer({ children: [
        new Paragraph({ alignment: AlignmentType.CENTER, children: [
          new TextRun({ children: [PageNumber.CURRENT], size: 18, color: MUTED, font: FONT }),
        ] }),
      ] }) },
      children: [
        h1("Tabla de contenido"),
        ...TOC_ENTRIES.map(([text, pg, indent]) => tocEntry(text, pg, { indent })),
        pageBreak(),
        ...body,
      ],
    },
  ],
});

Packer.toBuffer(doc).then(buf => {
  const out = path.join(__dirname, "Informe_Academico_SoundAccess.docx");
  fs.writeFileSync(out, buf);
  console.log("Escrito:", out);
});
