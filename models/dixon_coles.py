import math
import random

from .base import MatchModel
from .helpers import compute_strengths, poisson_pmf


def _dc_tau(hg, ag, home_xg, away_xg, rho):
    """Dixon-Coles correction factor for low-scoring outcomes."""
    if hg == 0 and ag == 0:
        return 1.0 - rho * home_xg * away_xg
    elif hg == 1 and ag == 0:
        return 1.0 + rho * away_xg
    elif hg == 0 and ag == 1:
        return 1.0 + rho * home_xg
    elif hg == 1 and ag == 1:
        return 1.0 - rho
    else:
        return 1.0


class DixonColesModel(MatchModel):
    """Dixon-Coles model: Poisson with low-score correlation adjustment.

    Uses home/away attack/defense split. Applies a correction factor (tau)
    to scorelines 0-0, 1-0, 0-1, and 1-1, controlled by parameter rho.
    Rho is estimated from the season's completed results via grid search
    over log-likelihood (unweighted, since rho is a structural property).

    If half_life is set, recent matches are weighted more heavily using
    exponential decay (half_life in number of matches).
    """

    MAX_GOALS = 10  # max goals per team when computing outcome probabilities

    def __init__(self, half_life=None):
        self.half_life = half_life

    def setup(self, standings, completed):
        (self.league_avg_home, self.league_avg_away,
         self.home_attack, self.home_defense,
         self.away_attack, self.away_defense) = compute_strengths(
            standings, completed, self.half_life
        )

        # Estimate rho from completed matches via grid search
        self.rho = self._estimate_rho(completed)

    def _expected_goals(self, home, away):
        home_xg = self.home_attack[home] * self.away_defense[away] * self.league_avg_home
        away_xg = self.away_attack[away] * self.home_defense[home] * self.league_avg_away
        return home_xg, away_xg

    def _estimate_rho(self, completed):
        """Estimate rho using unweighted log-likelihood across all matches.

        Rho captures a structural property of football scoring (low-score
        correlation), not team-specific form, so all matches are weighted
        equally regardless of the half-life setting.
        """
        best_rho = 0.0
        best_ll = float("-inf")

        for rho_candidate in [i * 0.01 for i in range(-30, 1)]:  # constrain rho <= 0
            ll = 0.0
            for m in completed:
                home_xg, away_xg = self._expected_goals(m["home"], m["away"])
                hg, ag = m["home_goals"], m["away_goals"]

                p = poisson_pmf(hg, home_xg) * poisson_pmf(ag, away_xg)
                tau = _dc_tau(hg, ag, home_xg, away_xg, rho_candidate)
                p = max(p * tau, 1e-15)

                ll += math.log(p)
            if ll > best_ll:
                best_ll = ll
                best_rho = rho_candidate

        return best_rho

    def predict_score(self, home, away):
        home_xg, away_xg = self._expected_goals(home, away)

        # Sample from the DC-adjusted scoreline distribution
        probs = []
        for hg in range(self.MAX_GOALS + 1):
            for ag in range(self.MAX_GOALS + 1):
                p = (poisson_pmf(hg, home_xg) * poisson_pmf(ag, away_xg)
                     * _dc_tau(hg, ag, home_xg, away_xg, self.rho))
                probs.append((hg, ag, p))

        # Normalize and sample
        total = sum(p for _, _, p in probs)
        r = random.random() * total
        cumulative = 0.0
        for hg, ag, p in probs:
            cumulative += p
            if r <= cumulative:
                return hg, ag
        return probs[-1][0], probs[-1][1]

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

        p_home = 0.0
        p_draw = 0.0
        p_away = 0.0
        best_score = (0, 0)
        best_prob = 0.0

        home_goal_probs = [0.0] * (self.MAX_GOALS + 1)
        away_goal_probs = [0.0] * (self.MAX_GOALS + 1)

        for hg in range(self.MAX_GOALS + 1):
            for ag in range(self.MAX_GOALS + 1):
                p = (poisson_pmf(hg, home_xg) * poisson_pmf(ag, away_xg)
                     * _dc_tau(hg, ag, home_xg, away_xg, self.rho))
                if hg > ag:
                    p_home += p
                elif hg == ag:
                    p_draw += p
                else:
                    p_away += p
                if p > best_prob:
                    best_prob = p
                    best_score = (hg, ag)
                home_goal_probs[hg] += p
                away_goal_probs[ag] += p

        total = p_home + p_draw + p_away
        # Normalize goal distributions
        h_total = sum(home_goal_probs)
        a_total = sum(away_goal_probs)
        home_goal_probs = [p / h_total for p in home_goal_probs]
        away_goal_probs = [p / a_total for p in away_goal_probs]

        from .poisson import _goals_ci
        home_goals_ci = _goals_ci(home_goal_probs)
        away_goals_ci = _goals_ci(away_goal_probs)

        return {
            "p_home": round(p_home / total, 4),
            "p_draw": round(p_draw / total, 4),
            "p_away": round(p_away / total, 4),
            "home_xg": round(home_xg, 2),
            "away_xg": round(away_xg, 2),
            "mode_score": list(best_score),
            "home_goals_ci": list(home_goals_ci),
            "away_goals_ci": list(away_goals_ci),
            "home_attack": round((self.home_attack[home] + self.away_attack[home]) / 2, 2),
            "home_defense": round((self.home_defense[home] + self.away_defense[home]) / 2, 2),
            "away_attack": round((self.home_attack[away] + self.away_attack[away]) / 2, 2),
            "away_defense": round((self.home_defense[away] + self.away_defense[away]) / 2, 2),
            "rho": self.rho,
        }

    def team_columns(self, team):
        atk = (self.home_attack[team] + self.away_attack[team]) / 2
        def_ = (self.home_defense[team] + self.away_defense[team]) / 2
        return [
            ("Atk", f"{atk:.2f}"),
            ("Def", f"{def_:.2f}"),
        ]

    def __str__(self):
        hl = f", half-life: {self.half_life}" if self.half_life else ""
        return (f"DixonColesModel (home avg: {self.league_avg_home:.2f}, "
                f"away avg: {self.league_avg_away:.2f}, "
                f"rho: {self.rho:.3f}{hl})")
