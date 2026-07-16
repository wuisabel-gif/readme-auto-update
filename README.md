# README Auto Update

README Auto Update is an agent skill for Claude Code and Codex that creates and refreshes project
or GitHub profile READMEs from repository evidence. It can understand local code, owned
repositories, organization work, open-source contributions, and privacy-safe private contribution
totals.

The skill is the primary product. It lets you review the evidence and proposed README in an
interactive session and does not require any model API key — the agent you are already running is
the writer. An optional GitHub Action is included for scheduled, unattended updates.

## What it can update

- A project README from source files, manifests, documentation, tests, and Git history
- A GitHub profile README from owned, organization, and open-source work
- Private contribution totals without revealing private repository names
- One generated section while preserving every hand-written section around it
- A README on demand with Claude Code or Codex, or automatically on a GitHub Actions schedule

## Install the skill

For Claude Code, install the plugin straight from GitHub:

```text
/plugin marketplace add wuisabel-gif/readme-auto-update
/plugin install readme-auto-update@readme-auto-update
```

Alternatively, clone this repository and copy the packaged skill into your agent's skills
directory. The distributable skill is contained entirely in
[`skills/readme-auto-update`](skills/readme-auto-update).

For Claude Code (manual install):

```bash
mkdir -p ~/.claude/skills
cp -R skills/readme-auto-update ~/.claude/skills/readme-auto-update
```

For Codex:

```bash
mkdir -p ~/.codex/skills
cp -R skills/readme-auto-update ~/.codex/skills/readme-auto-update
```

Restart the agent if the skill is not immediately listed.

## Use it

Open a repository in Claude Code and ask:

```text
Use /readme-auto-update to analyze this repository and improve its README.
```

In Codex, the same request uses `$readme-auto-update`. For a GitHub profile README:

```text
Use /readme-auto-update to update my profile README from my owned projects,
organization work, open-source contributions, and anonymous private activity.
```

The skill reads the existing README, gathers relevant evidence, writes only a managed section, and
shows or inspects the resulting diff. It does not commit or push unless you request that separately.

### Local repository mode

Local mode uses the repository already open in the agent. It inspects useful files and Git history while
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

## Example generated profile README

The best output should read like a person explaining what they care about—not a dashboard reciting
commit counts. This fictional AI-written example uses repository and contribution evidence to tell
a compact story. The introduction and footer remain hand-written; only the marked section is
regenerated.

```md
# Hi, I'm Example User

I like building small tools that remove the annoying part of a larger problem.

<!-- README-AUTO-UPDATE:START:readme-auto-update -->
Most of these projects started with something I wanted to stop doing by hand. One began because I
kept forgetting the right release commands. Another came from trying to test hardware software
before the hardware existed. The useful part is not how many commits they took; it is that the next
person can start a little farther ahead.

## ⭐ Highlights

- 🧵 **[Threadline](https://github.com/example-user/threadline).** Remembers the release steps for a
  project and turns them into one repeatable command, with a dry run before anything is published.
- 🌊 **[Tidepool](https://github.com/example-user/tidepool).** A simulator for testing telemetry and
  packet handling while the real device is still being assembled.
- ✍️ **[Plainspoken](https://github.com/example-user/plainspoken).** Finds stiff, generic language in
  technical documentation and helps rewrite it without flattening the author's voice.

## 🤝 Collaborations and open source

- **[Example Docs Platform](https://github.com/example-org/docs-platform).** Contributed publishing
  checks and preview tooling so documentation changes can be reviewed before they reach the main
  site. Three pull requests were merged during the selected period.
- **[Community Toolkit](https://github.com/community-library/toolkit).** Improved error reporting and
  reviewed changes to the command-line interface. The goal was simple: failures should tell people
  what to do next.

## The rest of the workshop

### Developer tools

- **[Patchwork](https://github.com/example-user/patchwork).** Keeps small repository maintenance jobs
  in one place instead of scattering them across shell history.
- **[Logbook](https://github.com/example-user/logbook).** Turns noisy local development logs into a
  searchable timeline of what changed and why a run failed.

### Hardware and simulation

- **[Signal Bench](https://github.com/example-user/signal-bench).** Generates realistic sensor traffic
  for exercising parsers, dashboards, and failure handling without a lab setup.

## Private work

Some recent work happened in private repositories. Their names, organizations, technologies, and
descriptions stay hidden; only the existence of that activity is included here.

<sub>Last updated by README Auto Update on YYYY-MM-DD UTC.</sub>
<!-- README-AUTO-UPDATE:END:readme-auto-update -->

You can also find my manually maintained contact links below.
```

The AI writer can produce this narrative form because it can connect verified descriptions,
documentation, and contribution evidence. The deterministic `rules` writer uses a simpler factual
layout. Neither writer should invent motivation or impact: when the repository does not explain
why something exists, the output should say what it does and stop there. Private repository
identity remains hidden unless `show_private_names` is explicitly enabled.

## Optional automatic updates

After the interactive workflow is working, the included GitHub Action can update a profile README
on a schedule. Add these repository secrets under **Settings → Secrets and variables → Actions**:

- `README_AUTO_UPDATE_GITHUB_TOKEN` — user-authorized token for account discovery
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` — optional; either one enables the Action's AI writer

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
          # or, to write with Claude instead:
          # anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
```

Replace `YOUR_GITHUB_USERNAME/readme-auto-update@v1` with the repository owner and published tag,
or use a local checkout for development.

### Action writer modes

- `auto` (default) uses AI when an API key is present and deterministic rules otherwise.
- `ai` writes from privacy-filtered evidence through the OpenAI Responses API or the Anthropic
  Messages API. When both keys are set, OpenAI is used.
- `rules` makes no model request and has no model cost.

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
| `openai_api_key` | — | AI mode requires this or `anthropic_api_key` |
| `anthropic_api_key` | — | Used in AI mode when no OpenAI key is set |
| `mode` | `auto` | `auto`, `ai`, or `rules` |
| `output_file` | `README.md` | Markdown file to update |
| `section_name` | `readme-auto-update` | Name embedded in marker comments |
| `model` | per provider | AI writer model; defaults to `gpt-5.6-luna` (OpenAI) or `claude-opus-4-8` (Anthropic) |
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
.claude-plugin/             Claude Code plugin and marketplace manifests
skills/readme-auto-update/  Installable agent skill (Claude Code and Codex)
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

## Related projects

- **[Cadence](https://github.com/wuisabel-gif/Cadence)** — an AI-text humanizer that scores prose
  for machine-generated patterns and rewrites it in a chosen voice. Pair it with README Auto
  Update: after generating a README section, run Cadence over the prose to catch flat sentence
  rhythm and AI-sounding phrasing before publishing.

## License

[MIT](LICENSE)
