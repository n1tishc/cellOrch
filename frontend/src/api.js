const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function listRuns(params = {}) {
  const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value));
  const r = await fetch(`${BASE}/runs?${query}`);
  return r.json();
}
export async function getMetrics() {
  const r = await fetch(`${BASE}/metrics`);
  return r.json();
}
export async function getResources() {
  const r = await fetch(`${BASE}/resources`);
  return r.json();
}
export async function getRun(id) {
  const r = await fetch(`${BASE}/runs/${id}`);
  return r.json();
}
async function transition(id, action) {
  const response = await fetch(`${BASE}/runs/${id}/${action}`, { method: "POST" });
  if (!response.ok) throw new Error(await response.text());
}

export function pauseRun(id) { return transition(id, "pause"); }
export function resumeRun(id) { return transition(id, "resume"); }
export function cancelRun(id) { return transition(id, "cancel"); }

export async function injectFault(id) {
  await fetch(`${BASE}/runs/${id}/inject-fault`, { method: "POST" });
}
export async function startRun() {
  await fetch(`${BASE}/runs`, { method: "POST" });
}
