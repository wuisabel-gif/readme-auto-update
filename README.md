# README Auto Update

README Auto Update is a Codex skill that creates and refreshes project or GitHub profile READMEs
from repository evidence. It can understand local code, owned repositories, organization work,
open-source contributions, and privacy-safe private contribution totals.

The Codex skill is the primary product. It lets you review the evidence and proposed README in an
interactive session and does not require an OpenAI API key. An optional GitHub Action is included
for scheduled, unattended updates.

## What it can update

- A project README from source files, manifests, documentation, tests, and Git history
- A GitHub profile README from owned, organization, and open-source work
- Private contribution totals without revealing private repository names
- One generated section while preserving every hand-written section around it
- A README on demand with Codex, or automatically on a GitHub Actions schedule

## Install the Codex skill

Clone this repository, then copy the packaged skill into your personal Codex skills directory:

```bash
mkdir -p ~/.codex/skills
cp -R skills/readme-auto-update ~/.codex/skills/readme-auto-update
```

Restart Codex if the skill is not immediately listed. The distributable skill is contained entirely
in [`skills/readme-auto-update`](skills/readme-auto-update).

## Use it in Codex

Open a repository in Codex and ask:

```text
Use $readme-auto-update to analyze this repository and improve its README.
```

For a GitHub profile README:

```text
Use $readme-auto-update to update my profile README from my owned projects,
organization work, open-source contributions, and anonymous private activity.
```

The skill reads the existing README, gathers relevant evidence, writes only a managed section, and
shows or inspects the resulting diff. It does not commit or push unless you request that separately.

### Local repository mode

Local mode uses the repository already open in Codex. It inspects useful files and Git history while
avoiding credentials, dependency trees, build artifacts, and unrelated generated files. No GitHub
token or OpenAI API key is required.

### GitHub account mode

Account mode uses the included privacy-filtering snapshot script. Authenticate with the GitHub CLI
or set one of these environment variables:

```bash
export README_AUTO_UPDATE_GITHUB_TOKEN=your_token
# or
export GH_TOKEN=your_token
```

Credential lookup order is `README_AUTO_UPDATE_GITHUB_TOKEN`, `GH_TOKEN`, then `gh auth token`.
The script does not use the repository-scoped `GITHUB_TOKEN` for account discovery and never prints
the credential.

Private repository names, links, descriptions, languages, and topics are hidden by default. They
are represented as one anonymous **Private work** entry. Explicitly ask for private names only when
publishing them and exposing their metadata to the active model is acceptable.

## Managed README section

README Auto Update changes only the content between these markers:

```md
# Hi, I'm Example User

This introduction is maintained by hand.

<!-- README-AUTO-UPDATE:START:readme-auto-update -->
Generated content is replaced here.
<!-- README-AUTO-UPDATE:END:readme-auto-update -->

This footer is also maintained by hand.
```

If the markers are absent, the skill appends a managed block. It rejects duplicate, unbalanced, or
injected markers instead of risking unrelated README content.

## Optional automatic updates

After the interactive workflow is working, the included GitHub Action can update a profile README
on a schedule. Add these repository secrets under **Settings → Secrets and variables → Actions**:

- `README_AUTO_UPDATE_GITHUB_TOKEN` — user-authorized token for account discovery
- `OPENAI_API_KEY` — optional; required only for the Action's AI writer

Then create `.github/workflows/readme-auto-update.yml`:

```yaml
name: Update profile README

on:
  schedule:
    - cron: "17 6 * * 1"
  workflow_dispatch:

permissions:
  contents: write

concurrency:
  group: readme-auto-update-profile
  cancel-in-progress: true

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: YOUR_GITHUB_USERNAME/readme-auto-update@v1
        with:
          github_token: ${{ secrets.README_AUTO_UPDATE_GITHUB_TOKEN }}
          openai_api_key: ${{ secrets.OPENAI_API_KEY }}
```

Replace `YOUR_GITHUB_USERNAME/readme-auto-update@v1` with the repository owner and published tag,
or use a local checkout for development.

### Action writer modes

- `auto` (default) uses AI when `openai_api_key` is present and deterministic rules otherwise.
- `ai` writes from privacy-filtered evidence through the OpenAI Responses API.
- `rules` makes no OpenAI request and has no model cost.

Example rules-only configuration:

```yaml
      - uses: YOUR_GITHUB_USERNAME/readme-auto-update@v1
        with:
          github_token: ${{ secrets.README_AUTO_UPDATE_GITHUB_TOKEN }}
          mode: rules
```

## Action inputs

| Input | Default | Description |
| --- | --- | --- |
| `github_token` | required | User-authorized token used for account discovery |
| `openai_api_key` | — | Required only in `ai` mode |
| `mode` | `auto` | `auto`, `ai`, or `rules` |
| `output_file` | `README.md` | Markdown file to update |
| `section_name` | `readme-auto-update` | Name embedded in marker comments |
| `model` | `gpt-5.6-luna` | OpenAI model used by the Action's AI writer |
| `days` | `365` | Contribution window from 1 to 365 days |
| `max_repositories` | `30` | Maximum repository evidence entries passed to the writer |
| `include_owned` | `true` | Include user-owned repositories |
| `include_organizations` | `true` | Include work in the user's organizations |
| `include_open_source` | `true` | Include outside public contributions |
| `include_private` | `true` | Include permitted private activity anonymously |
| `show_private_names` | `false` | Expose private repository metadata to the writer and output |
| `include_archived` | `false` | Include archived repositories |
| `prompt` | — | Additional AI style or content preferences |
| `commit` | `true` | Commit and push a changed README |
| `dry_run` | `false` | Print the proposed diff without writing or pushing |

The Action outputs `changed`, `mode_used`, `output_file`, `username`, `repositories_analyzed`, and
`private_contributions`. See [`examples/readme-auto-update.yml`](examples/readme-auto-update.yml)
for the complete workflow.

## GitHub access and privacy

Start with the least access that produces the summary you want. Public contribution discovery uses
a user-authorized token with profile read access. Private and organization activity can require
`read:user`, `read:org`, and `repo`, SAML SSO authorization, and organization approval. Fine-grained
tokens may need separate authorization for each resource owner.

GitHub's normal contribution-graph rules still apply, and organization policy can reduce the data
returned. The discovery credential is used only for GraphQL reads; the workflow's own
`GITHUB_TOKEN` receives only `contents: write` so it can update the profile repository.

See [`SECURITY.md`](SECURITY.md) for the threat model and the skill's
[`github-access.md`](skills/readme-auto-update/references/github-access.md) for access guidance.

## Project structure

```text
skills/readme-auto-update/  Installable Codex skill
src/readme_auto_update/     GitHub Action implementation
examples/                   Example scheduled workflow
tests/                      Skill and Action tests
action.yml                  Composite Action interface
Dockerfile                  Action runtime image
```

## Development

Requirements: Python 3.12+ and Git.

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall -q entrypoint.py src tests skills/readme-auto-update/scripts
docker build -t readme-auto-update .
```

## License

[MIT](LICENSE)
