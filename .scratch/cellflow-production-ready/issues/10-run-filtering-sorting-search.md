# 10 — Run Filtering, Sorting & Search

**What to build:** With 10+ runs the dashboard grid becomes overwhelming — there's no way to find a specific run, filter by status, or sort by recency. This ticket adds query parameters to the `/runs` API endpoint and a filter/sort bar to the dashboard so the operator can narrow down the view.

**Blocked by:** [01 — Config, Enums & Input Validation](./01-config-enums-input-validation.md)

**Status:** ready-for-agent

- [ ] Add query parameters to `GET /runs`: `status` (filter by status), `stage` (filter by current stage), `search` (name substring match), `sort` (by `created_at`, `updated_at`, `name`; ascending or descending)
- [ ] Add a filter bar to the dashboard above the run grid with:
  - Status dropdown (All, Running, Waiting, Pending, Completed, Failed)
  - Stage dropdown (All, Seed, Incubate, Image, Count, Decision, Passage)
  - Search input (filters by run name)
  - Sort selector (Newest, Oldest, Name A-Z, Name Z-A)
- [ ] Filter/sort state should be reflected in the URL (query params) so the view is shareable/bookmarkable
- [ ] Show result count ("Showing 3 of 12 runs")
- [ ] Verify: filtering to "Failed" shows only failed runs
- [ ] Verify: searching "Line-05" shows only matching runs
- [ ] Verify: sorting by newest shows the most recently created run first
