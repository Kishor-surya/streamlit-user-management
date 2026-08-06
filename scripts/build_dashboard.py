"""Builds the static CI/CD metrics dashboard published to GitHub Pages.

Reads artifacts produced earlier in the pages workflow run (coverage.xml,
htmlcov/, test-results.xml, codeql-metrics.json, dependabot-metrics.json)
and renders a single self-contained site/index.html.
"""

import json
import os
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"


def load_json(filename, default):
    path = ROOT / filename
    if path.exists():
        return json.loads(path.read_text())
    return default


def coverage_percent():
    cov_file = ROOT / "coverage.xml"
    if not cov_file.exists():
        return None
    root = ET.parse(cov_file).getroot()
    return round(float(root.attrib["line-rate"]) * 100, 1)


def test_summary():
    junit_file = ROOT / "test-results.xml"
    if not junit_file.exists():
        return {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    root = ET.parse(junit_file).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    attrib = suite.attrib if suite is not None else {}
    return {
        "tests": int(attrib.get("tests", 0)),
        "failures": int(attrib.get("failures", 0)),
        "errors": int(attrib.get("errors", 0)),
        "skipped": int(attrib.get("skipped", 0)),
    }


def severity_rows(metrics):
    by_sev = metrics.get("bySeverity", {})
    if not by_sev:
        return '<tr><td colspan="2">None found</td></tr>'
    return "".join(f"<tr><td>{sev}</td><td>{count}</td></tr>" for sev, count in sorted(by_sev.items()))


def main():
    SITE.mkdir(exist_ok=True)

    cov_pct = coverage_percent()
    tests = test_summary()
    codeql = load_json("codeql-metrics.json", {"total": 0, "bySeverity": {}})
    dependabot = load_json("dependabot-metrics.json", {"total": 0, "bySeverity": {}})

    htmlcov = ROOT / "htmlcov"
    if htmlcov.exists():
        shutil.copytree(htmlcov, SITE / "coverage", dirs_exist_ok=True)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    sha = os.environ.get("GITHUB_SHA", "")[:7]
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    run_url = f"https://github.com/{repo}/actions/runs/{run_id}"

    tests_ok = tests["failures"] == 0 and tests["errors"] == 0
    cov_display = f"{cov_pct}%" if cov_pct is not None else "N/A"
    cov_class = "ok" if (cov_pct or 0) >= 70 else "warn"

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>User Management &mdash; CI/CD Dashboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {{ color-scheme: light dark; }}
  body {{
    font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
    max-width: 960px; margin: 2rem auto; padding: 0 1rem; line-height: 1.5;
  }}
  h1 {{ margin-bottom: 0.2rem; }}
  .sub {{ color: #666; margin-top: 0; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin: 1.5rem 0; }}
  .card {{ border: 1px solid #d0d7de; border-radius: 8px; padding: 1rem; }}
  .card h2 {{ margin: 0 0 0.3rem; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.03em; color: #666; }}
  .card .value {{ font-size: 2rem; font-weight: 700; }}
  .ok {{ color: #1a7f37; }}
  .warn {{ color: #9a6700; }}
  .bad {{ color: #cf222e; }}
  table {{ border-collapse: collapse; width: 100%; margin: 0.5rem 0 1.5rem; }}
  th, td {{ border: 1px solid #d0d7de; padding: 0.4rem 0.6rem; text-align: left; font-size: 0.9rem; }}
  th {{ background: rgba(127,127,127,0.1); }}
  a {{ color: #0969da; }}
  footer {{ color: #666; font-size: 0.85rem; margin-top: 2rem; }}
</style>
</head>
<body>
  <h1>User Management &mdash; CI/CD Dashboard</h1>
  <p class="sub">
    Repository: <a href="https://github.com/{repo}">{repo}</a>
    &bull; Commit <code>{sha}</code>
    &bull; Generated {generated_at}
  </p>

  <div class="cards">
    <div class="card">
      <h2>Unit Tests</h2>
      <div class="value {'ok' if tests_ok else 'bad'}">{tests['tests']} run</div>
      <div>{tests['failures']} failed &bull; {tests['errors']} errors &bull; {tests['skipped']} skipped</div>
    </div>
    <div class="card">
      <h2>Code Coverage</h2>
      <div class="value {cov_class}">{cov_display}</div>
      <div><a href="coverage/index.html">Full HTML report &rarr;</a></div>
    </div>
    <div class="card">
      <h2>CodeQL Alerts (open)</h2>
      <div class="value {'ok' if codeql['total'] == 0 else 'warn'}">{codeql['total']}</div>
      <div><a href="https://github.com/{repo}/security/code-scanning">Security tab &rarr;</a></div>
    </div>
    <div class="card">
      <h2>Dependabot Alerts (open)</h2>
      <div class="value {'ok' if dependabot['total'] == 0 else 'warn'}">{dependabot['total']}</div>
      <div><a href="https://github.com/{repo}/security/dependabot">Security tab &rarr;</a></div>
    </div>
  </div>

  <h2>CodeQL alerts by severity</h2>
  <table><tr><th>Severity</th><th>Count</th></tr>{severity_rows(codeql)}</table>

  <h2>Dependabot alerts by severity</h2>
  <table><tr><th>Severity</th><th>Count</th></tr>{severity_rows(dependabot)}</table>

  <footer>
    Built by the <code>pages.yml</code> workflow &bull; <a href="{run_url}">this run</a>
  </footer>
</body>
</html>
"""
    (SITE / "index.html").write_text(html, encoding="utf-8")
    (SITE / ".nojekyll").touch()


if __name__ == "__main__":
    main()
