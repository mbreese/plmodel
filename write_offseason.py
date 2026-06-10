#!/usr/bin/env python3
"""Write a placeholder HTML page for a league with no fixture data.

Used when the league CSV is missing or empty (off-season, or fetch failed).
"""

import os
import sys
from datetime import datetime


LEAGUE_NAMES = {
    "PL": ("Premier League", "England"),
    "ELC": ("Championship", "England"),
    "PD": ("La Liga", "Spain"),
    "BL1": ("Bundesliga", "Germany"),
    "SA": ("Serie A", "Italy"),
    "FL1": ("Ligue 1", "France"),
    "DED": ("Eredivisie", "Netherlands"),
    "PPL": ("Primeira Liga", "Portugal"),
}


def render(code):
    name, country = LEAGUE_NAMES.get(code, (code, ""))
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name} — Off-season</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700&family=Instrument+Serif&display=swap" rel="stylesheet">
<style>
    :root {{
        --bg: #fafaf8;
        --surface: #ffffff;
        --border: #e2e0db;
        --border-light: #eeece8;
        --text: #1a1a18;
        --text-secondary: #6b6963;
        --text-tertiary: #9b9790;
        --accent: #1a6b3c;
    }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
        font-family: 'DM Sans', sans-serif;
        background: var(--bg);
        color: var(--text);
        line-height: 1.5;
        -webkit-font-smoothing: antialiased;
    }}
    .container {{
        max-width: 640px;
        margin: 0 auto;
        padding: 64px 24px 80px;
    }}
    .country {{
        font-size: 12px;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--text-tertiary);
        margin-bottom: 8px;
    }}
    h1 {{
        font-family: 'Instrument Serif', serif;
        font-size: 48px;
        font-weight: 400;
        letter-spacing: -0.02em;
        line-height: 1.1;
        margin-bottom: 32px;
    }}
    .notice {{
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 32px;
        margin-bottom: 24px;
    }}
    .notice-label {{
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--accent);
        margin-bottom: 12px;
    }}
    .notice-body {{
        font-size: 16px;
        color: var(--text-secondary);
    }}
    .back-link {{
        display: inline-block;
        font-size: 14px;
        color: var(--text-secondary);
        text-decoration: none;
        border-bottom: 1px solid var(--border);
        padding-bottom: 2px;
        transition: color 0.15s, border-color 0.15s;
    }}
    .back-link:hover {{
        color: var(--accent);
        border-color: var(--accent);
    }}
    .footer {{
        margin-top: 48px;
        padding-top: 20px;
        border-top: 1px solid var(--border-light);
        font-size: 12px;
        color: var(--text-tertiary);
    }}
</style>
</head>
<body>
<div class="container">
    <div class="country">{country}</div>
    <h1>{name}</h1>
    <div class="notice">
        <div class="notice-label">Off-season</div>
        <div class="notice-body">No fixture data is currently available for this league. Predictions will resume once the next season's schedule is published.</div>
    </div>
    <a href="index.html" class="back-link">← All leagues</a>
    <div class="footer">
        Updated {now}
    </div>
</div>
</body>
</html>'''


def main():
    if len(sys.argv) != 2:
        print("Usage: write_offseason.py <league-code>", file=sys.stderr)
        sys.exit(2)
    code = sys.argv[1]
    os.makedirs("html", exist_ok=True)
    path = f"html/{code}-predictions.html"
    with open(path, "w") as f:
        f.write(render(code))
    print(f"Wrote off-season placeholder to {path}")


if __name__ == "__main__":
    main()
