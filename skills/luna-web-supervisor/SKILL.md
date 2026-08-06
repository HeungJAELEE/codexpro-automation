---
name: luna-web-supervisor
description: Explicit-only continuous command mode in which a gpt-5.6-luna Codex task supervises a bounded sequence of Oracle DevSpace Web GPT implementation runs, validates and records each result, and sends failed validation evidence back to Web GPT for bounded remediation without editing product source itself. Use only when the user explicitly invokes $luna-web-supervisor or asks to start the separate continuous Luna supervisor route.
---

# Luna Web Supervisor

Use this skill only after explicit invocation. It is the separate **연속 지휘모드**
route; it does not change or weaken `web-gpt`.

The division of labor is fixed:

- **Web GPT** explores, judges, edits product source, runs its own tests, and
  creates the authorized local commit.
- **Luna** submits one exact unit at a time, watches or recovers that exact
  Oracle run, runs deterministic verification, records the result, and advances
  the sequence.
- When verification fails, **Luna does not repair code**. It freezes the
  failure evidence into a remediation mission, records and reads back that
  failure, then sends the remediation mission to a new Web GPT run inside the
  same unit.

## Activation gate

An invocation such as `$luna-web-supervisor` activates this workflow. Ordinary
requests, a large project, or mention of Luna/Web GPT do not activate it.

Before any live submission:

1. Confirm the current Codex task is actually `gpt-5.6-luna` with `high`
   reasoning from surfaced runtime metadata. Do not infer this from the skill
   name or manifest. If it cannot be proven, report
   `LUNA_SUPERVISOR_MODEL_UNCONFIRMED` and do not submit.
2. Read `chatgpt-question-designer` and `chatgpt-thinking-browser` completely.
   Reuse their current Oracle + DevSpace transport and exact-recovery rules.
3. Confirm the user authorized one exact project, ordered unit list, maximum
   Web attempts per unit, total live-submission ceiling, local-commit boundary,
   and recording targets. If any of these is missing, prepare a draft manifest
   and dry-run only.
4. Confirm every Notion URL is necessary, permitted for AI access, and limited
   to the approved project. Never copy a whole conversation, secret, cookie,
   credential, or unrelated Notion content.

The explicit supervisor invocation authorizes only the frozen manifest. It does
not authorize push, PR, deployment, permission changes, destructive Git
operations, or a different project.

## Hard role boundary

Luna may:

- read project files and applicable rules;
- write host-only supervisor state;
- write ignored operational missions/checkpoints below the manifest's exact
  `.ai-bridge` checkpoint directory;
- run the manifest's exact verification commands;
- update the exact existing Notion records and read them back;
- submit and recover the exact serialized Oracle runs.

Luna must not:

- edit product source, tests, configuration, schema, dependencies, or lockfiles;
- create the product commit, amend/rebase/reset history, push, open a PR, or
  deploy;
- silently broaden an allowed file set or validation command;
- replace an uncertain Oracle submission with a new conversation;
- treat its own judgment as a substitute for deterministic verification.

If a Luna verification command changes tracked or untracked project state, stop
with `VALIDATION_MUTATED_SOURCE`; do not clean or reset it automatically.

## Freeze the batch

Copy `references/manifest.example.json` into the approved project's ignored
`.ai-bridge` directory and replace every placeholder. Validate against
`references/manifest.schema.json`; the Python helper is the authoritative
semantic validator.

Each manifest must fix:

- the exact Git root and ordered unit IDs;
- one pre-existing, nonempty mission file per unit;
- `max_web_attempts` from 1 to 10 per unit;
- total `live_submission_limit` equal to the sum of those attempt limits;
- Web GPT as Oracle DevSpace `orchestrator`, `GPT-5.6 Sol`, visible
  `Extra High`, concurrency 1;
- Luna as `gpt-5.6-luna/high`, `source_writes: false`;
- allowed outcomes (`completed`, `hold`, `choice_issue`);
- commit policy, exact net changed paths, and argv-based verification commands
  for each outcome;
- exact Notion/record targets and an ignored project checkpoint directory;
- expiry within 30 days, request fingerprint, `push: false`, and
  `deploy: false`.

`HOLD` and `CHOICE_ISSUE` are valid continuable outcomes only when declared in
that unit. Their final net diff must match their frozen outcome contract.

Resolve one repository-authoritative Python executable and keep using it:

```powershell
$LunaSupervisorPython = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'
& $LunaSupervisorPython "$env:USERPROFILE\.codex\skills\luna-web-supervisor\scripts\supervisor_state.py" prepare `
  --manifest C:\exact-project\.ai-bridge\supervisor.json
```

`prepare` requires the exact Git root to be clean, freezes all mission hashes,
checks that the checkpoint directory is Git-ignored, and stores durable state
under `%USERPROFILE%\.codex\state\luna-web-supervisor`.

## Continuous unit loop

Always begin or resume with:

```powershell
& $LunaSupervisorPython "$env:USERPROFILE\.codex\skills\luna-web-supervisor\scripts\supervisor_state.py" status `
  --manifest C:\exact-project\.ai-bridge\supervisor.json
```

Follow only the returned `next_action`.

### 1. Preview and reserve

For the current original or remediation mission, run the existing dispatcher
with `--mode orchestrator`, `--reasoning-level "Very High"`, and `--dry-run`.
Review the preview, hash the exact preview artifact, then reserve:

```powershell
$OraclePreview = 'C:\exact-project\.ai-bridge\oracle-preview.json'
& $LunaSupervisorPython "$env:USERPROFILE\.codex\bin\chatgpt_oracle_dispatch.py" `
  --mode orchestrator `
  --project-root C:\exact-project `
  --mission-path C:\exact-project\.ai-bridge\current-exact-mission.md `
  --manifest-output $OraclePreview `
  --reasoning-level "Very High" `
  --dry-run
$OraclePreviewHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $OraclePreview).Hash

& $LunaSupervisorPython "$env:USERPROFILE\.codex\skills\luna-web-supervisor\scripts\supervisor_state.py" reserve `
  --manifest C:\exact-project\.ai-bridge\supervisor.json `
  --unit-id session-02 `
  --preview-sha256 $OraclePreviewHash
```

Reservation is written before live submission so a crash cannot cause an
untracked duplicate. After reservation, rerun that exact dispatcher command
once with a fresh `--manifest-output` and without `--dry-run`. Do not invoke
`web-gpt` recursively: its one-shot authority remains separate and unchanged.

### 2. Bind the exact Oracle run

Record the returned run directory and one textual Oracle evidence file that
contains both `GPT-5.6 Sol` and `Extra High`:

```powershell
& $LunaSupervisorPython "$env:USERPROFILE\.codex\skills\luna-web-supervisor\scripts\supervisor_state.py" submitted `
  --manifest C:\exact-project\.ai-bridge\supervisor.json `
  --unit-id session-02 `
  --run-dir C:\exact-host-oracle-run `
  --display-proof-file C:\exact-host-oracle-run\stdout.log
```

If the live command times out or becomes uncertain, recover only that recorded
run and stored slug. Never create a replacement submission. Use the current
Oracle runtime's own wait and recovery budgets; this skill does not alter them.

### 3. Freeze the durable result

Only Oracle state `complete`, exit code 0, the same slug, and the exact nonempty
`output.md` may advance:

```powershell
& $LunaSupervisorPython "$env:USERPROFILE\.codex\skills\luna-web-supervisor\scripts\supervisor_state.py" result `
  --manifest C:\exact-project\.ai-bridge\supervisor.json `
  --unit-id session-02 `
  --result-path C:\exact-host-oracle-run\output.md
```

### 4. Verify without repairing

Select only the outcome actually supported by the Web result:

```powershell
& $LunaSupervisorPython "$env:USERPROFILE\.codex\skills\luna-web-supervisor\scripts\supervisor_state.py" verify `
  --manifest C:\exact-project\.ai-bridge\supervisor.json `
  --unit-id session-02 `
  --outcome completed
```

The helper proves clean Git state, forward non-merge history, allowed paths,
the outcome's exact cumulative net diff, and every declared command. Logs stay
in host state.

### 5A. Successful verification

Append the human-readable checkpoint to every frozen record target: why the
unit existed, what Web GPT changed, selected outcome, commits, exact paths,
tests, retries, remaining risks, and what the user should know. Fetch the
records again, hash the relevant canonical readback, then call `record`:

```powershell
& $LunaSupervisorPython "$env:USERPROFILE\.codex\skills\luna-web-supervisor\scripts\supervisor_state.py" record `
  --manifest C:\exact-project\.ai-bridge\supervisor.json `
  --unit-id session-02 `
  --record-ref https://app.notion.com/p/exact-approved-record `
  --readback-fingerprint <sha256> `
  --summary "Session 02 completed; exact paths and checks were read back."
```

Only this transition unlocks the next unit.

### 5B. Failed verification and Web remediation

For a remediable missing change, missing commit, required reversion, or failed
test, `verify` returns `WEB_REMEDIATION_REQUIRED` and writes an ignored,
hash-frozen remediation mission. It includes the failure, log excerpt, current
commit, exact allowed paths, deterministic checks, and Web-owned correction
contract.

First append the failed attempt and remediation decision to the frozen record
targets and read them back. Then call:

```powershell
& $LunaSupervisorPython "$env:USERPROFILE\.codex\skills\luna-web-supervisor\scripts\supervisor_state.py" record-remediation `
  --manifest C:\exact-project\.ai-bridge\supervisor.json `
  --unit-id session-02 `
  --record-ref https://app.notion.com/p/exact-approved-record `
  --readback-fingerprint <sha256> `
  --summary "Attempt 1 failed validation; evidence and remediation mission were read back."
```

Status now returns `REMEDIATION_READY`. Preview, reserve, and submit that exact
remediation mission as a new serialized Web GPT run. Web GPT—not Luna—must
diagnose, edit, test, and commit. Repeat until verification passes or the
unit's frozen attempt budget is exhausted.

## Stop conditions

Stop and preserve state when:

- Luna model/effort, Sol model, or visible Extra High cannot be proven;
- submission ownership, slug, result identity, or mission hash is uncertain;
- Web GPT touches a path outside every authorized outcome;
- the worktree is dirty at a boundary or history diverges;
- a Luna validation command mutates project state;
- the attempt budget or authorization expiry is reached;
- record update/readback is missing;
- Web GPT reports a decision that changes scope, permissions, architecture,
  dependency policy, or external effects.

These cases require a new user decision or a newly authorized manifest. Never
repair around them locally.

## Completion report

Report the exact completed/remaining/blocked unit counts, Web attempts per unit,
final commits, verified commands, record URLs/readback status, and any pending
push/deploy gate. Say explicitly that Luna supervised and recorded the work but
did not author product changes.
