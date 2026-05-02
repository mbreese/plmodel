from .base import MatchModel
from .helpers import compute_elo, elo_expected, poisson_sample, poisson_pmf


class EloPoissonModel(MatchModel):
    """Elo-Poisson hybrid: uses Elo ratings to derive expected goals,
    then samples scorelines from Poisson distributions.

    The rating difference is mapped to expected goals using the league's
    home/away goal averages, scaled by the Elo expected score.

    home_xG = (league_avg_home + league_avg_away) * elo_expected(rating_diff)
    away_xG = (league_avg_home + league_avg_away) * (1 - elo_expected(rating_diff))

    This gives scorelines and goal differences while benefiting from
    Elo's implicit time-weighting and strength ordering.
    """

    def __init__(self, k=20, home_elo_advantage=50):
        self.k = k
        self.home_elo_advantage = home_elo_advantage

    def setup(self, standings, completed):
        self.elo, self.home_elo_advantage = compute_elo(
            completed, k=self.k, home_elo_advantage=self.home_elo_advantage
        )

        total_home = sum(m["home_goals"] for m in completed)
        total_away = sum(m["away_goals"] for m in completed)
        n = len(completed)
        self.league_avg_home = total_home / n
        self.league_avg_away = total_away / n

    def predict_score(self, home, away):
        rating_diff = self.elo[home] + self.home_elo_advantage - self.elo[away]
        exp_home = elo_expected(rating_diff)

        total_goals = self.league_avg_home + self.league_avg_away
        home_xg = total_goals * exp_home
        away_xg = total_goals * (1.0 - exp_home)

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
        rating_diff = self.elo[home] + self.home_elo_advantage - self.elo[away]
        exp_home = elo_expected(rating_diff)
        total_goals = self.league_avg_home + self.league_avg_away
        home_xg = total_goals * exp_home
        away_xg = total_goals * (1.0 - exp_home)

        from .poisson import _goals_ci, MAX_GOALS

        p_home = 0.0
        p_draw = 0.0
        p_away = 0.0
        best_score = (0, 0)
        best_prob = 0.0
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

        total = p_home + p_draw + p_away
        return {
            "p_home": round(p_home / total, 4),
            "p_draw": round(p_draw / total, 4),
            "p_away": round(p_away / total, 4),
            "home_xg": round(home_xg, 2),
            "away_xg": round(away_xg, 2),
            "mode_score": list(best_score),
            "home_goals_ci": list(_goals_ci(home_goal_probs)),
            "away_goals_ci": list(_goals_ci(away_goal_probs)),
            "home_elo": round(self.elo[home], 0),
            "away_elo": round(self.elo[away], 0),
        }

    def team_columns(self, team):
        return [
            ("Elo", f"{self.elo[team]:.0f}"),
        ]

    def __str__(self):
        return (f"EloPoissonModel (K={self.k}, MoV-scaled, "
                f"home adv: {self.home_elo_advantage} Elo pts, "
                f"home avg: {self.league_avg_home:.2f}, away avg: {self.league_avg_away:.2f})")
