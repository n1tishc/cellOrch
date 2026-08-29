# 11 — Dark Mode & Responsive Layout

**What to build:** The dashboard has no dark mode (a lab dashboard running all day needs one) and the header breaks on mobile. This ticket adds CSS custom properties for theming, a theme toggle, and responsive media queries so the dashboard is usable on any screen size.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] Define CSS custom properties for all colors, backgrounds, borders, and text colors
- [ ] Create a light theme (current colors) and a dark theme variant
- [ ] Add a theme toggle button in the header (sun/moon icon) that persists the choice in `localStorage`
- [ ] Default to the user's `prefers-color-scheme` system preference if no explicit choice is stored
- [ ] Add media queries for screens < 768px: header stacks vertically, grid becomes single-column, cards go full-width
- [ ] Add media queries for screens < 480px: metrics bar wraps, font sizes reduce
- [ ] Ensure all existing components (cards, detail panel, metrics bar, buttons) render correctly in both themes
- [ ] Verify: toggling dark mode doesn't cause layout shifts or flash of unstyled content
- [ ] Verify: the dashboard is usable on a 375px-wide screen (iPhone SE)
