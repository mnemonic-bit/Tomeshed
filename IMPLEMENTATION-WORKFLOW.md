# Numbered feature implementation workflow

## Goal and roles

The coordinator implements every feature in `FEATURES/README.md` in number order. The coordinator is the main Codex session. For each feature, the coordinator assigns one `feature_builder` to implementation and one `feature_reviewer` to independent verification. The coordinator owns integration, fixes, and the final completion decision.

`AGENTS.md` and `AGENT-LANG.md` apply to every role. `VDL/` is a read-only reference. All Tomeshed changes belong outside `VDL/`.

## Start or resume

1. Read `FEATURES/README.md`, `IMPLEMENTATION-STATE.md`, and the current git status.
2. Compare the state file with the source, tests, and recorded evidence. Treat a status without its required evidence as unverified.
3. Select the lowest-numbered feature whose status is not `completed`. Check its listed dependencies before implementation.
4. Record the selected feature as `active` in `IMPLEMENTATION-STATE.md`. Name its feature file, baseline revision, and pre-existing working-tree changes so the feature's edits can be identified later.

## Complete one feature

1. Read the feature file and map every acceptance criterion to a verification action. Inspect relevant current VDL source and documents. Use the installed `codebase-memory` skill for structural exploration and verify graph coverage for relied-on files.
2. Spawn `feature_builder` with the feature ID, file, baseline revision, owned files or responsibility, and the acceptance map. Keep dependent implementation work sequential when files or database schema overlap.
3. After the builder reports, inspect tracked and untracked changes and run or inspect the stated checks. Spawn `feature_reviewer` with the same feature ID, baseline revision, pre-existing changes, implementation paths, and evidence locations.
4. For every `failed` or `inconclusive` mandatory criterion, fix the cause, rerun the affected checks, and request another focused review. For `not_run`, perform the specified check or record the concrete missing tool, fixture, or environment.
5. Write a feature evidence report at `FEATURES/evidence/feature-NNNN.md`. Record each acceptance ID, result, command or observation, and artifact or file path. Include browser, restart, container, and authorization checks when the feature requires them.
6. Mark the feature `completed` in `IMPLEMENTATION-STATE.md` only when every mandatory acceptance criterion is `passed` and the reviewer has no unresolved finding. Record the evidence report path and the revision checked. Continue with the next numbered feature.

## Blockers and recovery

Use `blocked` only when a concrete missing credential, tool, external service, or unresolved requirement prevents further meaningful work. Record the blocker, affected acceptance IDs, attempted checks, and the next action in `IMPLEMENTATION-STATE.md`. Continue independent work within the active feature when possible. Do not advance to a feature that depends on an incomplete feature. When a session ends, the next coordinator resumes from the state file and rechecks the working tree before accepting a prior completion claim.

The coordinator may make routine implementation decisions without asking for each feature. A decision that changes the feature's user-visible scope or requires an irreversible external action needs user direction. A failed check remains visible until fixed or explicitly resolved.

## Launch prompt

From the repository root, start a Codex session with this request:

> Implement all numbered features in `FEATURES/README.md` in order. Act as the coordinator in `IMPLEMENTATION-WORKFLOW.md`. Use the project `feature_builder` and `feature_reviewer` agents for each feature. Keep working through the plan without asking me about routine implementation choices. Record evidence and progress after each feature. Stop only for a concrete blocker or when all acceptance criteria pass.

Agent definitions and the launch prompt govern a running session. They do not start a session or resume one after the process exits; use the same prompt again to resume from `IMPLEMENTATION-STATE.md`.
