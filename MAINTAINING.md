# Maintaining this profile

## Layout

| Path | What it is | Updated by |
|---|---|---|
| `README.md` | The profile page | You; the workflow rewrites only the block between `RECENT:START` and `RECENT:END` |
| `assets/banner.svg` | Header banner | You (hand-written SVG) |
| `assets/architecture-dark.svg` | Flagship architecture diagram | You |
| `assets/architecture-light.svg` | Light version of the diagram | `python scripts/build_profile.py light-variant` |
| `scripts/build_profile.py` | Generator, Python standard library only | — |
| `scripts/config.json` | Excluded repos, description overrides, counts | You |
| `.github/workflows/refresh-profile.yml` | Daily refresh | — |
| `output` branch | Generated `activity-*.svg` and `languages-*.svg` | Workflow (one force-pushed commit, no history) |

## Dynamic components

| Component | Data source | Frequency | Dependencies |
|---|---|---|---|
| Contribution activity card | GitHub GraphQL `contributionCalendar` (public page as local fallback) | Daily 03:17 UTC, on manual run, on script changes | Built-in `GITHUB_TOKEN` |
| Language card | REST `/repos/{owner}/{repo}/languages`, non-fork repos minus `exclude_repos` | Same | Same |
| Recently updated table | REST `/users/{login}/repos`, sorted by last push | Same; commits to `main` only when the table changes | Same |

If the API fails, the script exits before writing anything, so the last good cards stay online.

## Common edits

- **Run a refresh now:** Actions → Refresh profile → Run workflow.
- **Hide a repo from the cards and table:** add it to `exclude_repos` in `scripts/config.json`.
- **Change a description in the table:** set the description on the repository itself, then delete its entry from `description_overrides`.
- **Edit the diagram:** change `assets/architecture-dark.svg` (colours live between `THEME:START` and `THEME:END`), then run `python scripts/build_profile.py light-variant`.
- **Preview locally:** `python scripts/build_profile.py cards --out dist` (works without a token, at 60 API requests per hour).
- **Update "Now":** edit the three bullets in `README.md`. Keep it to three.
