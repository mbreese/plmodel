from .base import MatchModel
from .helpers import compute_strengths, negbin_sample, estimate_overdispersion


class NegBinModel(MatchModel):
    """Negative binomial model using per-team home/away attack/defense strength.

    Similar to the Poisson model but uses a negative binomial distribution
    to account for overdispersion in goal scoring. Football goals tend to
    have higher variance than Poisson predicts (more blowouts and 0-0s).

    The overdispersion parameter alpha is estimated from the season's data.
    When alpha=0, this is equivalent to the Poisson model.

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

        self.alpha = estimate_overdispersion(completed)

    def _expected_goals(self, home, away):
        home_xg = self.home_attack[home] * self.away_defense[away] * self.league_avg_home
        away_xg = self.away_attack[away] * self.home_defense[home] * self.league_avg_away
        return home_xg, away_xg

    def predict_score(self, home, away):
        home_xg, away_xg = self._expected_goals(home, away)
        return negbin_sample(home_xg, self.alpha), negbin_sample(away_xg, self.alpha)

    def predict(self, home, away):
        hg, ag = self.predict_score(home, away)
        if hg > ag:
            return "home"
        elif hg == ag:
            return "draw"
        else:
            return "away"

    def predict_match_detail(self, home, away):
        # When alpha=0, same as Poisson
        from .poisson import _poisson_match_detail
        home_xg, away_xg = self._expected_goals(home, away)
        detail = _poisson_match_detail(
            home, away, home_xg, away_xg,
            self.home_attack, self.home_defense,
            self.away_attack, self.away_defense,
        )
        detail["alpha"] = round(self.alpha, 4)
        return detail

    def team_columns(self, team):
        atk = (self.home_attack[team] + self.away_attack[team]) / 2
        def_ = (self.home_defense[team] + self.away_defense[team]) / 2
        return [
            ("Atk", f"{atk:.2f}"),
            ("Def", f"{def_:.2f}"),
        ]

    def __str__(self):
        hl = f", half-life: {self.half_life}" if self.half_life else ""
        return (f"NegBinModel (home avg: {self.league_avg_home:.2f}, "
                f"away avg: {self.league_avg_away:.2f}, "
                f"alpha: {self.alpha:.3f}{hl})")
