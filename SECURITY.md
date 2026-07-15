# Security policy

## Reporting a vulnerability

Use GitHub's private vulnerability-reporting feature rather than opening a public issue. Include
the affected version, impact, and a minimal reproduction without real credentials or private
repository data.

## Trust boundaries

README Auto Update handles three different permissions:

1. The workflow's built-in `GITHUB_TOKEN` lets the checked-out profile repository receive the
   generated README commit.
2. `README_AUTO_UPDATE_GITHUB_TOKEN` reads account-wide GitHub contribution metadata.
3. `OPENAI_API_KEY` sends an already filtered summary to the OpenAI Responses API in AI mode.

The discovery token is never passed to OpenAI. The OpenAI key is never passed to GitHub.

## Private repositories

`include_private` defaults to true so private contribution totals can be represented, while
`show_private_names` defaults to false. In that default configuration, README Auto Update collapses all
accessible private repositories and restricted contributions into one anonymous `Private work`
record before constructing the AI request.

Enabling `show_private_names` allows names, descriptions, languages, topics, URLs, and activity
counts for private repositories to reach the README writer. If AI mode is active, that evidence
also reaches the configured OpenAI model. Enable it only when publication and model processing are
both acceptable.

README Auto Update reads repository metadata, not source files or repository README contents from the
discovered repositories.

## Workflow safety

- Run README Auto Update from `schedule` or `workflow_dispatch`.
- Do not expose its secrets to untrusted pull-request workflows.
- Grant the workflow only `contents: write`.
- Give the discovery token the minimum scopes and repository access that meet the intended view.
- Authorize organization SSO only where needed and respect organization token policies.
- Prefer short-lived GitHub App credentials when operating this across a team or organization.
- Review a first run with `dry_run: "true"`.

Rules mode never contacts the OpenAI API.

## Supported versions

Security fixes are applied to the latest major release.

