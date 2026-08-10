# Cloud-first operations

This runbook makes GitHub-backed work independent of an awake Windows PC. It
does not pretend that unpublished local files exist in the cloud.

## Authority and lanes

- GitHub is the source of truth for repository bytes, branches, pull requests,
  and CI evidence.
- A Codex Cloud environment is the default execution lane for repository work.
- Oracle, DevSpace, CodexPro Bridge, Tailscale, and the signed-in desktop browser
  form an explicit local-only lane. They are used only for unpublished local
  files, signed-in desktop applications, or exact recovery of a persisted run.
- Cloudflare Worker and Tailscale Funnel are optional local adapters. They are
  not part of cloud completion and their health cannot prove cloud readiness.

The machine-readable policy is
[`contracts/cloud/cloud-first-v1.json`](../contracts/cloud/cloud-first-v1.json).

## One-time Codex Cloud setup

1. Connect GitHub in Codex and grant access only to the repositories that may
   be worked on.
2. Create a Codex Cloud environment for each repository. For this repository,
   the setup script is:

   ```bash
   python -m pip install "pytest>=8,<10"
   ```

3. Leave agent internet access off unless a task proves a narrower allowlist is
   required. Setup scripts can install dependencies before the agent phase.
4. Do not add an API key for ordinary Codex Cloud chats. If a different
   GitHub Actions workflow later uses `openai/codex-action`, store its API key as
   a GitHub secret and treat that workflow as a separate execution identity.
5. Confirm the environment loads the repository `AGENTS.md` and can run:

   ```bash
   python scripts/validate_cloud_first.py --root .
   python -m pytest -q tests/test_cloud_first_contract.py
   ```

## Task lifecycle

1. Start from an exact GitHub branch or commit.
2. Read the applicable `AGENTS.md` chain and declare the tests before editing.
3. Make changes in the cloud checkout and run the declared tests.
4. Review the diff, push a dedicated branch, and open a pull request.
5. Observe CI on the exact commit. A local test, an unpushed branch, or a tool
   receipt alone is not completion.
6. Merge only after the repository's human approval policy is satisfied.

The durable completion evidence is a GitHub commit plus its pull request and CI
status. A local transcript or Bridge health response is supporting evidence only.

## Dirty working tree migration

Cloud work cannot see local uncommitted bytes. Apply the exact policy
`synchronize-to-explicit-backup-branch-or-block`:

1. Inspect the local diff without resetting, cleaning, or stashing it.
2. Exclude secrets, credentials, caches, generated bulk, and machine-specific
   paths.
3. Commit the intended bytes to a clearly named backup branch and push it.
4. Record the branch and commit SHA as the cloud handoff identity.
5. If the bytes cannot be safely pushed, block that task or keep it on the
   explicit local-only lane. Never reconstruct or infer the missing content.

## PC-off acceptance test

The migration is complete for a repository only after all of these pass while
the Windows host and its Bridge/Funnel are unavailable:

1. Start a cloud task from the intended GitHub branch.
2. Read a repository file and the applicable `AGENTS.md`.
3. Make a harmless documentation change on a test branch.
4. Run the declared cloud-compatible tests.
5. Push the branch, open a pull request, and observe CI on the exact commit.
6. Close the test pull request without merging, unless the change is wanted.

Windows-only browser automation and unpublished local files are deliberately
outside this acceptance. Their continued need does not make the cloud lane fail;
it means that particular task belongs to the explicit local-only lane.
