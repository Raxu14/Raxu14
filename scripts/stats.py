"""Generate stats.svg for the profile README from the GitHub GraphQL API.

Runs in GitHub Actions (see .github/workflows/stats.yml), so the README
does not depend on any external, rate-limited stats service.
"""
import json
import os
import urllib.request
from html import escape

USER = os.environ.get("STATS_USER", "Raxu14")
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = os.environ.get("STATS_OUT", "stats.svg")

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    contributionsCollection {
      contributionCalendar { totalContributions }
    }
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def fetch():
    body = json.dumps({"query": QUERY, "variables": {"login": USER}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)
    if "errors" in data:
        raise SystemExit(f"GraphQL error: {data['errors']}")
    return data["data"]["user"]


def render(user):
    repos = user["repositories"]["nodes"]
    stats = [
        ("Contributions (last year)", user["contributionsCollection"]["contributionCalendar"]["totalContributions"]),
        ("Public repositories", user["repositories"]["totalCount"]),
        ("Stars earned", sum(r["stargazerCount"] for r in repos)),
        ("Followers", user["followers"]["totalCount"]),
    ]

    sizes = {}
    colors = {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            sizes[name] = sizes.get(name, 0) + edge["size"]
            colors[name] = edge["node"]["color"] or "#8b949e"
    total = sum(sizes.values()) or 1
    langs = sorted(sizes.items(), key=lambda kv: kv[1], reverse=True)[:5]

    width, pad = 420, 20
    parts = []
    y = 34
    for label, value in stats:
        parts.append(f'<text x="{pad}" y="{y}" class="label">{escape(label)}</text>')
        parts.append(f'<text x="{width - pad}" y="{y}" class="value" text-anchor="end">{value}</text>')
        y += 26

    if langs:
        y += 6
        bar_w = width - 2 * pad
        x = pad
        parts.append(f'<clipPath id="bar"><rect x="{pad}" y="{y}" width="{bar_w}" height="8" rx="4"/></clipPath>')
        parts.append('<g clip-path="url(#bar)">')
        for name, size in langs:
            w = bar_w * size / sum(s for _, s in langs)
            parts.append(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="8" fill="{colors[name]}"/>')
            x += w
        parts.append("</g>")
        y += 28
        x = pad
        for name, size in langs:
            pct = f"{100 * size / total:.0f}%"
            parts.append(f'<circle cx="{x + 5}" cy="{y - 4}" r="5" fill="{colors[name]}"/>')
            parts.append(f'<text x="{x + 15}" y="{y}" class="label">{escape(name)} {pct}</text>')
            x += 15 + 9 * len(name) + 40
        y += 10

    height = y + pad - 6
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<style>
  .label {{ font: 400 14px -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; fill: #57606a; }}
  .value {{ font: 600 14px -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; fill: #1f2328; }}
  @media (prefers-color-scheme: dark) {{
    .label {{ fill: #8b949e; }}
    .value {{ fill: #e6edf3; }}
  }}
</style>
{chr(10).join(parts)}
</svg>
"""


if __name__ == "__main__":
    svg = render(fetch())
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(svg)
    print(f"Wrote {OUT}")
