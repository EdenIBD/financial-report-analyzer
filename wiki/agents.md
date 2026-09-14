# agents.md — instructions for the wiki agent

- On every run, check log.md and index.md before making any change.
- When a significant change happens (a new technical decision, a shipped
  feature, a discovered bug/failure pattern), automatically add a dated entry
  to log.md:
  `## [YYYY-MM-DD] <short description> | <pages created/updated>`
- Do not ask the user to track this manually — log.md is the source of truth
  for the timeline.
- Update index.md every time a new page is created.
- Do not edit files under raw/ directly — they are immutable; corrections go
  into the wiki pages instead.
