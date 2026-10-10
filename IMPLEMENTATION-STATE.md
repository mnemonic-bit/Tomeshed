# Implementation state

The coordinator maintains this file according to `IMPLEMENTATION-WORKFLOW.md`. Allowed states are `queued`, `active`, `blocked`, and `completed`. A feature is `completed` only when its evidence report records `passed` for every mandatory acceptance criterion.

| Feature | State | Evidence report | Checked revision | Blocker or next action |
| --- | --- | --- | --- | --- |
| 0001 | completed | `FEATURES/evidence/feature-0001.md` | Code tree `cebafe659203088cd769c6c880e5e8d2d82e4ed5` | All AC-01–AC-13 passed; reviewer has no unresolved finding. |
| 0002 | completed | `FEATURES/evidence/feature-0002.md` | Code tree `e52238208d6adbecee52e2a0ee9f7889a193fa25` | All AC-01–AC-12 passed after the retry-race fix; reviewer has no unresolved finding. |
| 0003 | completed | `FEATURES/evidence/feature-0003.md` | Code tree `7886612a2103513dbdb89d31e5fff841a4cc6c5e` | All AC-01–AC-12 passed after the reader-focus fix; reviewer has no unresolved finding. |
| 0004 | completed | `FEATURES/evidence/feature-0004.md` | Code tree `2aec3ef9dbe36f7510df2f9520a4a9dba3438119` | All AC-01–AC-09 passed after dismissal and rendering-limit fixes; reviewer has no unresolved finding. |
| 0005 | completed | `FEATURES/evidence/feature-0005.md` | Code tree `cc3437dda64c1ffa6a6602536aa993043971247a` | All AC-01–AC-11 passed; reviewer has no unresolved Feature 0005 finding. |
| 0006 | completed | `FEATURES/evidence/feature-0006.md` | Code tree `29f33d4f10cc97db339c44122fee790a6a29b4b9` | All AC-01–AC-13 passed after transfer-restart and browser-check fixes; reviewer has no unresolved finding. |
| 0007 | completed | `FEATURES/evidence/feature-0007.md` | Code tree `0506050d5ee862d1e50e225279e8a0169c0ac2d2` | All AC-01–AC-11 passed after authorization and browser-check fixes; reviewer has no unresolved finding. |
