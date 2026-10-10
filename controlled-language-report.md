# Controlled Language for Reliable AI-Agent Handoffs

## Direct answer

The idea is sound. A restricted language inspired by ASD-STE100 can improve communication between LLM sessions and agents, particularly for task assignment, status reporting, acceptance criteria, blockers, and state transfer. ASD-STE100 combines controlled vocabulary with writing rules such as consistent terminology, short sentences, one instruction per sentence, explicit conditions, and gradual presentation of information.[^1][^2]

However, controlled English should not be the complete protocol. The strongest architecture uses three layers: a machine-validated message envelope, controlled natural language for semantic content, and durable artifacts for detailed evidence. This resembles established agent-communication concepts: FIPA separates the communicative act from message content, while current protocols such as A2A distinguish tasks, lifecycle state, messages, and artifacts.[^3][^4][^5][^6]

## Why the idea fits

A handoff between two agents has the same underlying problem as a maintenance instruction: one party knows an intended action and must encode it so another party can reconstruct that intent reliably. Unrestricted prose permits synonyms, vague references, hidden assumptions, mixed commands, and unclear completion conditions. These problems become more serious when the receiving agent has a fresh context and cannot recover the sender’s unstated assumptions.

The official ASD-STE100 rules target many of these failure modes. They require consistent technical nouns, approved meanings, short procedural sentences, one instruction per sentence, explicit conditions before commands, and one topic per paragraph. Those constraints map naturally to agent handoffs:[^1]

- **Consistent nouns:** Use `work item`, `repository`, `branch`, `test result`, and `artifact` consistently.
- **Single meanings:** Do not alternate between `done`, `finished`, `resolved`, and `complete` if they represent one workflow state.
- **One action per instruction:** Do not combine implementation, testing, and reporting in one sentence.
- **Explicit conditions:** State when an action is permitted and what happens when the condition is false.
- **Short references:** Replace pronouns such as “it,” “that,” and “this” when the antecedent could be unclear.
- **Gradual information:** Present goal, inputs, constraints, actions, and acceptance criteria in a stable order.

This is especially relevant to workflows that use separate LLM sessions. A previous design discussion established the same architectural boundary: shared workflow state should live in an external store rather than in an agent’s private context, and deterministic code should own transitions, limits, and retries. Controlled language improves what crosses that boundary; it does not remove the need for the boundary.[^7]

## What it can solve

| Failure mode | Unrestricted handoff | Controlled handoff |
|---|---|---|
| Vague reference | “Update it and check that it still works.” | “Update `TokenService.cs`. Run `TokenServiceTests`.” |
| Hidden condition | “Use the fallback if needed.” | “If the primary endpoint returns HTTP 503, use the fallback endpoint.” |
| Mixed actions | “Fix, test, document, and let me know.” | Four separately numbered actions. |
| Ambiguous completion | “Finish the authentication change.” | “Set the task to `completed` only when all acceptance checks pass.” |
| Synonym drift | `done`, `finished`, `closed`, `resolved` | One enum value: `completed`. |
| Unsupported inference | “Handle errors appropriately.” | “Return `failure` after three unsuccessful attempts. Include the last error.” |
| Lost provenance | “The tests passed.” | “Command `dotnet test Auth.Tests` exited with code 0 at the recorded commit.” |
| Unbounded authority | “Make any required changes.” | “You can modify only files under `src/Auth/` and `tests/Auth/`.” |

A controlled language is particularly useful for **semantic invariants** that are awkward to express with JSON Schema alone. A schema can require an `acceptance_criteria` array, but it cannot by itself guarantee that each criterion is observable, unambiguous, or testable. Controlled wording can impose rules such as “Each criterion must identify an observable result” and “Do not use `appropriate`, `properly`, `reasonable`, or `as needed` without a definition.”

## What it cannot solve

Controlled language reduces ambiguity; it does not establish truth. A sender can produce a perfectly clear but incorrect claim, omit a critical fact, or misclassify a task as complete. Structured-output documentation also warns that schema conformance can coexist with hallucinated content when an input does not fit the schema.[^8]

It also cannot supply shared domain semantics automatically. Both agents must agree on what `verified`, `blocked`, `owner`, and `dependency` mean. FIPA’s older agent-language model separates the message’s performative from its content language and ontology for precisely this reason: parseable syntax is not the same as shared meaning.[^4][^3]

Finally, strict ASD-STE100 vocabulary is probably too restrictive for software agents. Software workflows require technical nouns such as `commit`, `endpoint`, `worktree`, `migration`, and `JSON Schema`. ASD-STE100 itself allows domain-specific technical nouns, but an agent protocol should explicitly register such terms and definitions rather than attempt to eliminate them.[^1]

## A layered protocol

The recommended design is not “make every agent write STE.” It is an **Agent Controlled English protocol** influenced by STE and embedded in a typed workflow.

| Layer | Responsibility | Best representation |
|---|---|---|
| Transport | Delivery, identity, correlation, retries | A2A, HTTP, queue, files, or harness mechanism |
| Envelope | Message type, task ID, sender, recipient, lifecycle state | JSON or YAML validated by schema |
| Controlled semantics | Goal, instructions, constraints, acceptance criteria, blocker explanation | Restricted English fields |
| Evidence | Patches, plans, logs, test reports, design documents | Versioned artifact files with hashes or URIs |
| Workflow | Allowed state transitions, retry limits, approval gates | Deterministic state machine |

This division follows current protocol practice. MCP tool definitions use JSON Schema for inputs and can define output schemas that servers must satisfy and clients should validate. A2A models the task as a stateful unit, gives it a lifecycle, and separates messages from resulting artifacts. Neither typed schemas nor transport protocols alone guarantee semantic alignment; recent protocol research notes that clarification, confirmation, and repair are still often delegated to prompts and application-specific orchestration.[^9][^5][^6][^10]

## Message contract

A useful minimal envelope can contain these fields:

```yaml
protocol: agent-handoff/1.0
message_id: msg-0182
conversation_id: feature-417
in_reply_to: msg-0181
performative: request
sender: orchestrator
recipient: implementer
task_id: task-417-2
state: ready
priority: normal
deadline: null
payload:
  goal: Add cancellation support to the export operation.
  context_refs:
    - artifact://plans/export-cancellation.md
    - git://repo/commit/4a92d3c
  instructions:
    - Modify the export service.
    - Add tests for cancellation before file creation.
    - Add tests for cancellation during file creation.
  constraints:
    - Do not change the public REST contract.
    - Modify files only in src/Export and tests/Export.
  acceptance_criteria:
    - The operation returns HTTP 499 when the client cancels the request.
    - The service deletes each incomplete export file.
    - All Export tests pass.
  response_required:
    performative:
      - inform-result
      - failure
      - request-clarification
```

The `performative` names the intent of the message instead of asking the receiver to infer it from prose. This takes a useful idea from FIPA-ACL, where messages are communicative acts such as `request`, `inform`, `confirm`, and `not-understood`. A small application-specific set is usually better than adopting the full FIPA model:[^3][^4]

- `request`: Perform a task.
- `inform-progress`: Report progress without transferring control.
- `inform-result`: Return a terminal successful result.
- `failure`: Report that the task could not be completed.
- `request-clarification`: Ask for missing or conflicting information.
- `confirm`: Acknowledge an instruction, artifact, or state transition.
- `cancel`: Withdraw a previous request.
- `reject`: Refuse a task because it violates capability, policy, or preconditions.

## Controlled writing rules

An initial rule set should remain small enough to test and enforce. It can borrow the parts of STE that directly improve agent coordination without reproducing its entire dictionary.

### Terminology

1. Use one term for one concept.
2. Define workflow terms in a glossary.
3. Use each state name exactly as specified by the state-machine enum.
4. Do not use a pronoun when two or more antecedents are possible.
5. Use exact identifiers for files, symbols, commands, branches, and artifacts.
6. Do not use unexplained abbreviations.
7. Treat modal verbs as protocol terms: `must` is mandatory, `must not` is prohibited, `may` is permitted, and `should` is recommended.

### Instructions

1. Put one action in each instruction.
2. Start an instruction with an imperative verb.
3. Put a condition before its action: “If the test fails, return `failure`.”
4. State the actor when the responsible agent is not the recipient.
5. Separate goals from instructions. A goal describes the desired outcome; instructions constrain the method.
6. State prohibited actions explicitly.
7. Do not use vague modifiers such as `properly`, `cleanly`, `robust`, `suitable`, or `as necessary` unless the message defines them.

### Results

1. Report observations, not unsupported conclusions.
2. Attach evidence for each completion claim.
3. Distinguish `not_run`, `passed`, `failed`, and `inconclusive`.
4. Report changed artifacts with stable references.
5. Report assumptions in a separate field.
6. Report unresolved risks in a separate field.
7. Do not set `completed` when any mandatory criterion is `failed`, `not_run`, or `inconclusive`.

## Side-by-side examples

| Unrestricted language | Controlled agent language |
|---|---|
| “Take a look at the login issue and fix whatever seems wrong, but try not to break existing behavior.” | **Goal:** Restore login for expired access tokens. **Instruction 1:** Reproduce issue `AUTH-42`. **Instruction 2:** Modify only `TokenRefreshService`. **Constraint:** Do not change login behavior for valid tokens. **Completion:** Return `inform-result` only when all authentication tests pass. |
| “Once that is done, send it to the reviewer and tell them to check it.” | **Condition:** If all acceptance criteria pass, create a review task. **Recipient:** `security-reviewer`. **Artifact:** Attach the patch and test report. **Requested action:** Verify token validation and error handling. |
| “The implementation is basically done; only a few tests might need attention.” | **State:** `blocked`. **Completed:** The implementation is available in commit `8c31f20`. **Failed check:** `RefreshTokenTests.RejectsReusedToken`. **Required decision:** Confirm whether reused tokens must return HTTP 401 or HTTP 403. |
| “Use the new endpoint where appropriate.” | **Condition:** If `ApiVersion` is `v2`, call `/v2/export`. **Otherwise:** Call `/v1/export`. |
| “Make the code more robust.” | Add a timeout of 10 seconds to the outbound request. Retry HTTP 503 responses two times. Do not retry other responses. Return `failure` after the final unsuccessful attempt. |
| “Review the change and let me know if it looks good.” | Compare the patch with acceptance criteria `AC-1` through `AC-4`. Run command `dotnet test Export.Tests`. Return `approve` only if each criterion passes and the command exits with code 0. Otherwise, return `request-changes` with one finding per failed criterion. |

The controlled versions are longer, but they are less expensive operationally because they reduce clarification loops and make validation possible. The goal is not minimal token count; it is minimal **coordination uncertainty**.

## Task and state transfer

Do not transfer an agent’s entire conversational state. Transfer a **task projection**: the smallest authoritative state needed for the next role. A receiving implementer needs the goal, relevant baseline, constraints, acceptance criteria, and artifact references. It usually does not need the planner’s exploratory dialogue or discarded alternatives.

A durable task record could use this shape:

```yaml
task_id: task-417-2
revision: 6
status: blocked
owner: implementer
objective: Add cancellation support to the export operation.
baseline:
  repository: app-server
  commit: 4a92d3c
inputs:
  - artifact://plans/export-cancellation.md
constraints:
  - Do not change the public REST contract.
acceptance_checks:
  - id: AC-1
    statement: The operation returns HTTP 499 after client cancellation.
    verification: integration-test
    result: passed
    evidence: artifact://test-results/run-884.xml
  - id: AC-2
    statement: The service deletes each incomplete export file.
    verification: integration-test
    result: failed
    evidence: artifact://test-results/run-884.xml
blocker:
  code: TEST_FAILURE
  statement: The incomplete file remains after cancellation.
next_action:
  owner: implementer
  statement: Correct cleanup in ExportWriter.DisposeAsync.
```

Important values should be data rather than prose. Put `status`, `owner`, `result`, `priority`, and `blocker.code` in closed enums. Keep prose for content that genuinely requires language, such as the objective or blocker explanation. Schema-constrained output can guarantee field presence, types, and enum validity, although the runtime must still validate evidence and truth.[^11][^8]

Use optimistic concurrency through `revision` or an ETag so that an agent cannot overwrite newer state. Use stable IDs for tasks, criteria, messages, and artifacts. Keep history append-only where auditability matters. Let the orchestrator—not a worker’s prose—authorize workflow transitions.

## Clarification and repair

A protocol must define what an agent does when a message is incomplete. Otherwise, the model will often guess. The default rule should be:

> If a missing fact can change the selected action or acceptance result, do not infer the fact. Return `request-clarification`.

A clarification should identify the exact defect and offer bounded alternatives:

```yaml
performative: request-clarification
task_id: task-417-2
issue_code: CONFLICTING_REQUIREMENTS
statement: AC-2 requires file deletion, but constraint C-4 requires retention for diagnostics.
questions:
  - Select the rule that has priority: AC-2 or C-4.
work_completed:
  - Reproduced the cancellation path.
work_paused_at: ExportWriter.DisposeAsync
```

This repair mechanism is as important as the controlled language. Current protocol analysis finds that many systems can transmit and parse messages but provide limited support for clarification, confirmation, and semantic repair. A reliable workflow therefore treats `request-clarification`, `not-understood`, and `conflict` as normal protocol outcomes rather than agent failures.[^10]

## Validation strategy

Validation should occur at several levels:

1. **Schema validation:** Required fields, types, enum values, and unknown-field rejection.
2. **Controlled-language linting:** Sentence length, prohibited vague terms, ambiguous pronouns, multiple imperative verbs, and inconsistent terminology.
3. **Semantic validation:** Every acceptance criterion has a verification method; every completion claim has evidence; every referenced artifact exists.
4. **Transition validation:** Only permitted state changes occur, such as `running -> blocked` or `running -> completed`.
5. **Independent verification:** A reviewer or deterministic test checks important claims before the orchestrator commits the transition.

MCP’s distinction between input schema, output schema, and client-side validation is a useful precedent for the first layer. The later layers must remain application-specific because syntactic conformance cannot determine whether a patch satisfies a requirement.[^9]

A practical linter can flag phrases such as:

- `as needed`
- `if possible`
- `handle appropriately`
- `make sure it works`
- `the relevant files`
- `some tests`
- `should be fine`
- `probably complete`
- `etc.`
- pronouns with multiple possible antecedents

The linter should not automatically rewrite safety-critical semantics without review. A rewrite can silently change scope or obligation. It should report a rule ID, location, explanation, and proposed alternative.

## Where to apply it

Use strict controlled language at **interfaces between contexts**, not everywhere:

- Orchestrator-to-worker task assignment
- Worker-to-orchestrator terminal result
- Planner-to-implementer specification
- Implementer-to-reviewer review request
- Agent-to-human approval request
- Persisted checkpoint and recovery record
- Tool descriptions and parameters

Use ordinary technical prose for brainstorming, exploratory reasoning, design discussion, and large explanatory artifacts. Forcing every thought into controlled language can remove useful nuance, increase verbosity, and create an illusion of precision. The handoff should be strict; the attached design document can remain expressive.

This also aligns with the previously considered hybrid of built-in messages and file artifacts: use the messaging channel for small coordination events, but place plans, research, patches, and verification reports in durable files. Controlled messages should point to those artifacts rather than copy their complete contents.[^12]

## Recommended rollout

### Phase 1: Observe

Collect real handoffs and classify failures: missing input, unclear actor, ambiguous completion, terminology drift, stale state, unsupported claim, or lost artifact. Do not design a large dictionary before observing actual failure patterns.

### Phase 2: Define

Create:

- 6–10 performatives
- A task lifecycle with explicit terminal states
- A glossary of 20–50 workflow terms
- A minimal message schema
- 10–15 controlled-writing rules
- A clarification protocol

### Phase 3: Enforce

Generate messages through structured output where the selected model and harness support it. Validate the schema, then run a semantic linter. Reject invalid handoffs or route them back to the sender for repair. Structured output is preferable to plain JSON mode because plain JSON mode guarantees parseability but not conformance to a particular schema.[^13][^8]

### Phase 4: Evaluate

Compare unrestricted and controlled handoffs on:

- Task-success rate
- Clarification count
- Incorrect state-transition count
- Missing-evidence count
- Rework caused by misunderstood scope
- Tokens and latency per successful task
- Agreement between implementer and reviewer

The correct objective is not “maximum STE compliance.” It is fewer semantic defects per successful handoff. Rules that add verbosity without reducing failures should be removed.

## Architectural recommendation

For a multi-agent coding workflow, the most robust arrangement is:

1. A deterministic orchestrator owns task state and transition rules.
2. Each agent receives a versioned task projection, not an inherited conversation.
3. JSON Schema defines the envelope and closed-value fields.
4. A small STE-inspired language defines how prose fields are written.
5. Stable artifact references carry plans, patches, logs, and reports.
6. Every terminal result includes criterion-level evidence.
7. Ambiguity produces `request-clarification`, not an inferred decision.
8. A verifier checks consequential claims before the workflow advances.

The essential insight is that restricted English is best viewed as the **semantic interface definition language** between agents. It occupies the layer between rigid schemas and unrestricted prose. Used there, it can make handoffs more readable to humans, more predictable for models, easier to lint, and safer to evolve without pretending that natural language has become formally unambiguous.

---

## References

1. [ASD-STE100 Simplified Technical English](https://www.asd-ste100.org/assets/files/ASD-STE100_ISSUE9.pdf) - Explanatory text revised to include the definitions of technical nouns. (noun terms) and technical v...

2. [ABOUT STE - ASD-STE100](https://www.asd-ste100.org/about_STE.html) - Discover Simplified Technical English (ASD-STE100): a controlled language that improves clarity, red...

3. [Agent Communication Language](http://www.fipa.org/specs/fipa00018/OC00018.pdf)

4. [Standards and Interoperability](https://site.ieee.org/pes-mas/agent-technology/standards-and-interoperability/)

5. [Announcing the Agent2Agent Protocol (A2A)](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/) - Explore A2A, Google's new open protocol empowering developers to build interoperable AI solutions.

6. [Agent2Agent (A2A) Protocol Specification](https://a2a-protocol.org/v0.2.5/specification/) - An open protocol enabling communication and interoperability between opaque agentic applications.

7. [How does the orchestrator know in which state an item is? As an examle, when the coder writes new code, how does he know when to stop, and how does the orchestrator know when to pick up its work again?](https://www.perplexity.ai/search/a9b4ca6e-e53c-4cc9-b0a5-55f739e118ae) - Great question — this gets to the heart of the control flow mechanism between agents. There are seve...

8. [Structured model outputs | OpenAI APIplatform.openai.com › docs › guides › structured-outputs](https://platform.openai.com/docs/guides/structured-outputs) - Understand how to ensure model responses follow specific JSON Schema you define.

9. [Tools](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)

10. [Beyond Message Passing: Toward Semantically Aligned Agent ...](https://arxiv.org/html/2604.02369v1)

11. [openai.com › index › introducing-structured-outputs-in-the-apiIntroducing Structured Outputs in the API - OpenAI](https://openai.com/index/introducing-structured-outputs-in-the-api/) - We are introducing Structured Outputs in the API—model outputs now reliably adhere to developer-supp...

12. [Before we touch on the topic of concrete AGENTS.md files, can we talk about the message-passing protocol between sub-agents first? Is it good practice to pass messages like prompts and results between sub-agents through built-in mechanism? Can files be used instead? What are the pros and cons, and what would be a good file format?](https://www.perplexity.ai/search/6e3dad83-c5ee-4778-9c66-4fe29477d462) - Yes — both built-in message passing and file-based handoff are valid, and the best choice depends on...

13. [Structured Outputs - OpenAI API](https://platform.openai.com/docs/guides/json-mode) - Understand how to ensure model responses follow specific JSON Schema with OpenAI's Structured Output...

