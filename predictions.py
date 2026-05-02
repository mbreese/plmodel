"""Prediction data serialization — save/load simulation results as JSON."""

import json
import os


def save_predictions(filepath, all_results, standings, completed, remaining,
                     iterations, top_n, bottom_n, best_worst=None):
    """Save simulation results and metadata to a JSON file.

    Serializes everything the HTML report generator needs, including
    pre-computed team columns and per-match predictions from models.
    """
    data = {
        "iterations": iterations,
        "top_n": top_n,
        "bottom_n": bottom_n,
        "completed_count": len(completed),
        "remaining_count": len(remaining),
        "standings": standings,
        "completed": completed,
        "remaining": remaining,
        "best_worst": best_worst or {},
        "models": [],
    }

    for entry in all_results:
        model = entry["model"]
        results = entry["results"]

        # Pre-compute team_columns for each team
        team_columns = {}
        if model and results:
            for r in results:
                team = r["team"]
                team_columns[team] = model.team_columns(team)

        # Per-match predictions for remaining fixtures
        match_predictions = []
        if model:
            for m in remaining:
                detail = model.predict_match_detail(m["home"], m["away"])
                if detail:
                    detail["home"] = m["home"]
                    detail["away"] = m["away"]
                    match_predictions.append(detail)

        data["models"].append({
            "name": entry["name"],
            "model_str": entry["model_str"],
            "team_columns": team_columns,
            "results": results,
            "match_predictions": match_predictions,
        })

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


def load_predictions(filepath):
    """Load simulation results from a JSON file."""
    with open(filepath) as f:
        data = json.load(f)

    # Convert result tuples back from lists
    for model_entry in data["models"]:
        for r in model_entry["results"]:
            if r["pts_ci"]:
                r["pts_ci"] = tuple(r["pts_ci"])
            if r["gd_ci"]:
                r["gd_ci"] = tuple(r["gd_ci"])

    return data
