import React, { useEffect, useState } from "react";
import { cancelRun, exportRun, exportRuns, getMetrics, getResources, getRun, injectFault, listRuns, pauseRun, resumeRun, startRun } from "./api.js";

const STAGE_COLORS = {
  Seed: "#888780", Incubate: "#1D9E75", Image: "#1D9E75",
  Count: "#888780", Decision: "#534AB7", Passage: "#BA7517",
};
const STATUS_COLORS = {
  RUNNING: "#185FA5", WAITING: "#854F0B", PENDING: "#5F5E5A",
  PAUSED: "#854F0B", CANCELLED: "#5F5E5A", COMPLETED: "#3B6D11", FAILED: "#A32D2D",
};

function Bar({ value }) {
  return (
    <div className="bar">
      <div className="bar-fill" style={{ width: `${Math.round(value * 100)}%` }} />
      <span className="bar-label">{Math.round(value * 100)}%</span>
    </div>
  );
}

const PIPELINE = ["Seed", "Incubate", "Image", "Count", "Decision", "Passage"];
function Pipeline({ run }) {
  const current = PIPELINE.indexOf(run.stage_name);
  const completed = run.status === "COMPLETED";
  return <div className="pipeline" aria-label={`Protocol stage: ${run.stage_name}`}>
    {PIPELINE.map((stage, index) => <React.Fragment key={stage}>
      {index > 0 && <i className={index <= current || completed ? "done" : ""} />}
      <span className={`pipeline-node ${completed || index < current ? "done" : ""} ${!completed && index === current ? "current" : ""}`} title={stage}>{stage[0]}{stage === "Passage" && run.passage_count > 0 ? `×${run.passage_count}` : ""}</span>
    </React.Fragment>)}
  </div>;

export default function App() {
  const [runs, setRuns] = useState([]);
  const [metrics, setMetrics] = useState({});
  const [resources, setResources] = useState({ resources: {}, queue_depth: 0 });
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [connection, setConnection] = useState("connecting");
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState(null);
  const [eventSearch, setEventSearch] = useState("");
  const [hiddenEventTypes, setHiddenEventTypes] = useState(new Set());
  const [eventLimit, setEventLimit] = useState(50);
  const initialFilters = Object.fromEntries(new URLSearchParams(window.location.search));
  const [filters, setFilters] = useState({ status: initialFilters.status || "", stage: initialFilters.stage || "", search: initialFilters.search || "", sort: initialFilters.sort || "created_at", direction: initialFilters.direction || "desc" });
  const [theme, setTheme] = useState(() => localStorage.getItem("cellflow-theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("cellflow-theme", theme);
  }, [theme]);

  useEffect(() => {
    const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value && value !== "created_at" && value !== "desc"));
    window.history.replaceState(null, "", `${window.location.pathname}${query.size ? `?${query}` : ""}`);
  }, [filters]);

  async function refresh() {
    const [runResult, metricResult, resourceResult] = await Promise.allSettled([listRuns(filters), getMetrics(), getResources()]);
    if (runResult.status === "fulfilled") {
      setRuns(runResult.value);
      setLastUpdated(new Date());
      setError(metricResult.status === "rejected" ? "Metrics unavailable — showing run data." : "");
    } else {
      setError("API unreachable. Retrying…");
      setConnection("disconnected");
    }
    if (metricResult.status === "fulfilled") setMetrics(metricResult.value);
    if (resourceResult.status === "fulfilled") setResources(resourceResult.value);
    if (selected != null) {
      try { setDetail(await getRun(selected)); } catch { setError("Run detail unavailable."); }
    }
    setLoading(false);
  }

  useEffect(() => {
    let source;
    let retryTimer;
    let attempts = 0;
    const streamUrl = `${import.meta.env.VITE_API_URL || "http://localhost:8000"}/runs/stream`;
    const connect = () => {
      if (document.hidden) return;
      source = new EventSource(streamUrl);
      source.onopen = () => { attempts = 0; setConnection("connected"); setError(""); }; 
      source.onmessage = async ({ data }) => {
        const event = JSON.parse(data);
        const update = await getRun(event.run_id);
        setRuns((current) => current.map((run) => run.id === event.run_id ? update.run : run));
        if (selected === event.run_id) setDetail(update);
        getResources().then(setResources).catch(() => {});
      };
      source.onerror = () => {
        source.close();
        setConnection("reconnecting");
        setError("Connection lost. Reconnecting…");
        retryTimer = setTimeout(connect, Math.min(30000, 1000 * 2 ** attempts++));
      };
    };
    const onVisibility = () => { source?.close(); clearTimeout(retryTimer); if (!document.hidden) connect(); };
    refresh();
    connect();
    document.addEventListener("visibilitychange", onVisibility);
    return () => { source?.close(); clearTimeout(retryTimer); document.removeEventListener("visibilitychange", onVisibility); };
  }, [selected, filters]);

  const events = detail?.events ?? [];
  const eventTypes = [...new Set(events.map((event) => event.type))].sort();
  const visibleEvents = events.filter((event) => !hiddenEventTypes.has(event.type) && event.message.toLowerCase().includes(eventSearch.toLowerCase())).slice(0, eventLimit);
  const eventColor = (type) => ({ step_started: "blue", step_done: "green", retry: "yellow", failed: "red", completed: "green-bold", decision: "purple", passage: "orange", queued: "gray" }[type] || "gray");
  const relativeTime = (time) => { const seconds = Math.max(0, (Date.now() - new Date(time)) / 1000); return seconds < 60 ? "just now" : seconds < 3600 ? `${Math.floor(seconds / 60)}m ago` : `${Math.floor(seconds / 3600)}h ago`; };

  return (
    <div className="wrap">
      <header>
        <h1>CellFlow</h1>
        <span className="sub">lab-workflow orchestrator</span>
        <span className={`connection ${connection}`}><i />{connection}</span>
        {lastUpdated && <span className="updated">updated {lastUpdated.toLocaleTimeString()}</span>}
        <div className="metrics">
          <span>{metrics.runs_active ?? 0} active</span>
          <span>{metrics.runs_completed ?? 0} done</span>
          <span className="fail">{metrics.runs_failed ?? 0} failed</span>
          <span>{metrics.retries_total ?? 0} retries</span>
          <span>{metrics.audit_events_total ?? 0} events</span>
        </div>
        <button onClick={async () => { await startRun(); refresh(); }}>+ Start run</button>
        <button onClick={refresh}>Retry</button>
        <button onClick={() => exportRuns()}>Export runs</button>
        <button className="theme-toggle" aria-label="Toggle color theme" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>{theme === "dark" ? "☀" : "☾"}</button>
      </header>

      <section className="resource-panel">
        {Object.entries(resources.resources).map(([name, resource]) => <div className="resource" key={name}><span>{name}</span><b>{resource.used}/{resource.capacity}</b><div className={`utilization ${resource.used / resource.capacity > .8 ? "high" : resource.used / resource.capacity >= .5 ? "medium" : "low"}`}><i style={{ width: `${resource.used / resource.capacity * 100}%` }} /></div></div>)}
        <div className="resource queue"><span>Queue depth</span><b>{resources.queue_depth}</b></div>
      </section>
      {error && <div className="connection-error" role="alert">{error}</div>}
      <div className="filter-bar">
        <select value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.target.value })}><option value="">All statuses</option>{["RUNNING", "WAITING", "PENDING", "COMPLETED", "FAILED"].map((value) => <option key={value}>{value}</option>)}</select>
        <select value={filters.stage} onChange={(event) => setFilters({ ...filters, stage: event.target.value })}><option value="">All stages</option>{["Seed", "Incubate", "Image", "Count", "Decision", "Passage"].map((value) => <option key={value}>{value}</option>)}</select>
        <input placeholder="Search runs" value={filters.search} onChange={(event) => setFilters({ ...filters, search: event.target.value })} />
        <select value={`${filters.sort}:${filters.direction}`} onChange={(event) => { const [sort, direction] = event.target.value.split(":"); setFilters({ ...filters, sort, direction }); }}><option value="created_at:desc">Newest</option><option value="created_at:asc">Oldest</option><option value="name:asc">Name A-Z</option><option value="name:desc">Name Z-A</option></select>
      </div>
      <p className="result-count">Showing {runs.length} runs</p>
      <div className="grid">
        {loading && Array.from({ length: 6 }, (_, index) => <div className="card skeleton" key={index} />)}
        {!loading && runs.length === 0 && <div className="empty-state">No runs yet. Start a run to begin the protocol.</div>}
        {!loading && runs.map((r) => (
          <div
            key={r.id}
            className={`card ${selected === r.id ? "active" : ""}`}
            onClick={() => setSelected(r.id)}
          >
            <div className="card-top">
              <strong>{r.name}</strong>
              <span className="status" style={{ background: STATUS_COLORS[r.status] }}>
                {r.status}
              </span>
            </div>
            <div className="stage" style={{ color: STAGE_COLORS[r.stage_name] }}>
              {r.stage_name} · passage {r.passage_count}
            </div>
            <Pipeline run={r} />
            <Bar value={r.confluence} />
            <div className="run-actions" onClick={(e) => e.stopPropagation()}>
              <button disabled={!['PENDING', 'WAITING', 'RUNNING'].includes(r.status)} onClick={async () => { await pauseRun(r.id); refresh(); }}>Pause</button>
              <button disabled={r.status !== 'PAUSED'} onClick={async () => { await resumeRun(r.id); refresh(); }}>Resume</button>
              <button className="cancel" disabled={['COMPLETED', 'FAILED', 'CANCELLED'].includes(r.status)} onClick={async () => { await cancelRun(r.id); refresh(); }}>Cancel</button>
            </div>
            <button className="fault" onClick={(e) => { e.stopPropagation(); injectFault(r.id); }}>Inject fault</button>
            <button className="export" onClick={(e) => { e.stopPropagation(); exportRun(r.id); }}>Export</button>
          </div>
        ))}
      </div>

      {detail && (
        <div className="detail">
          <h2>{detail.run.name} — audit log</h2>
          <div className="event-controls"><input aria-label="Search audit events" placeholder="Search events" value={eventSearch} onChange={(event) => { setEventSearch(event.target.value); setEventLimit(50); }} /><div className="filter-chips">{eventTypes.map((type) => <button key={type} className={hiddenEventTypes.has(type) ? "is-hidden" : ""} onClick={() => { setHiddenEventTypes((current) => { const next = new Set(current); next.has(type) ? next.delete(type) : next.add(type); return next; }); setEventLimit(50); }}>{type}</button>)}</div></div>
          <ul className="timeline">{visibleEvents.map((ev) => <li key={ev.id} className={`event event-${eventColor(ev.type)}`}><time title={new Date(ev.created_at).toLocaleString()}>{relativeTime(ev.created_at)}</time><span className="ev-type">{ev.type}</span><span>{ev.message}</span></li>)}</ul>
          {events.filter((event) => !hiddenEventTypes.has(event.type) && event.message.toLowerCase().includes(eventSearch.toLowerCase())).length > eventLimit && <button onClick={() => setEventLimit((limit) => limit + 50)}>Load more</button>}
        </div>
      )}
    </div>
  );
}
