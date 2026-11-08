#!/usr/bin/env python3
"""Build the dynamic parts of the GitHub profile. Standard library only.

    python scripts/build_profile.py cards  --out dist   # activity + language SVGs
    python scripts/build_profile.py readme              # refresh "Recently updated" in README.md
    python scripts/build_profile.py light-variant       # regenerate architecture-light.svg

Data comes from the GitHub API. Set GITHUB_TOKEN for higher rate limits and the
GraphQL contribution calendar; without a token the script reads the public
contributions page instead. Any fetch error exits non-zero before writing, so
previously published files are never replaced with partial data.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "scripts" / "config.json").read_text(encoding="utf-8"))
LOGIN = CONFIG["login"]
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
API = "https://api.github.com"

THEMES = {
    "dark": {
        "bg": "#0b1220", "border": "#1b2742", "title": "#e6edf7", "muted": "#7b8bad",
        "value": "#f1f5ff", "track": "#16213a",
        "levels": ["#141d31", "#0e4a5c", "#0e7490", "#06b6d4", "#67e8f9"],
        "palette": ["#22d3ee", "#818cf8", "#3b82f6", "#2dd4bf", "#c084fc", "#94a3b8", "#475569"],
    },
    "light": {
        "bg": "#ffffff", "border": "#d8dee9", "title": "#0f172a", "muted": "#5b6b88",
        "value": "#0f172a", "track": "#eef2f7",
        "levels": ["#ebeff5", "#a5e4f1", "#45c3dd", "#0891b2", "#155e75"],
        "palette": ["#0891b2", "#6366f1", "#1d4ed8", "#0d9488", "#9333ea", "#64748b", "#94a3b8"],
    },
}
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"


# --------------------------------------------------------------------------- fetch

def _request(url: str, data: bytes | None = None, accept: str = "application/vnd.github+json") -> bytes:
    headers = {"Accept": accept, "User-Agent": f"{LOGIN}-profile-builder"}
    if TOKEN and url.startswith(API):
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def get_json(path: str):
    return json.loads(_request(f"{API}{path}"))


def fetch_repos() -> list[dict]:
    repos, page = [], 1
    while True:
        batch = get_json(f"/users/{LOGIN}/repos?per_page=100&type=owner&page={page}")
        repos += batch
        if len(batch) < 100:
            break
        page += 1
    excluded = set(CONFIG["exclude_repos"])
    return [r for r in repos if not r["fork"] and not r["archived"] and r["name"] not in excluded]


def fetch_calendar() -> list[tuple[dt.date, int]]:
    """Daily contribution counts for the last year, oldest first."""
    if TOKEN:
        query = """query($login:String!){user(login:$login){contributionsCollection{
          contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}"""
        body = json.dumps({"query": query, "variables": {"login": LOGIN}}).encode()
        data = json.loads(_request(f"{API}/graphql", data=body))
        if "errors" in data:
            raise RuntimeError(f"GraphQL error: {data['errors']}")
        weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
        days = [(dt.date.fromisoformat(d["date"]), d["contributionCount"])
                for w in weeks for d in w["contributionDays"]]
    else:
        page = _request(f"https://github.com/users/{LOGIN}/contributions", accept="text/html").decode("utf-8")
        cells = re.findall(r'data-date="(\d{4}-\d{2}-\d{2})" id="(contribution-day-component-[\d-]+)"', page)
        tips = dict(re.findall(r'for="(contribution-day-component-[\d-]+)"[^>]*>([^<]*)', page))
        days = []
        for date, cid in cells:
            m = re.match(r"\s*(\d+) contribution", tips.get(cid, ""))
            days.append((dt.date.fromisoformat(date), int(m.group(1)) if m else 0))
    if len(days) < 300:
        raise RuntimeError(f"Contribution calendar looks incomplete ({len(days)} days)")
    return sorted(days)


# --------------------------------------------------------------------------- svg helpers

def esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def frame(width: int, height: int, theme: dict, title: str, desc: str, body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" '
        f'height="{height}" role="img" aria-labelledby="t d">'
        f'<title id="t">{esc(title)}</title><desc id="d">{esc(desc)}</desc>'
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="14" '
        f'fill="{theme["bg"]}" stroke="{theme["border"]}"/>{body}</svg>\n'
    )


def text(x, y, s, fill, size=13, weight=400, family=SANS, anchor="start", spacing=0) -> str:
    return (f'<text x="{x}" y="{y}" fill="{fill}" font-family="{family}" font-size="{size}" '
            f'font-weight="{weight}" text-anchor="{anchor}" letter-spacing="{spacing}">{esc(s)}</text>')


# --------------------------------------------------------------------------- cards

def activity_card(days: list[tuple[dt.date, int]], theme: dict) -> str:
    total = sum(c for _, c in days)
    active = sum(1 for _, c in days if c)
    peak = max((c for _, c in days), default=0) or 1

    cell, gap, top, width = 12, 3, 104, 880   # same width as the language card
    start = days[0][0] - dt.timedelta(days=(days[0][0].weekday() + 1) % 7)  # back to Sunday
    weeks = (days[-1][0] - start).days // 7 + 1
    left = (width - (weeks * (cell + gap) - gap)) // 2
    rects, months, last_month_col = [], [], -10
    for date, count in days:
        col = (date - start).days // 7
        row = (date.weekday() + 1) % 7
        if count == 0:
            level = 0
        else:
            level = 1 + round(3 * (count - 1) / (peak - 1)) if peak > 1 else 4
        x, y = left + col * (cell + gap), top + row * (cell + gap)
        rects.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2.5" '
                     f'fill="{theme["levels"][level]}"><title>{count} on {date:%d %b %Y}</title></rect>')
        if date.day == 1 and col - last_month_col >= 3:
            months.append(text(x, top - 10, date.strftime("%b"), theme["muted"], 11, family=MONO))
            last_month_col = col

    height = top + 7 * (cell + gap) + 40

    stats = [(f"{total:,}", "contributions"), (str(active), "active days")]
    stat_svg, sx = [], width - left
    for value, label in reversed(stats):
        stat_svg.append(text(sx, 52, value, theme["value"], 22, 700, anchor="end"))
        stat_svg.append(text(sx, 72, label, theme["muted"], 11.5, anchor="end"))
        sx -= 130

    legend_y = top + 7 * (cell + gap) + 18
    legend = [text(left, legend_y + 10, f"Updated {dt.date.today():%d %b %Y}", theme["muted"], 11, family=MONO)]
    lx = width - left - 5 * (cell + gap) + gap - 40
    legend.append(text(lx - 8, legend_y + 10, "less", theme["muted"], 11, family=MONO, anchor="end"))
    for i, color in enumerate(theme["levels"]):
        legend.append(f'<rect x="{lx + i * (cell + gap)}" y="{legend_y}" width="{cell}" height="{cell}" rx="2.5" fill="{color}"/>')
    legend.append(text(lx + 5 * (cell + gap) + 5, legend_y + 10, "more", theme["muted"], 11, family=MONO))

    body = "".join([
        text(left, 46, "Contribution activity", theme["title"], 17, 600),
        text(left, 68, "last 12 months · public GitHub data", theme["muted"], 12, family=MONO),
        *stat_svg, *months, *rects, *legend,
    ])
    desc = f"{total} contributions on {active} active days in the last 12 months."
    return frame(width, height, theme, "GitHub contribution activity", desc, body)


def language_totals(repos: list[dict]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for repo in repos:
        for lang, size in get_json(f"/repos/{LOGIN}/{repo['name']}/languages").items():
            totals[lang] = totals.get(lang, 0) + size
    return totals


def languages_card(totals: dict[str, int], repo_count: int, theme: dict) -> str:
    grand = sum(totals.values()) or 1
    ranked = sorted(totals.items(), key=lambda kv: -kv[1])
    top = ranked[: CONFIG["languages_top"]]
    other = grand - sum(v for _, v in top)
    if other > 0:
        top.append(("Other", other))

    width, left, bar_y, bar_w = 880, 32, 92, 880 - 64
    segs, x = [], left
    clip = f'<clipPath id="bar"><rect x="{left}" y="{bar_y}" width="{bar_w}" height="12" rx="6"/></clipPath>'
    for i, (lang, size) in enumerate(top):
        w = bar_w * size / grand
        segs.append(f'<rect x="{x:.2f}" y="{bar_y}" width="{w + 0.5:.2f}" height="12" fill="{theme["palette"][i % 7]}"/>')
        x += w

    legend, cols = [], 4
    for i, (lang, size) in enumerate(top):
        cx = left + (i % cols) * (bar_w / cols)
        cy = bar_y + 44 + (i // cols) * 26
        legend.append(f'<circle cx="{cx + 5:.1f}" cy="{cy - 4}" r="5" fill="{theme["palette"][i % 7]}"/>')
        legend.append(text(cx + 18, cy, lang, theme["title"], 13, 500))
        legend.append(text(cx + bar_w / cols - 24, cy, f"{100 * size / grand:.1f}%", theme["muted"], 12,
                           family=MONO, anchor="end"))
    height = bar_y + 44 + ((len(top) - 1) // cols) * 26 + 28

    body = "".join([
        f"<defs>{clip}</defs>",
        text(left, 46, "Languages by code volume", theme["title"], 17, 600),
        text(left, 68, f"bytes across {repo_count} original public repositories (team projects included)",
             theme["muted"], 12, family=MONO),
        f'<rect x="{left}" y="{bar_y}" width="{bar_w}" height="12" rx="6" fill="{theme["track"]}"/>',
        f'<g clip-path="url(#bar)">{"".join(segs)}</g>', *legend,
    ])
    desc = ", ".join(f"{l} {100 * s / grand:.1f}%" for l, s in top)
    return frame(width, height, theme, "Language share across public repositories", desc, body)


# --------------------------------------------------------------------------- readme

def recent_table(repos: list[dict]) -> str:
    overrides = CONFIG.get("description_overrides", {})
    recent = sorted(repos, key=lambda r: r["pushed_at"], reverse=True)[: CONFIG["recent_count"]]
    rows = ["| Repository | What it is | Main language | Last push |", "|---|---|---|---|"]
    for r in recent:
        desc = overrides.get(r["name"]) or r["description"] or "—"
        pushed = dt.datetime.fromisoformat(r["pushed_at"].replace("Z", "+00:00"))
        lang = r["language"] or "—"
        rows.append(f"| [**{r['name']}**]({r['html_url']}) | {desc.replace('|', '/')} | {lang} | {pushed:%b %Y} |")
    return "\n".join(rows)


def update_readme(repos: list[dict]) -> bool:
    path = ROOT / "README.md"
    original = path.read_text(encoding="utf-8")
    pattern = re.compile(r"(<!-- RECENT:START -->).*?(<!-- RECENT:END -->)", re.S)
    if not pattern.search(original):
        raise RuntimeError("RECENT markers not found in README.md")
    updated = pattern.sub(lambda m: f"{m.group(1)}\n{recent_table(repos)}\n{m.group(2)}", original)
    if updated != original:
        path.write_text(updated, encoding="utf-8", newline="\n")
    return updated != original


# --------------------------------------------------------------------------- static assets

LIGHT_DIAGRAM_THEME = {
    "#0b1220": "#f7f9fc", "#0f1a2e": "#ffffff", "#24324f": "#d3dbe8", "#22d3ee": "#0891b2",
    "#e6edf7": "#0f172a", "#8b9bbd": "#526079", "#a5b4fc": "#4f46e5", "#5f7096": "#6b7a96",
    "#3b4d72": "#9aa8c2", "#818cf8": "#6366f1", "#1b2742": "#e3e8f0",
}


def light_variant() -> None:
    src = (ROOT / "assets" / "architecture-dark.svg").read_text(encoding="utf-8")
    start, end = src.index("<!-- THEME:START -->"), src.index("<!-- THEME:END -->")
    block = src[start:end]
    for dark, light in LIGHT_DIAGRAM_THEME.items():
        block = block.replace(dark, light)
    out = src[:start] + block + src[end:]
    (ROOT / "assets" / "architecture-light.svg").write_text(out, encoding="utf-8", newline="\n")


# --------------------------------------------------------------------------- main

def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "cards":
        out = Path(argv[argv.index("--out") + 1]) if "--out" in argv else ROOT / "dist"
        # Fetch everything before writing anything.
        repos, days = fetch_repos(), fetch_calendar()
        totals = language_totals(repos)
        rendered = {}
        for name, theme in THEMES.items():
            rendered[f"activity-{name}.svg"] = activity_card(days, theme)
            rendered[f"languages-{name}.svg"] = languages_card(totals, len(repos), theme)
        out.mkdir(parents=True, exist_ok=True)
        for fname, svg in rendered.items():
            (out / fname).write_text(svg, encoding="utf-8", newline="\n")
        print(f"wrote {len(rendered)} cards to {out}")
    elif cmd == "readme":
        changed = update_readme(fetch_repos())
        print("README updated" if changed else "README unchanged")
    elif cmd == "light-variant":
        light_variant()
        print("wrote assets/architecture-light.svg")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
