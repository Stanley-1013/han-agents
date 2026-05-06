# HAN Harness Roadmap

HAN already provides local orchestration, memory, task state, and a code graph.
The next maturity step is to make every agent workflow observable, replayable,
and regression-testable.

## Principles

- Record every workflow as a trace with spans for dispatch, tool calls,
  validation, memory writes, and failures.
- Keep deterministic evals in CI for fast regression checks before adding
  LLM-as-judge evals.
- Treat Critic results as quality signals, not a substitute for tests,
  trajectory checks, and human review on high-risk changes.
- Keep sandbox and permission policy explicit at workflow boundaries.

## Current Baseline

- `servers.tracing` stores provider-neutral traces and spans in SQLite.
- `servers.evals` supports deterministic exact and subsequence trajectory
  scoring for static datasets, stored traces, and exported JSONL traces.
- `get_next_dispatch(..., trace_id=...)` records dispatch/status decisions with
  prompts redacted from span output.
- `evals/trajectories.json` provides the built-in golden trajectory dataset,
  runnable with `python cli/main.py eval`.
- `servers.guardrails` defines provider-neutral agent policies and deterministic
  path/command checks; dispatch prompts include concise policy blocks.
- `hooks/pre_tool.py` denies or asks on risky Bash/Write/Edit events before
  execution in hosts that support PreToolUse decisions.
- `hooks/post_task.py` observes Task lifecycle plus post-tool Bash/Write/Edit
  events where available, emitting guardrail context and local guardrail spans
  when `TRACE_ID` is present.
- `python cli/main.py traces` lists local traces and guardrail events.
- `python cli/main.py guard` provides policy preflight checks for commands and
  paths with non-zero exit codes on violations.
- Guardrail enforcement supports `warn` and `block` modes through
  `HAN_GUARDRAIL_MODE` or `python cli/main.py guard --mode ...`.
- `python cli/main.py traces --export-jsonl <path>` exports local traces as
  JSONL for external processors.
- `python cli/main.py traces --export-otel-jsonl <path>` exports
  OpenTelemetry-style span JSONL using GenAI attributes where they fit and
  `han.*` attributes for local harness concepts.
- `python cli/main.py eval --trace <trace_id> --expected executor,critic`
  evaluates a recorded workflow dispatch sequence.
- `human_review_queue` stores durable review records for blocked tasks,
  warning/error trace spans, and guardrail violations tied to a task or trace.
- `schema_migrations` records the local schema version, and numbered SQL files
  in `migrations/` are applied by `python cli/main.py migrate`.
- The existing pytest suite is the first CI gate for code graph, drift,
  memory, facade, and extractor behavior.

## Next Steps

1. Add direct OTLP/OpenAI/LangSmith exporters if a deployment needs push-based
   telemetry instead of JSONL handoff.
2. Add host-specific integration tests for pre-tool blocking semantics.
3. Add retention/archival policy for traces and resolved review items.
4. Add LLM-as-judge evals after deterministic CI remains stable.
