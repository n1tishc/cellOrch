const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
let tokenProvider = async () => null;

export function setAuthTokenProvider(provider) { tokenProvider = provider; }

async function request(path, options = {}) {
  const token = await tokenProvider();
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${BASE}${path}`, { ...options, headers });
  if (!response.ok) throw new Error(await response.text());
  return response;
}

async function json(path, options) { return (await request(path, options)).json(); }
export async function listRuns(params = {}) {
  const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value));
  const response = await request(`/runs?${query}`);
  return { runs: await response.json(), total: Number(response.headers.get("X-Total-Count") || 0) };
}
export function getMetrics() { return json("/metrics"); }
export function getResources() { return json("/resources"); }
export function getRun(id) { return json(`/runs/${id}`); }
function transition(id, action) { return request(`/runs/${id}/${action}`, { method: "POST" }); }
export function pauseRun(id) { return transition(id, "pause"); }
export function resumeRun(id) { return transition(id, "resume"); }
export function cancelRun(id) { return transition(id, "cancel"); }
export function injectFault(id) { return request(`/runs/${id}/inject-fault`, { method: "POST" }); }
export function startRun() { return request("/runs", { method: "POST" }); }
export function listWebhooks() { return json("/webhooks"); }
export function createWebhook(payload) { return json("/webhooks", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }); }
export function deleteWebhook(id) { return request(`/webhooks/${id}`, { method: "DELETE" }); }
export function testWebhook(id) { return request(`/webhooks/${id}/test`, { method: "POST" }); }

async function download(path) {
  const response = await request(path);
  const filename = response.headers.get("content-disposition")?.match(/filename="?([^";]+)"?/)?.[1] || "export";
  const url = URL.createObjectURL(await response.blob());
  const anchor = Object.assign(document.createElement("a"), { href: url, download: filename });
  anchor.click();
  URL.revokeObjectURL(url);
}
export function exportRun(id, format = "csv") { return download(`/runs/${id}/export?format=${format}`); }
export function exportRuns(format = "csv") { return download(`/runs/export?format=${format}`); }
