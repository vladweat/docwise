import { createServer } from "node:http";

const port = Number(process.env.E2E_API_PORT ?? 18081);
const sessionId = "22222222-2222-4222-8222-222222222222";
const sessionAlpha = "66666666-6666-4666-8666-666666666666";
const sessionBeta = "77777777-7777-4777-8777-777777777777";
const documentId = "11111111-1111-4111-8111-111111111111";
const createdAt = "2026-01-01T00:00:00Z";
const secondOrganization = {
  id: "88888888-8888-4888-8888-888888888888",
  name: "Workspace Two",
  role: "employee",
  departments: [],
};
let sessionCreated = false;
let betaLoadFailures = 0;

const baseUser = {
  id: "33333333-3333-4333-8333-333333333333",
  email: "employee@docwise.example.com",
  role: "employee",
  departments: [],
  is_active: true,
  created_at: createdAt,
  organization_id: "44444444-4444-4444-8444-444444444444",
  organization_name: "Demo",
  organizations: [
    {
      id: "44444444-4444-4444-8444-444444444444",
      name: "Demo",
      role: "employee",
      departments: [],
    },
  ],
};
let currentUser = baseUser;

let document = {
  id: documentId,
  title: "Employee Handbook.pdf",
  content_format: "pdf",
  file_size_bytes: 256,
  total_pages: 1,
  access_roles: ["all"],
  status: "ready",
  last_error: null,
  preview_snippet: "Core working hours are 09:00 to 18:00.",
  created_at: createdAt,
};

function sendJson(response, status, body, headers = {}) {
  response.writeHead(status, {
    "content-type": "application/json",
    "access-control-allow-origin": "http://localhost:13000",
    "access-control-allow-credentials": "true",
    ...headers,
  });
  response.end(JSON.stringify(body));
}

async function readJson(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  return JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}");
}

async function discardBody(request) {
  for await (const _chunk of request) {
    // The fixture only needs to accept the browser upload, not persist its bytes.
  }
}

function makePdf() {
  const stream = "BT /F1 18 Tf 72 720 Td (Employee Handbook) Tj ET";
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    `<< /Length ${Buffer.byteLength(stream)} >>\nstream\n${stream}\nendstream`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
  ];
  let pdf = "%PDF-1.4\n";
  const offsets = [0];
  for (let index = 0; index < objects.length; index += 1) {
    offsets.push(Buffer.byteLength(pdf));
    pdf += `${index + 1} 0 obj\n${objects[index]}\nendobj\n`;
  }
  const xrefOffset = Buffer.byteLength(pdf);
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (const offset of offsets.slice(1)) {
    pdf += `${String(offset).padStart(10, "0")} 00000 n \n`;
  }
  pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF`;
  return Buffer.from(pdf);
}

const server = createServer(async (request, response) => {
  const url = new URL(request.url ?? "/", `http://localhost:${port}`);
  if (request.method === "OPTIONS") {
    response.writeHead(204, {
      "access-control-allow-origin": "http://localhost:13000",
      "access-control-allow-credentials": "true",
      "access-control-allow-methods": "GET,POST,DELETE,OPTIONS",
      "access-control-allow-headers": "content-type,x-requested-with",
    });
    response.end();
    return;
  }
  if (url.pathname === "/health") {
    sendJson(response, 200, { status: "ok" });
    return;
  }
  if (!url.pathname.startsWith("/api/v1/")) {
    sendJson(response, 404, { error: { code: "not_found", message: "Not found" } });
    return;
  }
  if (url.pathname === "/api/v1/auth/me") {
    const authenticated = request.headers.cookie?.includes("docwise_e2e=1");
    sendJson(response, authenticated ? 200 : 401, authenticated ? currentUser : { error: { code: "unauthorized", message: "Not authenticated" } });
    return;
  }
  if (url.pathname === "/api/v1/auth/login" && request.method === "POST") {
    const payload = await readJson(request);
    currentUser = payload.email === "admin@docwise.example.com"
      ? { ...baseUser, role: "admin" }
      : payload.email === "qa@docwise.example.com"
        ? { ...baseUser, email: payload.email, organizations: [...baseUser.organizations, secondOrganization] }
        : baseUser;
    if (payload.email === "qa@docwise.example.com") betaLoadFailures = 0;
    sendJson(response, 200, currentUser, { "set-cookie": "docwise_e2e=1; HttpOnly; Path=/; SameSite=Lax" });
    return;
  }
  if (url.pathname === "/api/v1/auth/switch-organization" && request.method === "POST") {
    const payload = await readJson(request);
    currentUser = payload.organization_id === secondOrganization.id
      ? { ...currentUser, organization_id: secondOrganization.id, organization_name: secondOrganization.name }
      : { ...currentUser, organization_id: baseUser.organization_id, organization_name: baseUser.organization_name };
    sendJson(response, 200, currentUser);
    return;
  }
  if (url.pathname === "/api/v1/documents/access-options") {
    sendJson(response, 200, { roles: ["all", "employee", "manager", "admin"], departments: [] });
    return;
  }
  if (url.pathname === "/api/v1/documents") {
    sendJson(response, 200, { items: [document], total: 1, limit: 50, offset: 0 });
    return;
  }
  if (url.pathname === "/api/v1/documents/upload" && request.method === "POST") {
    await discardBody(request);
    document = {
      ...document,
      id: "55555555-5555-4555-8555-555555555555",
      title: "Interview-demo.pdf",
      status: "processing",
      last_error: null,
      created_at: new Date().toISOString(),
    };
    setTimeout(() => {
      document = { ...document, status: "ready" };
    }, 700);
    sendJson(response, 202, document);
    return;
  }
  if (url.pathname === `/api/v1/documents/${document.id}/status`) {
    sendJson(response, 200, { id: document.id, status: document.status, last_error: null, stage: document.status === "processing" ? "parse" : null });
    return;
  }
  if (url.pathname === `/api/v1/documents/${documentId}/raw`) {
    response.writeHead(200, {
      "content-type": "application/pdf",
      "access-control-allow-origin": "http://localhost:13000",
      "access-control-allow-credentials": "true",
    });
    response.end(makePdf());
    return;
  }
  if (url.pathname === "/api/v1/chat/sessions") {
    if (currentUser.email === "qa@docwise.example.com") {
      const items = [
        { id: sessionAlpha, title: "Session Alpha", created_at: createdAt, updated_at: createdAt },
        { id: sessionBeta, title: "Session Beta", created_at: createdAt, updated_at: createdAt },
      ];
      sendJson(response, 200, { items, total: items.length, limit: 50, offset: 0 });
      return;
    }
    const items = sessionCreated ? [{ id: sessionId, title: "What are the core working hours?", created_at: createdAt, updated_at: createdAt }] : [];
    sendJson(response, 200, { items, total: items.length, limit: 50, offset: 0 });
    return;
  }
  if (url.pathname === `/api/v1/chat/sessions/${sessionAlpha}`) {
    if (currentUser.organization_id !== baseUser.organization_id) {
      sendJson(response, 404, { detail: "Session not found" });
      return;
    }
    sendJson(response, 200, {
      id: sessionAlpha,
      title: "Session Alpha",
      created_at: createdAt,
      updated_at: createdAt,
      messages: [
        { id: "99999999-9999-4999-8999-999999999991", role: "user", content: "Alpha question", sources: [], created_at: createdAt },
        { id: "99999999-9999-4999-8999-999999999992", role: "assistant", content: "History from session Alpha", sources: [], created_at: createdAt },
      ],
    });
    return;
  }
  if (url.pathname === `/api/v1/chat/sessions/${sessionBeta}`) {
    if (betaLoadFailures === 0) {
      betaLoadFailures += 1;
      sendJson(response, 503, { detail: "Temporary test failure" });
      return;
    }
    sendJson(response, 200, {
      id: sessionBeta,
      title: "Session Beta",
      created_at: createdAt,
      updated_at: createdAt,
      messages: [
        { id: "99999999-9999-4999-8999-999999999993", role: "user", content: "Beta question", sources: [], created_at: createdAt },
        { id: "99999999-9999-4999-8999-999999999994", role: "assistant", content: "History from session Beta", sources: [], created_at: createdAt },
      ],
    });
    return;
  }
  if (url.pathname === "/api/v1/chat/stream" && request.method === "POST") {
    const payload = await readJson(request);
    sessionCreated = true;
    response.writeHead(200, {
      "content-type": "text/event-stream",
      "cache-control": "no-cache",
      "access-control-allow-origin": "http://localhost:13000",
      "access-control-allow-credentials": "true",
    });
    response.write(`data: ${JSON.stringify({ type: "meta", cached: false, tokens_used: null, cost_usd: null, session_id: sessionId, message_id: null })}\n\n`);
    if (payload.query === "Trigger the broken stream") {
      response.write(`data: ${JSON.stringify({ type: "token", content: "Partial answer before stream failure" })}\n\n`);
      response.write(`data: ${JSON.stringify({ type: "error", content: "Chat failed. Try again." })}\n\n`);
      response.end(`data: ${JSON.stringify({ type: "done" })}\n\n`);
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 1500));
    response.write(`data: ${JSON.stringify({ type: "citations", citations: [{ doc_id: documentId, doc_title: document.title, page: 1, snippet: "Core working hours are 09:00 to 18:00." }] })}\n\n`);
    response.write(`data: ${JSON.stringify({ type: "token", content: "Core working hours are 09:00 to 18:00." })}\n\n`);
    response.end(`data: ${JSON.stringify({ type: "done" })}\n\n`);
    return;
  }
  sendJson(response, 404, { error: { code: "not_found", message: "Not found" } });
});

server.listen(port, "0.0.0.0");
