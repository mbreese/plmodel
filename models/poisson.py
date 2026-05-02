import math

from .base import MatchModel
from .helpers import compute_strengths, poisson_sample, poisson_pmf

MAX_GOALS = 10


def _poisson_match_detail(home, away, home_xg, away_xg,
                          home_attack, home_defense, away_attack, away_defense):
    """Compute detailed match prediction from Poisson expected goals."""
    p_home = 0.0
    p_draw = 0.0
    p_away = 0.0
    best_score = (0, 0)
    best_prob = 0.0

    # Per-team goal distributions for CI
    home_goal_probs = [0.0] * (MAX_GOALS + 1)
    away_goal_probs = [0.0] * (MAX_GOALS + 1)

    for hg in range(MAX_GOALS + 1):
        hp = poisson_pmf(hg, home_xg)
        home_goal_probs[hg] = hp
        for ag in range(MAX_GOALS + 1):
            ap = poisson_pmf(ag, away_xg)
            p = hp * ap
            if hg > ag:
                p_home += p
            elif hg == ag:
                p_draw += p
            else:
                p_away += p
            if p > best_prob:
                best_prob = p
                best_score = (hg, ag)

    for ag in range(MAX_GOALS + 1):
        away_goal_probs[ag] = poisson_pmf(ag, away_xg)

    # 95% CI for each team's goals
    home_goals_ci = _goals_ci(home_goal_probs)
    away_goals_ci = _goals_ci(away_goal_probs)

    total = p_home + p_draw + p_away
    return {
        "p_home": round(p_home / total, 4),
        "p_draw": round(p_draw / total, 4),
        "p_away": round(p_away / total, 4),
        "home_xg": round(home_xg, 2),
        "away_xg": round(away_xg, 2),
        "mode_score": list(best_score),
        "home_goals_ci": list(home_goals_ci),
        "away_goals_ci": list(away_goals_ci),
        "home_attack": round((home_attack[home] + away_attack[home]) / 2, 2),
        "home_defense": round((home_defense[home] + away_defense[home]) / 2, 2),
        "away_attack": round((home_attack[away] + away_attack[away]) / 2, 2),
        "away_defense": round((home_defense[away] + away_defense[away]) / 2, 2),
    }


def _goals_ci(probs, ci=0.95):
    """Compute 95% CI from a goal probability distribution."""
    tail = (1.0 - ci) / 2.0
    cumulative = 0.0
    lo = 0
    hi = len(probs) - 1
    found_lo = False
    for g, p in enumerate(probs):
        cumulative += p
        if cumulative >= tail and not found_lo:
            lo = g
            found_lo = True
        if cumulative >= 1.0 - tail:
            hi = g
            break
    return lo, hi


class PoissonModel(MatchModel):
    """Poisson-based model using per-team home/away attack/defense strength.

    Computes separate home and away strengths for each team. Home advantage
    is captured implicitly through league-wide home/away goal averages.

    For a match, expected goals are:
      home_xG = home_attack[home] * away_defense[away] * league_avg_home
      away_xG = away_attack[away] * home_defense[home] * league_avg_away

    Actual goals are drawn from Poisson(xG) distributions.

    If half_life is set, recent matches are weighted more heavily using
    exponential decay (half_life in number of matches).
    """

    def __init__(self, half_life=None):
        self.half_life = half_life

    def setup(self, standings, completed):
        (self.league_avg_home, self.league_avg_away,
         self.home_attack, self.home_defense,
         self.away_attack, self.away_defense) = compute_strengths(
            standings, completed, self.half_life
        )

    def _expected_goals(self, home, away):
        home_xg = self.home_attack[home] * self.away_defense[away] * self.league_avg_home
        away_xg = self.away_attack[away] * self.home_defense[home] * self.league_avg_away
        return home_xg, away_xg

    def predict_score(self, home, away):
        home_xg, away_xg = self._expected_goals(home, away)
        return poisson_sample(home_xg), poisson_sample(away_xg)

    def predict(self, home, away):
        hg, ag = self.predict_score(home, away)
        if hg > ag:
            return "home"
        elif hg == ag:
            return "draw"
        else:
            return "away"

    def predict_match_detail(self, home, away):
        home_xg, away_xg = self._expected_goals(home, away)
        return _poisson_match_detail(
            home, away, home_xg, away_xg,
            self.home_attack, self.home_defense,
            self.away_attack, self.away_defense,
        )

    def team_columns(self, team):
        atk = (self.home_attack[team] + self.away_attack[team]) / 2
        def_ = (self.home_defense[team] + self.away_defense[team]) / 2
        return [
            ("Atk", f"{atk:.2f}"),
            ("Def", f"{def_:.2f}"),
        ]

    def __str__(self):
        hl = f", half-life: {self.half_life}" if self.half_life else ""
        return (f"PoissonModel (home avg: {self.league_avg_home:.2f}, "
                f"away avg: {self.league_avg_away:.2f}{hl})")
