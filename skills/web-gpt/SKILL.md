---
name: web-gpt
description: Run regular non-Pro Web GPT through the installed Oracle and manually registered DevSpace workspace for direct answers, plans, adversarial reviews, bounded edits, orchestrator execution, or deep research. Use only when the user explicitly invokes `$web-gpt`, `/웹gpt`, or asks for a `웹 GPT` mode. Keep `$gpt`, ChatGPT Pro, comprehensive mode, Web Multi-GPT, and Local Multi-GPT on their existing separate routes.
---

# 웹GPT

Use the installed regular Web GPT path without changing or duplicating the
existing GPT, Pro, comprehensive, or Multi-GPT skills.

## Boundary

- Treat invocation as explicit opt-in to the Oracle + DevSpace lane.
- Keep `$gpt` and ChatGPT Pro attachment-only review completely separate.
- Never start comprehensive mode, Web Multi-GPT, or Local Multi-GPT from this
  skill.
- Never inspect, select, register, repair, or delete a ChatGPT app during a
  task. Use the already registered `DevSpace` app.
- Preserve the current user request, the nearest repository `AGENTS.md`, and
  every approval, security, privacy, release, and destructive-action gate.

## Select the mode

Map the user's explicit wording to exactly one mode:

| User wording | Mode | Authority |
|---|---|---|
| 질문, 답변, 분석, `direct` | `direct` | Read-only answer |
| 계획, 설계, `plan` | `plan` | Read-only plan |
| 검토, 적대적 검토, `review` | `review` | Read-only adversarial review |
| 수정, 고쳐줘, `edit` | `edit` | Bounded project write and tests |
| 지휘, 구현까지, `orchestrator` | `orchestrator` | Mission-owned project execution |
| 심층 리서치, `deep-research` | `deep-research` | Read-only deep research |

If the invocation contains no mode, use `direct`. If it requests Pro,
comprehensive, Web Multi-GPT, or Local Multi-GPT, do not reinterpret or chain
the request. Explain that those remain separate skills and ask the user to
invoke the intended route explicitly.

## Execute

1. Resolve one exact absolute project root from the current task or the user's
   explicit path. Read the applicable repository instruction chain before
   authoring the mission.
2. Read the installed
   `%USERPROFILE%\.codex\skills\chatgpt-question-designer\SKILL.md` completely.
3. For `direct`, `plan`, `review`, `edit`, or `orchestrator`, read and apply
   `%USERPROFILE%\.codex\skills\chatgpt-thinking-browser\SKILL.md`.
   For `deep-research`, read and apply
   `%USERPROFILE%\.codex\skills\chatgpt-deep-research-browser\SKILL.md`.
4. Read
   `%USERPROFILE%\.codex\skills\chatgpt-oracle-runtime\SKILL.md` for manifest,
   completion, lock, and exact-slug recovery rules.
5. If DevSpace is unavailable or the exact root is not registered, do not
   submit and do not fall back to Pro, ZIP attachments, CodexPro, agbrowse,
   in-app Browser, Chrome control, Playwright, or another workspace. Route only
   to the read-only diagnosis or explicitly authorized setup procedure in
   `chatgpt-workspace-setup`.
6. Create the UTF-8 mission and Oracle manifest using the existing project
   convention. Include the original request, selected mode, exact root,
   evidence paths, action authority, non-goals, acceptance conditions, and
   forbidden external effects.
7. Run the dispatcher preview first. Confirm the exact project root, mode,
   mission path, model/reasoning evidence, and write authority before a live
   submission.
8. Treat an explicit `$web-gpt` or `/웹gpt` task request as authorization for
   one live Oracle submission for that exact mission. A request for setup,
   explanation, or preview alone authorizes only the dry run.
9. For `direct`, `plan`, `review`, and `deep-research`, return the durable web
   result and locally recheck acceptance-affecting claims. For `edit` and
   `orchestrator`, inspect the actual diff and run the deterministic local
   verification required by the repository before claiming completion.
10. On timeout or observer loss, recover only the stored exact Oracle slug.
    Never resubmit, replace the conversation, or silently change the mode.

## Safety

- Keep secrets, credentials, cookies, browser profiles, Owner passwords, and
  unrelated private files out of missions and outputs.
- Do not broaden DevSpace from the exact registered project root.
- Do not commit, push, deploy, publish, migrate, delete, or change permissions
  unless the current request and the governing repository rules authorize that
  exact effect.
- Keep one active regular Web GPT run per project unless the owning runtime
  explicitly provides a safe independent-session mode.

## Examples

```text
$web-gpt 검토모드로 현재 변경사항을 읽기 전용으로 검토해줘.
$web-gpt 계획모드로 이 기능의 구현 계획을 작성해줘.
$web-gpt 수정모드로 이 오류를 수정하고 테스트해줘.
$web-gpt 지휘모드로 확정된 요구사항을 구현하고 검증해줘.
/웹gpt 심층 리서치로 이 설계의 최신 근거를 조사해줘.
```
