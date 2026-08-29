# 08 — Protocol Pipeline Visualization

**What to build:** The dashboard shows the current stage as text but gives no visual sense of where in the protocol a run is. This ticket adds a horizontal pipeline indicator on each run card — completed stages are green, the current stage is highlighted, future stages are gray — so the operator can see at a glance how far along each line is.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] Add a horizontal pipeline component to each run card showing all protocol stages as nodes in sequence: Seed → Incubate → Image → Count → Decision → Passage
- [ ] Completed stages render as green filled nodes, the current stage as a highlighted/active node (blue pulse or border), future stages as gray empty nodes
- [ ] For runs that have looped back (passaged), show the passage count on the Passage node or as a loop indicator
- [ ] The pipeline should be compact enough to fit on the existing card layout without breaking the grid
- [ ] Verify: a run at the Image stage shows Seed and Incubate as green, Image as active, Count/Decision/Passage as gray
- [ ] Verify: a completed run shows all stages as green
- [ ] Verify: a run that has passaged twice shows the loop visually (e.g. passage node shows "×2")
