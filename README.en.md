# Codex Web GPT Orchestrator

English | [한국어](README.md)

A cloud-first operations toolkit that uses GitHub as the source of truth and
Codex Cloud for planning, changes, tests, and pull requests. The default execution lane is Codex Cloud,
so repository work can continue when the PC is off.

The existing Windows Oracle and DevSpace automation remains available as an
explicit local-only lane for unpublished local files, signed-in desktop apps,
and exact recovery of persisted runs.

The optional local lane connects two upstream tools:

- [Oracle](https://github.com/steipete/oracle) creates signed-in ChatGPT browser
  sessions, selects the model, waits for the response, and harvests the result.
- [DevSpace](https://github.com/Waishnav/devspace) lets ChatGPT read, edit, and
  run commands only inside project roots approved by the user.

Regular cloud work starts from a GitHub branch or commit and returns a
reviewable diff and pull request. Only an explicitly selected local run sends
`@DevSpace` and an absolute UTF-8 mission-file path through Oracle.

## What it provides

- PC-independent checkout, changes, tests, pull requests, and CI evidence.
- Fail-closed migration of a local dirty tree to an explicit backup branch.
- Web GPT can inspect, change, and test a local project.
- Luna can supervise, verify, and record serialized Web GPT implementation and
  send failed checks back to Web GPT for remediation.
- Direct, plan, review, edit, orchestrator, deep-research, and Pro modes.
- Genuine Web Multi-GPT with independent ChatGPT sessions.
- Read-only Local Multi-GPT with parallel Codex lanes on the PC.
- Comprehensive workflows from planning through implementation and final gate.
- Per-project exclusion, immutable mission and attachment hashes, and exact
  session recovery.
- Isolated browser profiles so different projects can run concurrently.
- Automatic archive lifecycle for conversations owned by Oracle.
- Install receipts, backups, rollback, and uninstall support.

## How it works

```text
User request
    -> select an exact GitHub branch or commit
    -> Codex Cloud checks out the repo and loads AGENTS.md
    -> explore, edit, test, and review the diff in the cloud
    -> push a dedicated branch and open a pull request
    -> observe CI on the exact commit
```

Tasks that require local-only bytes or desktop sessions branch to Oracle +
DevSpace. State for that optional lane is stored outside DevSpace projects under
`%USERPROFILE%\.codex\state\chatgpt-oracle`.

## Modes and English invocation names

| Mode | CLI / natural-language name | Purpose | Transport |
|---|---|---|---|
| Cloud default | Codex Cloud / Cloud Work | Repository planning, implementation, tests, and PR | GitHub + isolated cloud environment |
| Regular GPT | `direct` / GPT | Questions, analysis, and small tasks | Oracle + DevSpace |
| Plan | `plan` / plan | Design before implementation | Oracle + DevSpace, read-only |
| Review | `review` / review | Independent code or plan review | Oracle + DevSpace, read-only |
| Edit | `edit` / edit | Scoped changes and tests | Oracle + DevSpace |
| Orchestrator | `orchestrator` / orchestrator | One GPT completes an already-scoped task | Oracle + DevSpace |
| Deep Research | `deep-research` / deep research | Public research plus project evidence | Oracle Deep Research + DevSpace |
| Web Multi-GPT | Web Multi-GPT | Independent parallel perspectives and merger | 2-25 Oracle sessions |
| Local Multi-GPT | Local Multi-GPT | Local advisory synthesis and counterexample search | Fixed `gpt-5.6-luna` + `max`, read-only |
| Luna continuous command | `$luna-web-supervisor` / continuous command mode | Serialize, verify, and record Web GPT implementation; return failed checks to Web GPT | Luna `high` supervisor + Oracle DevSpace Sol Extra High |
| Comprehensive | comprehensive mode | Plan, optional Pro/Multi, review, implementation, gate | Staged Oracle workflow |
| Pro | `pro` / Pro | Independent final judgment or design review; result only | Oracle attachments only |

Orchestrator mode is a single web submission. Comprehensive mode contains an
orchestrator-equivalent implementation stage plus planning, independent review,
optional Pro or Web Multi-GPT, and final gates.

Standalone Pro is a one-shot review route, separate from comprehensive mode. It
reviews the attached plan, code, or document, returns the durable result, and
stops; it never transitions automatically into implementation or another stage.
Use comprehensive mode only when the work must continue from planning through
implementation and gates.

Local Multi-GPT and Web Multi-GPT are separate paths. Local Multi-GPT is an
optional advisory tool that runs Codex child lanes on the PC. Every stage is
fixed to `gpt-5.6-luna` with `max` reasoning; any other model or effort is
rejected before a child process starts. Web Multi-GPT instead runs independent
ChatGPT web sessions through Oracle and merges their results.

Every Oracle mode in this table is part of the optional local lane. A failed
cloud task must not silently fall back to the user's PC.

## Requirements

Cloud default lane:

- A GitHub-synchronized repository
- A Codex Cloud environment with access to that repository
- Repository `AGENTS.md` plus cloud-compatible tests and CI

Optional local lane:

- Windows 11
- Python
- Node.js 22.19 or later and earlier than 27
- Git for Windows / Git Bash
- Tailscale
- An Oracle browser profile signed in to ChatGPT
- One manually registered DevSpace app in ChatGPT Developer Mode

The validated combination is Oracle `0.16.1` and DevSpace `1.0.4`. The installer
applies Windows compatibility patches only when exact upstream file hashes
match.

## Install the optional Windows lane

```powershell
git clone https://github.com/ventianima-lab/codexpro-automation.git
cd codexpro-automation
.\install.ps1 -WhatIf
.\install.ps1
```

The installer backs up replaced files and writes durable install receipts under
`%USERPROFILE%\.codex\receipts`.

## Optional one-time DevSpace setup

You do not install one ChatGPT app per project. Register one DevSpace app and
add each permitted project as another `--root` argument.

```powershell
python skills/chatgpt-workspace-setup/scripts/devspace_tailscale_setup.py setup `
  --root C:\projects\alpha `
  --root C:\projects\beta `
  --hostname your-device.your-tailnet.ts.net `
  --public-port 8443 `
  --dry-run
```

Review the output, then replace `--dry-run` with `--apply`. In ChatGPT Developer
Mode, manually register one app:

- Name: `DevSpace`
- URL: `https://your-device.your-tailnet.ts.net:8443/mcp`

After owner approval, the automation does not inspect or manipulate ChatGPT
settings, app lists, permissions, deletion, or picker UI per task. Adding a new
project only changes the DevSpace allowed roots.

See [DevSpace and Tailscale setup](docs/DEVSPACE_TAILSCALE_SETUP.md) for the
complete procedure.

## Regular GPT example

Create a UTF-8 mission file inside the project, then dry-run the manifest:

```powershell
python "$env:USERPROFILE\.codex\bin\chatgpt_oracle_dispatch.py" `
  --mode orchestrator `
  --project-root C:\project `
  --mission-path C:\project\mission.md `
  --manifest-output C:\project\.ai-bridge\oracle.json `
  --reasoning-level "Very High" `
  --dry-run
```

Remove `--dry-run` only when the run is authorized.

## Luna continuous command mode

`$luna-web-supervisor` is an explicit route separate from the unchanged
`$web-gpt` one-shot contract. The Codex task must be proven to run
`gpt-5.6-luna` with `high` reasoning and may not edit product source. Luna
serializes one Web GPT run at a time, recovers only its exact Oracle slug,
checks the declared Git and test contract, and reads back the existing Notion
record before advancing.

If the source checkout is dirty, the supervisor never stashes or resets it.
With explicit authorization for a separate Luna task, it carries the current
working-tree state into an isolated Codex worktree task and starts only from a
clean boundary there. An explicit request to auto-fill Notion targets selects
the single linked Task and Report for the same project only when both permit AI
access. Luna uses `high`; visible `Extra High` applies only to Web GPT Sol.

Oracle state `mode=browser` identifies the foundation browser runner, while
`dispatch_mode=orchestrator` preserves the semantic command contract. The
supervisor validates both instead of conflating them. If the private login
profile fails before the composer, only a classified no-submission incident
can preserve the attempt as `PRE_SUBMIT_FAILED` and unlock a new reservation;
the failed run itself is never resubmitted.

On a remediable validation failure, Luna does not fix the code. It freezes the
failure log, current commit, and allowed paths into a new remediation mission,
records and reads back that attempt, then asks a new Web GPT run to diagnose,
edit, test, and commit the correction. Per-unit `max_web_attempts` and the
manifest's total submission ceiling prevent an unbounded loop. See
[`skills/luna-web-supervisor/SKILL.md`](skills/luna-web-supervisor/SKILL.md)
for the state transitions and exact commands.

## Pro example

Pro uses no project app. It attaches the exact mission and evidence files with
frozen hashes.

```powershell
python "$env:USERPROFILE\.codex\bin\chatgpt_oracle_dispatch.py" `
  --mode pro `
  --project-root C:\project `
  --mission-path C:\project\pro.md `
  --attachment C:\project\evidence.zip `
  --manifest-output C:\project\.ai-bridge\pro.json `
  --dry-run
```

## Execution and recovery rules

- One active or uncertain Oracle workflow is allowed per normalized project.
- Different projects can run concurrently through isolated profiles.
- Web Multi-GPT runs child sessions in waves of at most five.
- Heavy non-Pro work receives about 90 minutes initially and another 90 minutes
  for exact recovery, for an effective ceiling of roughly 180 minutes.
- A browser or local-process exit is not proof that the web task failed.
- Recovery uses only the persisted Oracle slug and exact conversation URL. It
  never resubmits the task.
- Completion requires Oracle exit code zero and a fresh, nonempty durable output.

Recover one exact run with:

```powershell
python "$env:USERPROFILE\.codex\bin\chatgpt_oracle_run.py" recover `
  --run-dir C:\exact\oracle-run `
  --action harvest
```

## Update, rollback, and uninstall

```powershell
.\install.ps1 -WhatIf
.\install.ps1
.\rollback.ps1
.\uninstall.ps1
```

Use `-InstallLegacyRecoveryDependency` only on a machine that must recover an
already persisted legacy run.

## Documentation

- [PC-independent cloud-first operations](docs/CLOUD_FIRST_OPERATIONS.md)
- [Global ChatGPT routing and mode selection](docs/GLOBAL_CHATGPT_ROUTING.md)
- [DevSpace and Tailscale setup](docs/DEVSPACE_TAILSCALE_SETUP.md)
- [Technical changelog](docs/CHANGELOG.md)
- [Frozen legacy recovery assets](docs/FROZEN_LEGACY.md)
- [Release checklist](docs/RELEASE_CHECKLIST.md)
- [Security policy](SECURITY.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)

## Legacy compatibility

The former CodexPro and agbrowse files remain only for exact recovery of already
persisted legacy runs. They are not a new-work route or fallback. See
[Frozen legacy assets](docs/FROZEN_LEGACY.md) for the inventory.

## License

MIT License. Third-party copyrights and licenses for Oracle, DevSpace, and other
components are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
