#!/usr/bin/env python3
"""Generate a GitHub contribution radar chart SVG using pygal."""

import json
import math
import os
import urllib.request

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_USER = os.environ.get("GITHUB_USER", "LakshmanTurlapati")
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "radar-chart.svg")

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalPullRequestReviewContributions
      totalRepositoriesWithContributedCommits
    }
    repositories(ownerAffiliations: OWNER, first: 1) {
      totalCount
    }
    starredRepositories {
      totalCount
    }
    followers {
      totalCount
    }
  }
}
"""


def fetch_github_data():
    payload = json.dumps({"query": QUERY, "variables": {"login": GITHUB_USER}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"bearer {GITHUB_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())["data"]["user"]


def generate_radar(data):
    import pygal
    from pygal.style import Style

    cc = data["contributionsCollection"]

    labels = ["Commits", "Pull Requests", "Issues", "Code Reviews", "Repos"]
    values = [
        cc["totalCommitContributions"],
        cc["totalPullRequestContributions"],
        cc["totalIssueContributions"],
        cc["totalPullRequestReviewContributions"],
        cc["totalRepositoriesWithContributedCommits"],
    ]

    # Log normalization to prevent commits from dominating the chart
    max_log = math.log(max(values) + 1) if max(values) > 0 else 1
    normalized = [round(math.log(v + 1) / max_log * 100, 1) for v in values]
    # Floor at 10 so even small values are visible on the radar
    normalized = [max(n, 10) if v > 0 else 0 for n, v in zip(normalized, values)]

    dark_style = Style(
        background="#0d1117",
        plot_background="#0d111700",
        foreground="#c9d1d9",
        foreground_strong="#e6edf3",
        foreground_subtle="#484f58",
        colors=("#58a6ff", "#3fb950", "#d29922", "#f78166", "#bc8cff"),
        font_family="Segoe UI, Helvetica, Arial, sans-serif",
        title_font_size=16,
        label_font_size=12,
        value_font_size=10,
    )

    chart = pygal.Radar(
        style=dark_style,
        width=480,
        height=400,
        show_legend=False,
        fill=True,
        dots_size=4,
        show_y_labels=False,
        x_labels=labels,
        range=(0, 100),
        title="Contribution Radar",
        js=[],
    )

    chart.add(GITHUB_USER, normalized)

    svg_content = chart.render().decode("utf-8")

    # Add tooltips showing raw counts
    for label, raw, norm in zip(labels, values, normalized):
        old = f">{label}<"
        new = f" title=\"{label}: {raw}\">{label}<"
        svg_content = svg_content.replace(old, new, 1)

    with open(OUTPUT_PATH, "w") as f:
        f.write(svg_content)

    print(f"Radar chart written to {OUTPUT_PATH}")
    for label, raw, norm in zip(labels, values, normalized):
        print(f"  {label}: {raw} (normalized: {norm})")


if __name__ == "__main__":
    data = fetch_github_data()
    generate_radar(data)
