#!/usr/bin/env python3
"""Generate index.html linking to all league prediction pages."""

import os
from datetime import datetime

LEAGUES = [
    ("PL", "Premier League", "England"),
    ("ELC", "Championship", "England"),
    ("PD", "La Liga", "Spain"),
    ("BL1", "Bundesliga", "Germany"),
    ("SA", "Serie A", "Italy"),
    ("FL1", "Ligue 1", "France"),
    ("DED", "Eredivisie", "Netherlands"),
    ("PPL", "Primeira Liga", "Portugal"),
]


def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    cards = []
    for code, name, country in LEAGUES:
        filepath = f"html/{code}-predictions.html"
        if os.path.exists(filepath):
            cards.append(f'''
            <a href="{code}-predictions.html" class="league-card">
                <div class="league-country">{country}</div>
                <div class="league-name">{name}</div>
                <div class="league-code">{code}</div>
            </a>''')

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>League Predictions</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700&family=Instrument+Serif&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
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
        --shadow-sm: 0 1px 2px rgba(0,0,0,0.04);
        --shadow-md: 0 2px 8px rgba(0,0,0,0.06);
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
        max-width: 720px;
        margin: 0 auto;
        padding: 64px 24px 80px;
    }}

    h1 {{
        font-family: 'Instrument Serif', serif;
        font-size: 48px;
        font-weight: 400;
        letter-spacing: -0.02em;
        line-height: 1.1;
        margin-bottom: 8px;
    }}

    .subtitle {{
        font-size: 15px;
        color: var(--text-secondary);
        margin-bottom: 40px;
    }}

    .leagues {{
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
        gap: 12px;
    }}

    .league-card {{
        display: block;
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 20px;
        text-decoration: none;
        color: var(--text);
        transition: box-shadow 0.15s, border-color 0.15s;
        box-shadow: var(--shadow-sm);
    }}

    .league-card:hover {{
        box-shadow: var(--shadow-md);
        border-color: var(--accent);
    }}

    .league-country {{
        font-size: 12px;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--text-tertiary);
        margin-bottom: 4px;
    }}

    .league-name {{
        font-size: 18px;
        font-weight: 600;
        margin-bottom: 2px;
    }}

    .league-code {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
        color: var(--text-tertiary);
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
    <h1>League Predictions</h1>
    <div class="subtitle">Monte Carlo simulation-based predictions for domestic football leagues</div>
    <div class="leagues">
        {"".join(cards)}
    </div>
    <div class="footer">
        Updated {now}<br>
        <span style="font-size: 10px;">Disclaimer: These are simulated statistical models for entertainment purposes only. Results are based on publicly available data and are believed to be accurate, but no guarantees are made.</span>
    </div>
</div>
</body>
</html>'''

    os.makedirs("html", exist_ok=True)
    with open("html/index.html", "w") as f:
        f.write(html)
    print("Written to html/index.html")


if __name__ == "__main__":
    main()
