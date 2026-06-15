#!/usr/bin/env python3
"""Generate a GitHub contribution radar chart SVG using pygal."""

import json
import math
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_GITHUB_USER = "LakshmanTurlapati"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "radar-chart.svg"
REQUEST_TIMEOUT_SECONDS = 20
STABLE_CHART_SLUG = "contribution-radar-score"
STABLE_CHART_ID = f"chart-{STABLE_CHART_SLUG}"
UUID_PATTERN = (
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)
PYGAL_CHART_ID_RE = re.compile(rf"chart-({UUID_PATTERN})")
PYGAL_GENERATED_COMMENT_RE = re.compile(r"<!--Generated with pygal .*?-->")

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
  }
}
"""


def fetch_github_data(github_token, github_user, timeout=REQUEST_TIMEOUT_SECONDS):
    payload = json.dumps({"query": QUERY, "variables": {"login": github_user}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"bearer {github_token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-metrics-radar-generator",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub GraphQL request failed with HTTP {exc.code}: {detail}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GitHub GraphQL request failed: {exc.reason}") from exc

    errors = result.get("errors")
    if errors:
        messages = "; ".join(
            error.get("message", "Unknown GraphQL error") for error in errors
        )
        raise RuntimeError(f"GitHub GraphQL returned errors: {messages}")

    user = result.get("data", {}).get("user")
    if user is None:
        raise RuntimeError(
            f"GitHub user {github_user!r} was not found or is not accessible"
        )

    return user


def normalize_svg(svg_content):
    match = PYGAL_CHART_ID_RE.search(svg_content)
    if match:
        chart_uuid = match.group(1)
        svg_content = svg_content.replace(f"chart-{chart_uuid}", STABLE_CHART_ID)
        svg_content = svg_content.replace(
            f"['{chart_uuid}']", f"['{STABLE_CHART_SLUG}']"
        )
        svg_content = svg_content.replace(
            f'["{chart_uuid}"]', f'["{STABLE_CHART_SLUG}"]'
        )

    return PYGAL_GENERATED_COMMENT_RE.sub(
        "<!--Generated with pygal; normalized for stable diffs-->",
        svg_content,
        count=1,
    )


def generate_radar(data, github_user=DEFAULT_GITHUB_USER, output_path=OUTPUT_PATH):
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
    if any(value is None for value in values):
        raise RuntimeError("GitHub returned incomplete contribution data")

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
        title="Contribution Radar Score",
        js=[],
    )

    chart.add(github_user, normalized)

    svg_content = normalize_svg(chart.render().decode("utf-8"))

    # Add tooltips showing raw counts
    for label, raw in zip(labels, values):
        old = f">{label}<"
        new = f" title=\"{label}: {raw}\">{label}<"
        svg_content = svg_content.replace(old, new, 1)

    output_path.write_text(svg_content, encoding="utf-8")

    print(f"Radar chart written to {output_path}")
    for label, raw, norm in zip(labels, values, normalized):
        print(f"  {label}: {raw} (normalized: {norm})")


def main():
    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token:
        raise RuntimeError("GITHUB_TOKEN environment variable is required")

    github_user = os.environ.get("GITHUB_USER", DEFAULT_GITHUB_USER)
    data = fetch_github_data(github_token, github_user)
    generate_radar(data, github_user=github_user)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
