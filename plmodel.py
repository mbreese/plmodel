#!/usr/bin/env python3
"""Monte Carlo simulator for predicting soccer league final standings."""

import argparse
import os
import sys

from models import MODELS
from simulate import (
    load_fixtures,
    load_deductions,
    build_standings,
    compute_best_worst,
    simulate_season,
    aggregate_results,
    team_detail,
)
from report import generate_report, generate_report_from_data
from predictions import save_predictions, load_predictions


def print_standings(standings):
    """Print current league table."""
    sorted_teams = sorted(
        standings.items(),
        key=lambda x: (x[1]["points"], x[1]["gd"], x[1]["gf"]),
        reverse=True,
    )
    print("\nCurrent Standings:")
    print(f"{'Pos':>3}  {'Team':<25} {'P':>3} {'W':>3} {'D':>3} {'L':>3} {'GF':>4} {'GA':>4} {'GD':>4} {'Pts':>4}")
    print("-" * 62)
    for i, (team, s) in enumerate(sorted_teams, 1):
        gd = s["gd"]
        gd_str = f"+{gd}" if gd > 0 else str(gd)
        ded = s.get("deduction", 0)
        ded_str = f" (-{ded})" if ded else ""
        print(f"{i:>3}  {team:<25} {s['played']:>3} {s['wins']:>3} {s['draws']:>3} {s['losses']:>3} {s['gf']:>4} {s['ga']:>4} {gd_str:>4} {s['points']:>4}{ded_str}")


def print_summary(results, top_n, bottom_n, model=None):
    """Print simulation summary table."""
    # Check if model provides extra columns
    extra_headers = []
    if model and results:
        extra_headers = [h for h, _ in model.team_columns(results[0]["team"])]

    has_gd = results and results[0]["gd_ci"] is not None

    header = f"\n{'Team':<25} {'Avg':>5} {'95% CI':>8}"
    if has_gd:
        header += f" {'Pts CI':>9} {'GD CI':>9}"
    header += f" {'1st':>6} {'Top '+str(top_n):>6} {'Bot '+str(bottom_n):>6} {'Last':>6}"
    for h in extra_headers:
        header += f" {h:>6}"
    print(header)
    print("-" * len(header.strip()))

    for r in results:
        ci = f"{r['ci_low']}-{r['ci_high']}"
        line = f"{r['team']:<25} {r['avg_pos']:>5.1f} {ci:>8}"
        if has_gd:
            pts_lo, pts_hi = r['pts_ci']
            gd_lo, gd_hi = r['gd_ci']
            gd_lo_s = f"+{gd_lo}" if gd_lo > 0 else str(gd_lo)
            gd_hi_s = f"+{gd_hi}" if gd_hi > 0 else str(gd_hi)
            line += f" {pts_lo}–{pts_hi:>3} {gd_lo_s}–{gd_hi_s}"
        line += (
            f" {r['first_pct']:>5.1f}% {r['top_pct']:>5.1f}% "
            f"{r['bottom_pct']:>5.1f}% {r['last_pct']:>5.1f}%"
        )
        if model:
            for _, val in model.team_columns(r["team"]):
                line += f" {val:>6}"
        print(line)


def print_team_detail(dist, team):
    """Print full position distribution for a team."""
    print(f"\nPosition distribution for {team}:")
    print(f"{'Pos':>4} {'Prob':>8}  {'':40}")
    print("-" * 55)
    for pos, pct in dist:
        bar = "#" * int(pct)
        print(f"{pos:>4} {pct:>7.2f}%  {bar}")


def _build_model(name, half_life):
    """Instantiate a model by name, passing half_life where supported."""
    model_cls = MODELS[name]
    if name in ("poisson", "dixoncoles", "negbin"):
        return model_cls(half_life=half_life)
    else:
        return model_cls()


def run_all_models(standings, remaining, completed, iterations, top_n, bottom_n, half_life):
    """Run all models and return a list of result dicts."""
    all_results = []
    for name in MODELS:
        model = _build_model(name, half_life)
        print(f"  Running {name}...")
        position_counts, pts_ci, gd_ci = simulate_season(
            standings, remaining, completed=completed, model=model, iterations=iterations
        )
        results = aggregate_results(
            position_counts, iterations, pts_ci=pts_ci, gd_ci=gd_ci,
            top_n=top_n, bottom_n=bottom_n,
        )
        all_results.append({
            "name": name,
            "model_str": str(model),
            "results": results,
            "model": model,
        })
    return all_results


def main():
    parser = argparse.ArgumentParser(description="Monte Carlo league simulator")
    parser.add_argument("--fixtures", default=None, help="Path to fixtures CSV")
    parser.add_argument("--iterations", type=int, default=10000, help="Number of simulations (default: 10000)")
    parser.add_argument("--top", type=int, default=4, help="Top N positions to highlight (default: 4)")
    parser.add_argument("--bottom", type=int, default=3, help="Bottom N positions to highlight (default: 3)")
    parser.add_argument("--team", type=str, help="Show detailed position distribution for a team")
    parser.add_argument(
        "--model", type=str, default="global", choices=list(MODELS.keys()),
        help=f"Prediction model: {', '.join(MODELS.keys())}"
    )
    parser.add_argument(
        "--half-life", type=int, default=None,
        help="Half-life in matches for exponential decay weighting (poisson/dixoncoles only). "
             "E.g., 10 means a match 10 games ago counts half as much as the most recent."
    )
    parser.add_argument(
        "--html", type=str, default=None,
        help="Path for HTML report output (required for report generation)"
    )
    parser.add_argument(
        "--report", type=str, default=None,
        help="Generate HTML report from a saved predictions JSON file (no simulation needed)"
    )
    args = parser.parse_args()

    # Report-only mode: regenerate HTML from saved predictions
    if args.report is not None:
        if not args.html:
            parser.error("--html is required with --report")
        data = load_predictions(args.report)
        generate_report_from_data(data, output_path=args.html)
        print(f"Report written to {args.html}")
        return

    # All other modes require --fixtures
    if not args.fixtures:
        parser.error("--fixtures is required")

    # Derive predictions path from fixtures name
    fixtures_base = os.path.splitext(os.path.basename(args.fixtures))[0]
    predictions_path = f"data/{fixtures_base}-predictions.json"

    completed, remaining = load_fixtures(args.fixtures)
    deductions = load_deductions(args.fixtures)
    standings = build_standings(completed, deductions=deductions)

    if deductions:
        print(f"\nPoint deductions applied:")
        for team, pts in deductions.items():
            print(f"  {team}: -{pts} pts")

    print_standings(standings)

    best_worst = compute_best_worst(standings, remaining)

    # HTML report mode: run all models
    if args.html is not None:
        print(f"\nCompleted: {len(completed)} matches | Remaining: {len(remaining)} matches")
        print(f"Running {args.iterations:,} simulations per model...")

        all_results = run_all_models(
            standings, remaining, completed, args.iterations, args.top, args.bottom, args.half_life
        )

        save_predictions(
            predictions_path, all_results, standings,
            completed=completed,
            remaining=remaining,
            iterations=args.iterations,
            top_n=args.top,
            bottom_n=args.bottom,
            best_worst=best_worst,
        )
        print(f"Predictions saved to {predictions_path}")

        generate_report(
            all_results, standings,
            completed=completed,
            remaining=remaining,
            completed_count=len(completed),
            remaining_count=len(remaining),
            iterations=args.iterations,
            top_n=args.top,
            bottom_n=args.bottom,
            best_worst=best_worst,
            output_path=args.html,
        )
        print(f"Report written to {args.html}")
        return

    # Single model mode
    model = _build_model(args.model, args.half_life)

    print(f"\nCompleted: {len(completed)} matches | Remaining: {len(remaining)} matches")
    print(f"Running {args.iterations:,} simulations...")

    position_counts, pts_ci, gd_ci = simulate_season(standings, remaining, completed=completed, model=model, iterations=args.iterations)
    print(f"Model: {model}")
    results = aggregate_results(position_counts, args.iterations, pts_ci=pts_ci, gd_ci=gd_ci, top_n=args.top, bottom_n=args.bottom)

    print_summary(results, args.top, args.bottom, model=model)

    if args.team:
        team = args.team
        if team not in position_counts:
            # Try case-insensitive match
            matches = [t for t in position_counts if t.lower() == team.lower()]
            if matches:
                team = matches[0]
            else:
                print(f"\nTeam '{args.team}' not found. Available teams:")
                for t in sorted(position_counts.keys()):
                    print(f"  {t}")
                sys.exit(1)
        dist = team_detail(position_counts, team, args.iterations)
        print_team_detail(dist, team)


if __name__ == "__main__":
    main()
