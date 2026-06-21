const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function listRuns() {
  const r = await fetch(`${BASE}/runs`);
  return r.json();
}
export async function getMetrics() {
  const r = await fetch(`${BASE}/metrics`);
  return r.json();
}
export async function getRun(id) {
  const r = await fetch(`${BASE}/runs/${id}`);
  return r.json();
}
export async function injectFault(id) {
  await fetch(`${BASE}/runs/${id}/inject-fault`, { method: "POST" });
}
export async function startRun() {
  await fetch(`${BASE}/runs`, { method: "POST" });
}
