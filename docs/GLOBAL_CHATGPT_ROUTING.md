# Global ChatGPT routing

## Cloud-first default

Repository-backed work uses GitHub plus Codex Cloud by default. The selected
cloud environment checks out one exact branch or commit, loads the repository's
`AGENTS.md`, edits and tests in an isolated container, then returns a reviewable
diff. A dedicated remote branch or pull request plus observed CI is the durable
result.

This route has no dependency on an awake Windows host, Tailscale Funnel,
Cloudflare relay Worker, DevSpace, Oracle browser profile, or local Bridge.

Route a task to cloud when all required source bytes are committed to GitHub and
the work can run with repository dependencies, configured environment values,
and cloud-compatible tests. A local dirty working tree is never implicit input:
use `synchronize-to-explicit-backup-branch-or-block` before starting cloud work.

## Explicit local-only lane

Select the explicit local-only lane only when the user needs unpublished local
files, a signed-in desktop application or browser session, or exact persisted-run
recovery. This lane requires the host to remain awake,
online, and healthy.

The supported local English names are `GPT`/`direct`, `plan`, `review`, `edit`,
`orchestrator`, `deep research`/`deep-research`, `Web Multi-GPT`,
`comprehensive mode`, and `Pro`. Korean names documented in the main README map
to the same runners; language never selects a different backend.

- New regular local browser work uses Oracle + DevSpace through the manually registered
  DevSpace app.
- Regular local work selects `GPT-5.6 Sol` with Oracle `heavy` and verifies the
  visible `Extra High` tier. It does not silently fall back to High or another
  model.
- The local composer contains only `@DevSpace` and an absolute UTF-8 mission
  path. It does not attach the task body or mutate ChatGPT app settings per task.
- Explicit local Pro uses Oracle attachment-only and no DevSpace or CodexPro app.
- Existing persisted agbrowse and CodexPro runs remain exact recovery-only.
  There is no new agbrowse submission path or Oracle-to-agbrowse fallback.
- Comprehensive stages author the next semantic mission and a bound hash
  receipt. The local host owns transport, immutable identity, host safety, and
  one final deterministic gate rather than rewriting web output.
- Genuine local Web Multi-GPT uses distinct Oracle sessions with independent
  throwaway copies of the signed-in profile, in waves of at most five.

## PC-off acceptance

A repository is cloud-ready only after a task succeeds while the Windows host
and its Bridge/Funnel are unavailable: checkout an exact GitHub branch, read the
applicable instructions, make a harmless test-branch change, run declared tests,
push the branch, open a pull request, and observe CI on the exact commit.

Bridge health, HTTP 200, a local test, or an unpushed branch does not satisfy
this acceptance. See [Cloud-first operations](CLOUD_FIRST_OPERATIONS.md).

## Standalone Pro versus local comprehensive

`chatgpt-pro-browser` is the explicit local standalone Pro route. It submits one
attachment-only Oracle Pro session, saves the durable result, returns it to the
calling local Codex task, and stops.

`chatgpt-pro-plan-handoff` owns explicit local comprehensive mode. Only that
staged runner may place an optional Pro decision between plan and review and
continue afterward to implementation and gates. Natural-language `Pro` or
`GPT Pro` requests do not override the cloud-first default unless the user asks
for the local browser route or requires local-only evidence.

## Local orchestrator versus local comprehensive

| | `orchestrator` | comprehensive |
|---|---|---|
| Runner | `chatgpt_oracle_dispatch.py --mode orchestrator` | `chatgpt_oracle_comprehensive.py` |
| Browser submissions | one | several, one per stage |
| Stage receipts | none | hash-bound per workflow/stage/attempt/input |
| Independent review | no | yes, review repairs and finalizes the plan |
| Pro / Web Multi stage | not available | selectable |
| Completion | the answer itself | final web PASS plus zero-exit local gate |
| Recovery unit | one run | workflow plus stage identity |

These are optional local browser modes, not fallbacks from a failed cloud task.
If the cloud environment is misconfigured, repair or block the cloud task. Do
not silently wake or depend on the user's PC.
