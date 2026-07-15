# GitHub access and privacy

## Credential order

The snapshot script checks:

1. `README_AUTO_UPDATE_GITHUB_TOKEN`
2. `GH_TOKEN`
3. `gh auth token` from an existing authenticated GitHub CLI session

The workflow-provided `GITHUB_TOKEN` is intentionally not used for account discovery because it is
limited to the repository containing the workflow.

## Access levels

- Public profile and open-source work: use a user-authorized credential with profile read access.
- Private contribution data: classic tokens typically need `read:user` and `repo`.
- Organization classification: classic tokens typically need `read:org`.
- SAML organizations can require separate SSO authorization.
- Organization policy can block or require approval for tokens.

Fine-grained tokens should be preferred when one resource owner is sufficient. They can be
incomplete for multi-organization, outside-collaborator, and broad account summaries. For managed
team use, prefer a GitHub App with short-lived credentials and explicitly selected repositories.

## Privacy modes

Default mode includes private contribution counts but replaces all accessible private repository
records with one `Private work` record. It removes private names, owners, URLs, descriptions,
languages, topics, star counts, and update dates before writing JSON.

`--show-private-names` is an explicit privacy boundary. Do not select it merely because the token
can access private repositories.

`--exclude-private` removes accessible and restricted private activity from the evidence. When a
category is excluded, calculate displayed totals from the remaining repository evidence rather
than showing account-wide totals that may contain the excluded work.

GitHub contribution-graph rules still apply. Commit attribution depends on linked commit email and
eligible branches. Restricted contribution counts appear only when GitHub exposes them for the
profile and credential.

