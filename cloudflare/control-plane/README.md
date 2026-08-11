# Cloudflare control-plane bootstrap

This directory owns the public, static bootstrap endpoint for CodexPro Automation.
It intentionally contains no GitHub write capability, Oracle/DevSpace runtime, or secrets.

## Deploy

Use Node.js 24 and an authenticated Wrangler session. Keep the account identifier in the
process environment rather than committing it to the repository.

```powershell
$env:CLOUDFLARE_ACCOUNT_ID='<account-id>'
& 'C:\Program Files\nodejs\npx.cmd' --yes wrangler@4.120.0 deploy
Remove-Item Env:CLOUDFLARE_ACCOUNT_ID
```

## Verify

```powershell
& 'C:\Program Files\nodejs\npx.cmd' --yes wrangler@4.120.0 deployments list
Invoke-WebRequest 'https://codexpro-automation-control-plane.<workers-subdomain>.workers.dev/'
Invoke-WebRequest 'https://codexpro-automation-control-plane.<workers-subdomain>.workers.dev/control-plane.json'
```

The root and machine-readable status must return `200`; an unknown path must return `404`.
Security headers are defined in `public/_headers` and must be verified from the served route.

## Rollback

Record the currently active deployment version before any later release. A later deployment
can be rolled back with Wrangler's deployment rollback command, using that recorded version.
For this first bootstrap there is no earlier version to restore.
