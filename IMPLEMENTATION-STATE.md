# Implementation state

The coordinator maintains this file according to `IMPLEMENTATION-WORKFLOW.md`. Allowed states are `queued`, `active`, `blocked`, and `completed`. A feature is `completed` only when its evidence report records `passed` for every mandatory acceptance criterion.

| Feature | State | Evidence report | Checked revision | Blocker or next action |
| --- | --- | --- | --- | --- |
| 0001 | queued | — | — | Start with `FEATURES/feature-0001-app-shell-and-access.md`. |
| 0002 | queued | — | — | Wait for 0001. |
| 0003 | queued | — | — | Wait for 0002. |
| 0004 | queued | — | — | Wait for 0003. |
| 0005 | queued | — | — | Wait for 0002 and 0003. |
| 0006 | queued | — | — | Wait for 0002. |
| 0007 | queued | — | — | Wait for 0002 and 0003. |
