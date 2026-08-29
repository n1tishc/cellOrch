# 06 — Dashboard Resilience

**What to build:** If the API is unreachable, the dashboard silently shows stale data or crashes. There are no loading states, no error boundaries, no retry indicators. This ticket adds loading skeletons during initial fetch, error toasts when the API is down, visual retry indicators, and graceful degradation so the operator always knows what's happening.

**Blocked by:** [05 — Real-Time Dashboard (SSE)](./05-real-time-dashboard-sse.md)

**Status:** ready-for-agent

- [ ] Add a loading skeleton grid that displays while the initial run list is being fetched
- [ ] Add an error toast/banner that appears when the API is unreachable, with a "Retrying..." message
- [ ] Add a connection status indicator (green dot = connected, red dot = disconnected) in the header
- [ ] Handle SSE connection loss: show a "Reconnecting..." indicator, attempt automatic reconnection
- [ ] Add a manual "Retry" button that forces a full data refresh
- [ ] Show "last updated" timestamp so the operator knows how stale the data is
- [ ] Handle empty states gracefully: "No runs yet" message with a prompt to start one
- [ ] Handle partial failures: if `/runs` succeeds but `/metrics` fails, still show runs with a degraded indicator
- [ ] Verify: killing the orchestrator while the dashboard is open shows the error state, not a blank page
- [ ] Verify: restarting the orchestrator causes the dashboard to reconnect and resume showing data
