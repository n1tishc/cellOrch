import React, { useEffect, useState } from "react";
import { cancelRun, getMetrics, getRun, injectFault, listRuns, pauseRun, resumeRun, startRun } from "./api.js";

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

export default function App() {
  const [runs, setRuns] = useState([]);
  const [metrics, setMetrics] = useState({});
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [connection, setConnection] = useState("connecting");
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState(null);

  async function refresh() {
    const [runResult, metricResult] = await Promise.allSettled([listRuns(), getMetrics()]);
    if (runResult.status === "fulfilled") {
      setRuns(runResult.value);
      setLastUpdated(new Date());
      setError(metricResult.status === "rejected" ? "Metrics unavailable — showing run data." : "");
    } else {
      setError("API unreachable. Retrying…");
      setConnection("disconnected");
    }
    if (metricResult.status === "fulfilled") setMetrics(metricResult.value);
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
  }, [selected]);

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
      </header>

      {error && <div className="connection-error" role="alert">{error}</div>}
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
            <Bar value={r.confluence} />
            <div className="run-actions" onClick={(e) => e.stopPropagation()}>
              <button disabled={!['PENDING', 'WAITING', 'RUNNING'].includes(r.status)} onClick={async () => { await pauseRun(r.id); refresh(); }}>Pause</button>
              <button disabled={r.status !== 'PAUSED'} onClick={async () => { await resumeRun(r.id); refresh(); }}>Resume</button>
              <button className="cancel" disabled={['COMPLETED', 'FAILED', 'CANCELLED'].includes(r.status)} onClick={async () => { await cancelRun(r.id); refresh(); }}>Cancel</button>
            </div>
            <button className="fault" onClick={(e) => { e.stopPropagation(); injectFault(r.id); }}>Inject fault</button>
          </div>
        ))}
      </div>

      {detail && (
        <div className="detail">
          <h2>{detail.run.name} — audit log</h2>
          <ul>
            {detail.events.map((ev) => (
              <li key={ev.id}>
                <span className="ev-type">{ev.type}</span> {ev.message}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
