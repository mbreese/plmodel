"""HTML report generator for league simulation results."""

import html
import json
import os
from datetime import datetime


def _pct_color(value, low_hue=0, high_hue=145):
    """Map a 0-100 percentage to a background color.

    Uses HSL: 0% -> transparent, 1-100% -> pale to saturated green.
    For 'danger' columns (relegation), use low_hue (red).
    """
    if value < 0.1:
        return "transparent"
    # Opacity scales with value
    alpha = min(0.08 + (value / 100) * 0.55, 0.63)
    return f"hsla({high_hue}, 72%, 38%, {alpha:.2f})"


def _danger_color(value):
    """Color for relegation/bottom columns — red tones."""
    if value < 0.1:
        return "transparent"
    alpha = min(0.08 + (value / 100) * 0.55, 0.63)
    return f"hsla(4, 72%, 44%, {alpha:.2f})"


def _pos_color(avg_pos, num_teams):
    """Color for average position — gradient from green (1st) to red (last)."""
    ratio = (avg_pos - 1) / max(num_teams - 1, 1)
    hue = 145 * (1 - ratio)
    return f"hsla({hue:.0f}, 50%, 42%, 0.12)"


def generate_report_from_data(data, output_path="html/predictions.html"):
    """Generate an HTML report from a loaded predictions data dict."""
    generate_report(
        data["models"], data["standings"],
        completed=data.get("completed", []),
        remaining=data.get("remaining", []),
        completed_count=data["completed_count"],
        remaining_count=data["remaining_count"],
        iterations=data["iterations"],
        top_n=data["top_n"],
        bottom_n=data["bottom_n"],
        best_worst=data.get("best_worst", {}),
        output_path=output_path,
    )


def generate_report(all_results, standings, completed_count, remaining_count,
                    iterations, top_n, bottom_n, completed=None, remaining=None,
                    best_worst=None, output_path="html/predictions.html"):
    """Generate an HTML report with tabbed results from all models.

    Args:
        all_results: list of dicts with keys: name, model_str, results, and
                     either 'model' (MatchModel instance) or 'team_columns' (pre-computed dict)
        standings: current standings dict
        completed_count: number of completed matches
        remaining_count: number of remaining matches
        iterations: number of MC iterations
        top_n: top N cutoff
        bottom_n: bottom N cutoff
        output_path: output file path
    """
    MODEL_DESCRIPTIONS = {
        "global": "Uses fixed historical base rates for all matches regardless of the teams playing. Default rates: 46% home win, 25% draw, 29% away win. The simplest baseline model — useful as a reference point.",
        "season": "Calculates home win, draw, and away win probabilities from completed matches in the current season. Rates update as more matches are played but do not consider individual team strength. Falls back to global rates if no matches have been completed yet.",
        "poisson": "Estimates per-team attack and defense ratings based on match results, then models expected goals using a Poisson distribution. Supports exponential decay weighting (half-life) to emphasize recent form. Produces expected goals (xG), most likely scorelines, and 95% confidence intervals.",
        "dixoncoles": "Extends the Poisson model with a low-score correlation adjustment (Dixon & Coles, 1997). Estimates a rho parameter that corrects probabilities for common low-scoring outcomes (0-0, 1-0, 0-1, 1-1), producing more realistic scoreline distributions than a standard Poisson model.",
        "negbin": "A negative binomial variant of the Poisson model that accounts for overdispersion — the tendency for real goal distributions to have higher variance than Poisson predicts. Estimates an alpha parameter from season data; when alpha is zero, it reduces to the standard Poisson model.",
        "elo": "Uses the Elo rating system (named after its creator Arpad Elo), which maps rating differences to match outcome probabilities. Each team maintains a rating updated after every match (K-factor = 20). Draw probability is calibrated from observed season draw rates and varies with the rating gap between teams.",
        "elopoisson": "A hybrid model that combines Elo ratings (named after creator Arpad Elo) with Poisson goal sampling. Converts the Elo rating difference into expected goals using league averages, then samples scorelines from a Poisson distribution. Benefits from Elo's implicit time-weighting while producing full scoreline predictions.",
    }

    num_teams = len(standings)
    sorted_standings = sorted(
        standings.items(),
        key=lambda x: (x[1]["points"], x[1]["gd"], x[1]["gf"]),
        reverse=True,
    )
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Derive current league code from output path
    output_base = os.path.splitext(os.path.basename(output_path))[0]
    current_league = output_base.replace("-predictions", "")

    LEAGUE_NAMES = {
        "PL": "Premier League",
        "ELC": "Championship",
        "PD": "La Liga",
        "BL1": "Bundesliga",
        "SA": "Serie A",
        "FL1": "Ligue 1",
        "DED": "Eredivisie",
        "PPL": "Primeira Liga",
    }

    league_title = LEAGUE_NAMES.get(current_league, current_league)

    # Build league nav links
    league_nav_html = ""
    for code, name in LEAGUE_NAMES.items():
        cls = "current" if code == current_league else ""
        league_nav_html += f'<a href="{code}-predictions.html" class="{cls}">{name}</a>\n'

    # Build tab data — standings is the first tab
    tabs_html = [
        '<button class="tab active" data-panel="panel-standings" onclick="switchTab(this)">Standings</button>'
    ]
    panels_html = []

    for idx, entry in enumerate(all_results):
        name = entry["name"]
        model_str = entry["model_str"]
        results = entry["results"]
        model = entry.get("model")
        team_columns_data = entry.get("team_columns", {})

        def _get_team_columns(team):
            if model:
                return model.team_columns(team)
            return team_columns_data.get(team, [])

        panel_id = f"panel-{idx}"

        tabs_html.append(
            f'<button class="tab" data-panel="{panel_id}" onclick="switchTab(this)">'
            f'{html.escape(name)}</button>'
        )

        # Extra columns
        extra_headers = []
        if results:
            cols = _get_team_columns(results[0]["team"])
            extra_headers = [h for h, _ in cols]

        # Check if this model has GD data
        has_gd = results and results[0]["gd_ci"] is not None

        # Build table rows
        rows = []
        for i, r in enumerate(results):
            team = html.escape(r["team"])
            avg = r["avg_pos"]
            first = r["first_pct"]
            top = r["top_pct"]
            bot = r["bottom_pct"]
            last = r["last_pct"]

            extra_cells = ""
            for hdr, val in _get_team_columns(r["team"]):
                extra_cells += f'<td class="stat-cell extra-col">{html.escape(str(val))}</td>'

            pts_gd_cells = ""
            if has_gd:
                pts_lo, pts_hi = r["pts_ci"]
                gd_lo, gd_hi = r["gd_ci"]
                gd_lo_s = f"+{gd_lo}" if gd_lo > 0 else str(gd_lo)
                gd_hi_s = f"+{gd_hi}" if gd_hi > 0 else str(gd_hi)
                pts_gd_cells = (
                    f'<td class="stat-cell ci-cell">{pts_lo}–{pts_hi}</td>'
                    f'<td class="stat-cell ci-cell">{gd_lo_s}–{gd_hi_s}</td>'
                )

            row_class = ""
            if i < top_n:
                row_class = "zone-top"
            elif i >= num_teams - bottom_n:
                row_class = "zone-bottom"

            ci = f"{r['ci_low']}–{r['ci_high']}"

            rows.append(f'''<tr class="{row_class}">
                <td class="pos-cell">{i + 1}</td>
                <td class="team-cell clickable" onclick="showTeamDetail('{team}')">{team}</td>
                <td class="stat-cell avg-cell" style="background:{_pos_color(avg, num_teams)}">{avg:.1f}</td>
                <td class="stat-cell ci-cell">{ci}</td>
                {pts_gd_cells}
                <td class="stat-cell pct-cell" style="background:{_pct_color(first)}">{first:.1f}%</td>
                <td class="stat-cell pct-cell" style="background:{_pct_color(top)}">{top:.1f}%</td>
                <td class="stat-cell pct-cell danger" style="background:{_danger_color(bot)}">{bot:.1f}%</td>
                <td class="stat-cell pct-cell danger" style="background:{_danger_color(last)}">{last:.1f}%</td>
                {extra_cells}
            </tr>''')

        extra_th = "".join(f'<th class="extra-col">{html.escape(h)}</th>' for h in extra_headers)
        pts_gd_th = '<th>Pts CI</th><th>GD CI</th>' if has_gd else ''

        model_desc = MODEL_DESCRIPTIONS.get(name, "")
        about_link = f'<a href="#" class="model-about-link" onclick="event.preventDefault();showModelAbout(\'{html.escape(name)}\')">about this model</a>' if model_desc else ""

        panel_html = f'''
        <div class="panel" id="{panel_id}">
            <div class="model-info">{html.escape(model_str)}{about_link}</div>
            <table>
                <thead>
                    <tr>
                        <th class="pos-col">#</th>
                        <th class="team-col">Team</th>
                        <th>Avg Pos</th>
                        <th>95% CI</th>
                        {pts_gd_th}
                        <th>1st</th>
                        <th>Top {top_n}</th>
                        <th>Bot {bottom_n}</th>
                        <th>Last</th>
                        {extra_th}
                    </tr>
                </thead>
                <tbody>
                    {"".join(rows)}
                </tbody>
            </table>
        </div>'''
        panels_html.append(panel_html)

    # Build standings panel (first tab)
    standings_rows = []
    for i, (team, s) in enumerate(sorted_standings):
        row_class = ""
        if i < top_n:
            row_class = "zone-top"
        elif i >= num_teams - bottom_n:
            row_class = "zone-bottom"
        gd = s["gd"]
        gd_str = f"+{gd}" if gd > 0 else str(gd)
        ded = s.get("deduction", 0)
        ded_str = f' <span class="deduction">(-{ded})</span>' if ded else ""
        bw = best_worst.get(team, {}) if best_worst else {}
        best = bw.get("best", "")
        worst = bw.get("worst", "")
        max_pts = bw.get("max_pts", "")
        min_pts = bw.get("min_pts", "")
        bw_pts = f"{min_pts}–{max_pts}" if max_pts != "" else ""
        bw_pos = f"{best}–{worst}" if best != "" else ""
        standings_rows.append(f'''<tr class="{row_class}">
            <td class="pos-cell">{i + 1}</td>
            <td class="team-cell clickable" onclick="showTeamDetail('{html.escape(team)}')">{html.escape(team)}</td>
            <td class="stat-cell">{s["played"]}</td>
            <td class="stat-cell">{s["wins"]}</td>
            <td class="stat-cell">{s["draws"]}</td>
            <td class="stat-cell">{s["losses"]}</td>
            <td class="stat-cell">{s["gf"]}</td>
            <td class="stat-cell">{s["ga"]}</td>
            <td class="stat-cell gd-cell">{gd_str}</td>
            <td class="stat-cell pts-cell">{s["points"]}{ded_str}</td>
            <td class="stat-cell ci-cell">{bw_pts}</td>
            <td class="stat-cell ci-cell">{bw_pos}</td>
        </tr>''')

    standings_panel = f'''
        <div class="panel active" id="panel-standings">
            <div class="model-info">Current league table — {completed_count} matches played, {remaining_count} remaining</div>
            <table>
                <thead>
                    <tr>
                        <th class="pos-col">#</th>
                        <th class="team-col">Team</th>
                        <th>P</th>
                        <th>W</th>
                        <th>D</th>
                        <th>L</th>
                        <th>GF</th>
                        <th>GA</th>
                        <th>GD</th>
                        <th>Pts</th>
                        <th>Pts Range</th>
                        <th>Pos Range</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(standings_rows)}
                </tbody>
            </table>
        </div>'''
    panels_html.insert(0, standings_panel)

    # Build fixture data JSON for team detail view
    fixture_data = {
        "completed": completed or [],
        "remaining": remaining or [],
        "models": [],
    }
    for entry in all_results:
        # match_predictions may come from saved JSON or need computing from model
        match_preds = entry.get("match_predictions", [])
        if not match_preds and entry.get("model") and remaining:
            model = entry["model"]
            for m in remaining:
                detail = model.predict_match_detail(m["home"], m["away"])
                if detail:
                    detail["home"] = m["home"]
                    detail["away"] = m["away"]
                    match_preds.append(detail)
        fixture_data["models"].append({
            "name": entry["name"],
            "match_predictions": match_preds,
        })
    fixture_data_json = json.dumps(fixture_data)

    page_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{league_title} — Predictions</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=Instrument+Serif&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
    :root {{
        --white: #ffffff;
        --bg: #fafaf8;
        --surface: #ffffff;
        --border: #e2e0db;
        --border-light: #eeece8;
        --text: #1a1a18;
        --text-secondary: #6b6963;
        --text-tertiary: #9b9790;
        --accent: #1a6b3c;
        --accent-light: #e8f5ee;
        --danger: #a62e1f;
        --danger-light: #fceae8;
        --tab-hover: #f0eeea;
        --tab-active-border: #1a1a18;
        --zone-top-border: #2d9a5a;
        --zone-bottom-border: #c4493a;
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
        max-width: 960px;
        margin: 0 auto;
        padding: 48px 24px 80px;
    }}

    .header {{
        margin-bottom: 40px;
    }}

    .header-top {{
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 16px;
    }}

    .header h1 {{
        font-family: 'Instrument Serif', serif;
        font-size: 42px;
        font-weight: 400;
        letter-spacing: -0.02em;
        line-height: 1.1;
        margin-bottom: 12px;
    }}

    .league-menu {{
        position: relative;
    }}

    .league-menu-btn {{
        background: none;
        border: 1px solid var(--border);
        border-radius: 6px;
        padding: 8px 10px;
        cursor: pointer;
        display: flex;
        flex-direction: column;
        gap: 4px;
        transition: background 0.15s;
    }}

    .league-menu-btn:hover {{
        background: var(--tab-hover);
    }}

    .league-menu-btn span {{
        display: block;
        width: 18px;
        height: 2px;
        background: var(--text);
        border-radius: 1px;
    }}

    .league-menu-dropdown {{
        display: none;
        position: absolute;
        top: calc(100% + 6px);
        right: 0;
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 8px;
        box-shadow: var(--shadow-md);
        min-width: 200px;
        z-index: 50;
        overflow: hidden;
    }}

    .league-menu-dropdown.open {{
        display: block;
    }}

    .league-menu-dropdown a {{
        display: block;
        padding: 10px 16px;
        text-decoration: none;
        font-size: 14px;
        color: var(--text-secondary);
        transition: background 0.1s;
        border-bottom: 1px solid var(--border-light);
    }}

    .league-menu-dropdown a:last-child {{
        border-bottom: none;
    }}

    .league-menu-dropdown a:hover {{
        background: var(--tab-hover);
        color: var(--text);
    }}

    .league-menu-dropdown a.current {{
        font-weight: 600;
        color: var(--text);
        background: var(--bg);
    }}

    .header .subtitle {{
        font-size: 15px;
        color: var(--text-secondary);
        display: flex;
        gap: 20px;
        flex-wrap: wrap;
    }}

    .header .subtitle span {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }}

    .header .subtitle .dot {{
        width: 4px;
        height: 4px;
        border-radius: 50%;
        background: var(--text-tertiary);
        display: inline-block;
    }}

    /* Standings Section */
    .section {{
        margin-bottom: 48px;
    }}

    .section-title {{
        font-family: 'DM Sans', sans-serif;
        font-size: 13px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--text-tertiary);
        margin-bottom: 16px;
    }}

    .card {{
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 8px;
        overflow: hidden;
        box-shadow: var(--shadow-sm);
    }}

    /* Tabs */
    .tabs {{
        display: flex;
        gap: 0;
        border-bottom: 1px solid var(--border);
        background: var(--surface);
        border-radius: 8px 8px 0 0;
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
    }}

    .tab {{
        font-family: 'DM Sans', sans-serif;
        font-size: 13px;
        font-weight: 500;
        padding: 14px 20px;
        border: none;
        background: transparent;
        color: var(--text-secondary);
        cursor: pointer;
        white-space: nowrap;
        position: relative;
        transition: color 0.15s, background 0.15s;
    }}

    .tab:hover {{
        color: var(--text);
        background: var(--tab-hover);
    }}

    .tab.active {{
        color: var(--text);
        font-weight: 600;
    }}

    .tab.active::after {{
        content: '';
        position: absolute;
        bottom: -1px;
        left: 12px;
        right: 12px;
        height: 2px;
        background: var(--tab-active-border);
        border-radius: 2px 2px 0 0;
    }}

    /* Panels */
    .panel {{
        display: none;
    }}

    .panel.active {{
        display: block;
    }}

    .model-info {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
        color: var(--text-tertiary);
        padding: 14px 20px;
        border-bottom: 1px solid var(--border-light);
        background: var(--bg);
    }}

    /* Tables */
    table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 14px;
    }}

    thead th {{
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--text-tertiary);
        padding: 10px 12px;
        text-align: right;
        border-bottom: 1px solid var(--border);
        background: var(--white);
        position: sticky;
        top: 0;
    }}

    thead th.pos-col,
    thead th.team-col {{
        text-align: left;
    }}

    thead th.pos-col {{
        width: 36px;
        padding-left: 20px;
    }}

    thead th.team-col {{
        width: 200px;
    }}

    tbody tr {{
        transition: background 0.1s;
    }}

    tbody tr:hover {{
        background: rgba(0,0,0,0.018);
    }}

    tbody tr:not(:last-child) td {{
        border-bottom: 1px solid var(--border-light);
    }}

    td {{
        padding: 9px 12px;
    }}

    .pos-cell {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
        color: var(--text-tertiary);
        width: 36px;
        padding-left: 20px;
    }}

    .team-cell {{
        font-weight: 500;
        font-size: 14px;
    }}

    .team-cell.clickable {{
        cursor: pointer;
        color: var(--accent);
    }}

    .team-cell.clickable:hover {{
        text-decoration: underline;
    }}

    /* Team detail overlay */
    .team-detail-overlay {{
        display: none;
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(0,0,0,0.3);
        z-index: 100;
        overflow-y: auto;
        padding: 40px 20px;
    }}

    .team-detail-overlay.visible {{
        display: block;
    }}

    .team-detail {{
        max-width: 900px;
        margin: 0 auto;
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 10px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.12);
        overflow: hidden;
    }}

    .team-detail-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 20px 24px;
        border-bottom: 1px solid var(--border);
    }}

    .team-detail-header h2 {{
        font-family: 'Instrument Serif', serif;
        font-size: 28px;
        font-weight: 400;
    }}

    .team-detail-close {{
        background: none;
        border: 1px solid var(--border);
        border-radius: 6px;
        padding: 6px 14px;
        font-family: 'DM Sans', sans-serif;
        font-size: 13px;
        cursor: pointer;
        color: var(--text-secondary);
    }}

    .team-detail-close:hover {{
        background: var(--tab-hover);
        color: var(--text);
    }}

    .team-detail-section {{
        padding: 16px 24px 8px;
        font-size: 13px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--text-tertiary);
    }}

    .team-detail table {{
        font-size: 13px;
    }}

    .team-detail .result-w {{ color: var(--accent); font-weight: 600; }}
    .team-detail .result-d {{ color: var(--text-secondary); font-weight: 500; }}
    .team-detail .result-l {{ color: var(--danger); font-weight: 600; }}

    .match-predictions {{
        padding: 8px 24px 16px;
    }}

    .match-pred-row {{
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
        margin-bottom: 4px;
    }}

    .match-pred-tag {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
        padding: 2px 8px;
        border-radius: 3px;
        background: var(--bg);
        border: 1px solid var(--border-light);
        color: var(--text-secondary);
    }}

    .prob-bar-container {{
        display: flex;
        height: 6px;
        border-radius: 3px;
        overflow: hidden;
        margin: 4px 0;
    }}

    .prob-bar-home {{ background: var(--accent); }}
    .prob-bar-draw {{ background: var(--text-tertiary); }}
    .prob-bar-away {{ background: var(--danger); }}

    /* Fixture cards */
    .fixture-card {{
        border: 1px solid var(--border-light);
        border-radius: 6px;
        margin: 12px 24px;
        overflow: hidden;
    }}

    .fixture-header {{
        padding: 12px 16px;
        background: var(--bg);
        border-bottom: 1px solid var(--border-light);
    }}

    .fixture-meta {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
        color: var(--text-tertiary);
        margin-bottom: 4px;
    }}

    .fixture-teams {{
        font-size: 16px;
        font-weight: 500;
    }}

    .fixture-home {{
        color: var(--accent);
    }}

    .fixture-vs {{
        color: var(--text-tertiary);
        font-size: 13px;
        margin: 0 8px;
    }}

    .fixture-away {{
        color: var(--danger);
    }}

    .fixture-predictions {{
        padding: 8px;
    }}

    .pred-table {{
        font-size: 12px;
    }}

    .pred-table th {{
        font-size: 10px;
        padding: 6px 8px;
    }}

    .pred-table td {{
        padding: 5px 8px;
    }}

    .pred-model {{
        font-weight: 600;
        font-size: 11px;
        color: var(--text-secondary);
        white-space: nowrap;
    }}

    .pred-details {{
        font-size: 11px;
    }}

    .stat-cell {{
        text-align: right;
        font-family: 'JetBrains Mono', monospace;
        font-size: 13px;
    }}

    .pts-cell {{
        font-weight: 700;
    }}

    .gd-cell {{
        font-weight: 500;
    }}

    .deduction {{
        font-size: 11px;
        color: var(--danger);
        font-weight: 400;
    }}

    .pct-cell {{
        border-radius: 3px;
        padding: 6px 10px;
        margin: 2px 0;
    }}

    .avg-cell {{
        border-radius: 3px;
        padding: 6px 10px;
    }}

    .extra-col {{
        color: var(--text-secondary);
        font-size: 12px;
    }}

    /* Zone indicators */
    tr.zone-top td:first-child {{
        box-shadow: inset 3px 0 0 var(--zone-top-border);
    }}

    tr.zone-bottom td:first-child {{
        box-shadow: inset 3px 0 0 var(--zone-bottom-border);
    }}

    /* Legend */
    .legend {{
        display: flex;
        gap: 24px;
        padding: 14px 20px;
        border-top: 1px solid var(--border-light);
        font-size: 12px;
        color: var(--text-tertiary);
    }}

    .legend-item {{
        display: flex;
        align-items: center;
        gap: 8px;
    }}

    .legend-swatch {{
        width: 3px;
        height: 14px;
        border-radius: 2px;
    }}

    .legend-swatch.top {{ background: var(--zone-top-border); }}
    .legend-swatch.bottom {{ background: var(--zone-bottom-border); }}

    /* Model about link */
    .model-about-link {{
        float: right;
        font-family: 'DM Sans', sans-serif;
        font-size: 12px;
        color: var(--text-tertiary);
        text-decoration: none;
        cursor: pointer;
    }}

    .model-about-link:hover {{
        color: var(--accent);
        text-decoration: underline;
    }}

    /* Model about modal */
    .model-about-overlay {{
        display: none;
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(0,0,0,0.3);
        z-index: 200;
        padding: 40px 20px;
        overflow-y: auto;
    }}

    .model-about-overlay.visible {{
        display: flex;
        align-items: center;
        justify-content: center;
    }}

    .model-about-box {{
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 10px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.12);
        max-width: 480px;
        width: 100%;
        overflow: hidden;
    }}

    .model-about-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 18px 24px;
        border-bottom: 1px solid var(--border);
    }}

    .model-about-header h3 {{
        font-family: 'Instrument Serif', serif;
        font-size: 22px;
        font-weight: 400;
    }}

    .model-about-body {{
        padding: 20px 24px;
        font-size: 14px;
        line-height: 1.65;
        color: var(--text-secondary);
    }}

    /* Footer */
    .footer {{
        margin-top: 48px;
        padding-top: 20px;
        border-top: 1px solid var(--border-light);
        font-size: 12px;
        color: var(--text-tertiary);
    }}

    @media (max-width: 640px) {{
        .container {{ padding: 24px 12px 60px; }}
        .header h1 {{ font-size: 28px; }}
        table {{ font-size: 12px; }}
        .tab {{ padding: 10px 14px; font-size: 12px; }}
        td, thead th {{ padding: 7px 8px; }}
        .pos-cell, thead th.pos-col {{ padding-left: 12px; }}
    }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <div class="header-top">
            <h1>{league_title}</h1>
            <div class="league-menu">
                <button class="league-menu-btn" onclick="document.getElementById('league-dropdown').classList.toggle('open')" aria-label="Switch league">
                    <span></span><span></span><span></span>
                </button>
                <div class="league-menu-dropdown" id="league-dropdown">
                    {league_nav_html}
                </div>
            </div>
        </div>
        <div class="subtitle">
            <span>{completed_count} matches played</span>
            <span class="dot"></span>
            <span>{remaining_count} remaining</span>
            <span class="dot"></span>
            <span>{iterations:,} simulations per model</span>
        </div>
    </div>

    <div class="section">
        <div class="card">
            <div class="tabs">
                {"".join(tabs_html)}
            </div>
            {"".join(panels_html)}
            <div class="legend">
                <div class="legend-item">
                    <div class="legend-swatch top"></div>
                    Top {top_n}
                </div>
                <div class="legend-item">
                    <div class="legend-swatch bottom"></div>
                    Bottom {bottom_n}
                </div>
            </div>
        </div>
    </div>

    <div class="footer">
        Generated {now}<br>
        <span style="font-size: 10px;">Disclaimer: These are simulated statistical models for entertainment purposes only. Results are based on publicly available data and are believed to be accurate, but no guarantees are made.</span>
    </div>
</div>

<div class="team-detail-overlay" id="team-detail-overlay" onclick="if(event.target===this)closeTeamDetail()">
    <div class="team-detail" id="team-detail"></div>
</div>

<div class="model-about-overlay" id="model-about-overlay" onclick="if(event.target===this)closeModelAbout()">
    <div class="model-about-box">
        <div class="model-about-header">
            <h3 id="model-about-title"></h3>
            <button class="team-detail-close" onclick="closeModelAbout()">Close</button>
        </div>
        <div class="model-about-body" id="model-about-body"></div>
    </div>
</div>

<script>
const FIXTURE_DATA = {fixture_data_json};

const MODEL_DESCS = {json.dumps({name: desc for name, desc in MODEL_DESCRIPTIONS.items()})};

const MODEL_TITLES = {{
    "global": "Global Rate",
    "season": "Season Rate",
    "poisson": "Poisson",
    "dixoncoles": "Dixon-Coles",
    "negbin": "Negative Binomial",
    "elo": "Elo",
    "elopoisson": "Elo-Poisson",
}};

function showModelAbout(name) {{
    document.getElementById('model-about-title').textContent = MODEL_TITLES[name] || name;
    document.getElementById('model-about-body').textContent = MODEL_DESCS[name] || '';
    document.getElementById('model-about-overlay').classList.add('visible');
    document.body.style.overflow = 'hidden';
}}

function closeModelAbout() {{
    document.getElementById('model-about-overlay').classList.remove('visible');
    if (!document.getElementById('team-detail-overlay').classList.contains('visible')) {{
        document.body.style.overflow = '';
    }}
}}

function switchTab(btn) {{
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(btn.dataset.panel).classList.add('active');
}}

function probBg(p, type) {{
    const alpha = Math.min(0.06 + p * 0.4, 0.45);
    if (type === 'home') return `hsla(145, 72%, 38%, ${{alpha.toFixed(2)}})`;
    if (type === 'away') return `hsla(4, 72%, 44%, ${{alpha.toFixed(2)}})`;
    return `hsla(40, 20%, 50%, ${{alpha.toFixed(2)}})`;
}}

function showTeamDetail(team) {{
    const completed = FIXTURE_DATA.completed.filter(m => m.home === team || m.away === team);
    const remaining = FIXTURE_DATA.remaining.filter(m => m.home === team || m.away === team);
    const models = FIXTURE_DATA.models;

    // Sort by date
    completed.sort((a, b) => (a.date || '').localeCompare(b.date || ''));
    remaining.sort((a, b) => (a.date || '').localeCompare(b.date || ''));

    let h = `<div class="team-detail-header">
        <h2>${{team}}</h2>
        <button class="team-detail-close" onclick="closeTeamDetail()">Close</button>
    </div>`;

    // Completed matches
    h += `<div class="team-detail-section">Completed (${{completed.length}})</div>`;
    h += `<table><thead><tr>
        <th>MD</th><th>Date</th><th class="team-col">Opponent</th>
        <th>Score</th><th>Result</th>
    </tr></thead><tbody>`;

    for (const m of completed) {{
        const isHome = m.home === team;
        const opponent = isHome ? m.away : m.home;
        const venue = isHome ? '(H)' : '(A)';
        const score = isHome ? `${{m.home_goals}}-${{m.away_goals}}` : `${{m.away_goals}}-${{m.home_goals}}`;

        let result, cls;
        if (m.home_goals === m.away_goals) {{
            result = 'D'; cls = 'result-d';
        }} else if ((isHome && m.home_goals > m.away_goals) || (!isHome && m.away_goals > m.home_goals)) {{
            result = 'W'; cls = 'result-w';
        }} else {{
            result = 'L'; cls = 'result-l';
        }}

        h += `<tr>
            <td class="stat-cell">${{m.matchday || ''}}</td>
            <td class="stat-cell">${{m.date || ''}}</td>
            <td class="team-cell">${{venue}} ${{opponent}}</td>
            <td class="stat-cell">${{score}}</td>
            <td class="stat-cell ${{cls}}">${{result}}</td>
        </tr>`;
    }}
    h += `</tbody></table>`;

    // Remaining fixtures with predictions
    if (remaining.length > 0) {{
        h += `<div class="team-detail-section">Upcoming (${{remaining.length}})</div>`;

        for (const m of remaining) {{
            const md = m.matchday ? `MD${{m.matchday}}` : '';
            const date = m.date || '';
            const meta = [md, date].filter(Boolean).join(' \u2014 ');

            h += `<div class="fixture-card">
                <div class="fixture-header">
                    <div class="fixture-meta">${{meta}}</div>
                    <div class="fixture-teams">
                        <span class="fixture-home">${{m.home}}</span>
                        <span class="fixture-vs">vs</span>
                        <span class="fixture-away">${{m.away}}</span>
                    </div>
                </div>
                <div class="fixture-predictions">
                    <table class="pred-table">
                        <thead><tr>
                            <th>Model</th>
                            <th>${{m.home}} %</th>
                            <th>Draw</th>
                            <th>${{m.away}} %</th>
                            <th>Score</th>
                            <th>xG</th>
                            <th>Details</th>
                        </tr></thead>
                        <tbody>`;

            for (const model of models) {{
                const pred = model.match_predictions.find(
                    p => p.home === m.home && p.away === m.away
                );
                if (!pred) continue;

                const pH = (pred.p_home * 100).toFixed(0);
                const pD = (pred.p_draw * 100).toFixed(0);
                const pA = (pred.p_away * 100).toFixed(0);

                const score = pred.mode_score ? `${{pred.mode_score[0]}}\u2013${{pred.mode_score[1]}}` : '\u2014';
                const xg = pred.home_xg !== undefined ? `${{pred.home_xg}}\u2013${{pred.away_xg}}` : '\u2014';

                let details = [];
                if (pred.home_goals_ci) {{
                    details.push(`Goals: ${{pred.home_goals_ci[0]}}\u2013${{pred.home_goals_ci[1]}} v ${{pred.away_goals_ci[0]}}\u2013${{pred.away_goals_ci[1]}}`);
                }}
                if (pred.home_elo !== undefined) {{
                    details.push(`Elo: ${{Math.round(pred.home_elo)}} v ${{Math.round(pred.away_elo)}}`);
                }}
                if (pred.home_attack !== undefined) {{
                    details.push(`Atk: ${{pred.home_attack}} v ${{pred.away_attack}}`);
                    details.push(`Def: ${{pred.home_defense}} v ${{pred.away_defense}}`);
                }}

                h += `<tr>
                    <td class="pred-model">${{model.name}}</td>
                    <td class="stat-cell" style="background:${{probBg(pred.p_home, 'home')}}"><strong>${{pH}}%</strong></td>
                    <td class="stat-cell" style="background:${{probBg(pred.p_draw, 'draw')}}"><strong>${{pD}}%</strong></td>
                    <td class="stat-cell" style="background:${{probBg(pred.p_away, 'away')}}"><strong>${{pA}}%</strong></td>
                    <td class="stat-cell">${{score}}</td>
                    <td class="stat-cell">${{xg}}</td>
                    <td class="stat-cell pred-details">${{details.map(d => `<span class="match-pred-tag">${{d}}</span>`).join(' ')}}</td>
                </tr>`;
            }}

            h += `</tbody></table></div></div>`;
        }}
    }}

    document.getElementById('team-detail').innerHTML = h;
    document.getElementById('team-detail-overlay').classList.add('visible');
    document.body.style.overflow = 'hidden';
}}

function closeTeamDetail() {{
    document.getElementById('team-detail-overlay').classList.remove('visible');
    document.body.style.overflow = '';
}}

document.addEventListener('keydown', e => {{
    if (e.key === 'Escape') {{
        closeModelAbout();
        closeTeamDetail();
        document.getElementById('league-dropdown').classList.remove('open');
    }}
}});

document.addEventListener('click', e => {{
    const menu = document.querySelector('.league-menu');
    if (menu && !menu.contains(e.target)) {{
        document.getElementById('league-dropdown').classList.remove('open');
    }}
}});
</script>
</body>
</html>'''

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(page_html)
