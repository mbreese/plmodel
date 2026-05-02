import csv
import os
import random
from collections import defaultdict

from models import GlobalRateModel


def load_fixtures(filepath):
    """Load fixtures CSV, split into completed results and remaining fixtures.

    Supports multiple formats:
    - football-data.co.uk: columns HomeTeam, AwayTeam, FTHG, FTAG
    - football-data.org (via fetch.py): columns HomeTeam, AwayTeam, FTHG, FTAG, Date, Time
    - Simple format: columns home, away, home_goals, away_goals

    Rows with scores are completed matches. Rows without scores (or missing
    entirely) are remaining fixtures. Any home/away pair not present in the
    file at all is also added as a remaining fixture (with no date).
    """
    completed = []
    remaining = []
    teams = set()
    seen_pairs = set()

    with open(filepath, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames

        # Detect format
        if "HomeTeam" in fieldnames:
            home_col, away_col = "HomeTeam", "AwayTeam"
            hg_col, ag_col = "FTHG", "FTAG"
        else:
            home_col, away_col = "home", "away"
            hg_col, ag_col = "home_goals", "away_goals"

        has_date = "Date" in fieldnames
        has_matchday = "Matchday" in fieldnames

        for row in reader:
            home = row[home_col].strip()
            away = row[away_col].strip()
            teams.add(home)
            teams.add(away)
            seen_pairs.add((home, away))

            home_goals = row.get(hg_col, "").strip()
            away_goals = row.get(ag_col, "").strip()

            date = row.get("Date", "").strip() if has_date else ""
            time_ = row.get("Time", "").strip() if has_date else ""
            matchday = row.get("Matchday", "").strip() if has_matchday else ""

            if home_goals != "" and away_goals != "":
                completed.append({
                    "home": home,
                    "away": away,
                    "home_goals": int(home_goals),
                    "away_goals": int(away_goals),
                    "date": date,
                    "time": time_,
                    "matchday": matchday,
                })
            else:
                remaining.append({
                    "home": home,
                    "away": away,
                    "date": date,
                    "time": time_,
                    "matchday": matchday,
                })

    # Also add any missing home/away pairs not in the file at all
    for home in sorted(teams):
        for away in sorted(teams):
            if home != away and (home, away) not in seen_pairs:
                remaining.append({"home": home, "away": away, "date": "", "time": "", "matchday": ""})

    return completed, remaining


def load_deductions(fixtures_path):
    """Load point deductions from a companion CSV file.

    For a fixtures file at data/E1.csv, looks for data/E1-deductions.csv.
    Format: team,points (points is a positive integer to deduct).
    Returns a dict of {team: points_deducted}.
    """
    base = os.path.splitext(fixtures_path)[0]
    deductions_path = f"{base}-deductions.csv"

    deductions = {}
    if os.path.exists(deductions_path):
        with open(deductions_path) as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    team = row[0].strip()
                    try:
                        pts = int(row[1].strip())
                        deductions[team] = pts
                    except ValueError:
                        # Skip header row or malformed lines
                        pass
    return deductions


def build_standings(completed, deductions=None):
    """Build current standings from completed match results."""
    standings = defaultdict(lambda: {
        "played": 0, "wins": 0, "draws": 0, "losses": 0,
        "gf": 0, "ga": 0, "gd": 0, "points": 0,
    })

    for match in completed:
        home = match["home"]
        away = match["away"]
        hg = match["home_goals"]
        ag = match["away_goals"]

        standings[home]["played"] += 1
        standings[away]["played"] += 1

        standings[home]["gf"] += hg
        standings[home]["ga"] += ag
        standings[home]["gd"] += hg - ag
        standings[away]["gf"] += ag
        standings[away]["ga"] += hg
        standings[away]["gd"] += ag - hg

        if hg > ag:
            standings[home]["wins"] += 1
            standings[home]["points"] += 3
            standings[away]["losses"] += 1
        elif hg == ag:
            standings[home]["draws"] += 1
            standings[home]["points"] += 1
            standings[away]["draws"] += 1
            standings[away]["points"] += 1
        else:
            standings[away]["wins"] += 1
            standings[away]["points"] += 3
            standings[home]["losses"] += 1

    # Apply point deductions
    if deductions:
        for team, pts in deductions.items():
            if team in standings:
                standings[team]["points"] -= pts
                standings[team]["deduction"] = pts

    return dict(standings)


def compute_best_worst(standings, remaining, iterations=50000):
    """Compute best and worst possible finishing positions for each team.

    Uses Monte Carlo simulation with constrained outcomes:
    - Best: team wins all remaining, other matches get uniform random outcomes
    - Worst: team loses all remaining, other matches get uniform random outcomes

    Tracks the extreme positions seen across iterations to find tight bounds
    that respect fixture constraints (teams playing each other can't both lose).

    Returns dict of {team: {"best": int, "worst": int, "max_pts": int, "min_pts": int}}.
    """
    teams = list(standings.keys())
    num_teams = len(teams)

    # Count remaining matches per team for max/min pts
    remaining_count = defaultdict(int)
    for m in remaining:
        remaining_count[m["home"]] += 1
        remaining_count[m["away"]] += 1

    # Precompute which matches involve each team vs not
    team_matches = {}
    other_matches = {}
    for team in teams:
        mine = []
        others = []
        for m in remaining:
            if m["home"] == team or m["away"] == team:
                mine.append(m)
            else:
                others.append(m)
        team_matches[team] = mine
        other_matches[team] = others

    result = {}
    for team in teams:
        current_pts = standings[team]["points"]
        max_pts = current_pts + 3 * remaining_count[team]
        min_pts = current_pts

        mine = team_matches[team]
        others = other_matches[team]

        best_pos = num_teams
        worst_pos = 1

        for _ in range(iterations):
            # --- Best case: team wins all ---
            points_best = {t: standings[t]["points"] for t in teams}
            points_best[team] = max_pts
            # Other matches involving this team: opponents get 0
            # Other matches not involving this team: random
            for m in others:
                r = random.random()
                if r < 1.0 / 3:
                    points_best[m["home"]] += 3
                elif r < 2.0 / 3:
                    points_best[m["home"]] += 1
                    points_best[m["away"]] += 1
                else:
                    points_best[m["away"]] += 3

            ranked = sorted(teams, key=lambda t: (points_best[t], random.random()), reverse=True)
            pos = ranked.index(team) + 1
            if pos < best_pos:
                best_pos = pos

            # --- Worst case: team loses all ---
            points_worst = {t: standings[t]["points"] for t in teams}
            # team stays at current points
            # opponents in team's matches get 3 pts each
            for m in mine:
                opp = m["away"] if m["home"] == team else m["home"]
                points_worst[opp] += 3
            # Other matches: random
            for m in others:
                r = random.random()
                if r < 1.0 / 3:
                    points_worst[m["home"]] += 3
                elif r < 2.0 / 3:
                    points_worst[m["home"]] += 1
                    points_worst[m["away"]] += 1
                else:
                    points_worst[m["away"]] += 3

            ranked = sorted(teams, key=lambda t: (points_worst[t], random.random()), reverse=True)
            pos = ranked.index(team) + 1
            if pos > worst_pos:
                worst_pos = pos

        result[team] = {
            "best": best_pos,
            "worst": worst_pos,
            "max_pts": max_pts,
            "min_pts": min_pts,
        }

    return result


def simulate_season(standings, remaining, completed=None, model=None, iterations=10000):
    """Run Monte Carlo simulation of remaining fixtures.

    Args:
        standings: Current standings dict from build_standings()
        remaining: List of remaining fixture dicts
        completed: List of completed match dicts (passed to model.setup())
        model: A MatchModel instance (defaults to GlobalRateModel)
        iterations: Number of simulations to run

    Returns a dict: {team: {position: count}} across all iterations.
    """
    if model is None:
        model = GlobalRateModel()

    model.setup(standings, completed or [])

    teams = sorted(standings.keys())
    position_counts = {team: defaultdict(int) for team in teams}
    points_dist = {team: defaultdict(int) for team in teams}
    gd_dist = {team: defaultdict(int) for team in teams}

    # Check if model supports scoreline prediction (for GD tiebreaker)
    has_scores = model.predict_score(teams[0], teams[1]) is not None

    # Compute current GD from completed matches
    base_gd = {team: standings[team]["gd"] for team in teams}

    for _ in range(iterations):
        points = {team: standings[team]["points"] for team in teams}
        gd = {team: base_gd[team] for team in teams}

        for match in remaining:
            home, away = match["home"], match["away"]

            if has_scores:
                hg, ag = model.predict_score(home, away)
                if hg > ag:
                    points[home] += 3
                elif hg == ag:
                    points[home] += 1
                    points[away] += 1
                else:
                    points[away] += 3
                gd[home] += hg - ag
                gd[away] += ag - hg
            else:
                outcome = model.predict(home, away)
                if outcome == "home":
                    points[home] += 3
                elif outcome == "draw":
                    points[home] += 1
                    points[away] += 1
                else:
                    points[away] += 3

        # Rank: points first, then GD (if available), then random tiebreak
        if has_scores:
            ranked = sorted(teams, key=lambda t: (points[t], gd[t], random.random()), reverse=True)
        else:
            ranked = sorted(teams, key=lambda t: (points[t], random.random()), reverse=True)

        for pos, team in enumerate(ranked, 1):
            position_counts[team][pos] += 1
        for team in teams:
            points_dist[team][points[team]] += 1
            gd_dist[team][gd[team]] += 1

    # Compute points CI (95%) for each team
    pts_ci = {}
    for team in teams:
        dist = points_dist[team]
        pts_ci[team] = _value_ci(dist, iterations)

    gd_ci = {}
    if has_scores:
        for team in teams:
            dist = gd_dist[team]
            gd_ci[team] = _value_ci(dist, iterations)
    else:
        gd_ci = None

    return position_counts, pts_ci, gd_ci


def _value_ci(counts, iterations, ci=0.95):
    """Compute confidence interval from a {value: count} distribution.

    Returns (low, high) — the values at the 2.5th and 97.5th percentiles.
    """
    tail = (1.0 - ci) / 2.0
    low_target = tail * iterations
    high_target = (1.0 - tail) * iterations

    sorted_vals = sorted(counts.keys())
    cumulative = 0
    ci_low = sorted_vals[0]
    ci_high = sorted_vals[-1]
    found_low = False

    for val in sorted_vals:
        cumulative += counts[val]
        if cumulative >= low_target and not found_low:
            ci_low = val
            found_low = True
        if cumulative >= high_target:
            ci_high = val
            break

    return ci_low, ci_high


def _position_ci(counts, iterations, num_teams, ci=0.95):
    """Compute confidence interval positions from a position count distribution.

    Returns (low_pos, high_pos) — the positions at the lower and upper
    percentile boundaries. E.g., for 95% CI: 2.5th and 97.5th percentiles.
    """
    tail = (1.0 - ci) / 2.0
    low_target = tail * iterations
    high_target = (1.0 - tail) * iterations

    cumulative = 0
    ci_low = None
    ci_high = num_teams

    for pos in range(1, num_teams + 1):
        cumulative += counts.get(pos, 0)
        if cumulative >= low_target and ci_low is None:
            ci_low = pos
        if cumulative >= high_target:
            ci_high = pos
            break

    return ci_low or 1, ci_high


def aggregate_results(position_counts, iterations, pts_ci=None, gd_ci=None,
                      top_n=4, bottom_n=3):
    """Aggregate simulation results into summary statistics per team."""
    teams = sorted(position_counts.keys())
    num_teams = len(teams)
    results = []

    for team in teams:
        counts = position_counts[team]
        avg_pos = sum(pos * count for pos, count in counts.items()) / iterations
        top_pct = sum(counts[p] for p in range(1, top_n + 1)) / iterations * 100
        bottom_pct = sum(counts[p] for p in range(num_teams - bottom_n + 1, num_teams + 1)) / iterations * 100
        first_pct = counts[1] / iterations * 100
        last_pct = counts[num_teams] / iterations * 100

        # 95% confidence interval (2.5th to 97.5th percentile)
        ci_low, ci_high = _position_ci(counts, iterations, num_teams)

        entry = {
            "team": team,
            "avg_pos": avg_pos,
            "ci_low": ci_low,
            "ci_high": ci_high,
            "first_pct": first_pct,
            "top_pct": top_pct,
            "bottom_pct": bottom_pct,
            "last_pct": last_pct,
            "position_dist": dict(counts),
            "pts_ci": pts_ci[team] if pts_ci else None,
            "gd_ci": gd_ci[team] if gd_ci else None,
        }
        results.append(entry)

    results.sort(key=lambda r: r["avg_pos"])
    return results


def team_detail(position_counts, team, iterations):
    """Return full position distribution for a single team."""
    counts = position_counts[team]
    num_teams = len(position_counts)
    dist = []
    for pos in range(1, num_teams + 1):
        count = counts.get(pos, 0)
        pct = count / iterations * 100
        dist.append((pos, pct))
    return dist
