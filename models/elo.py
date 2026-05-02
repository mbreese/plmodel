import random

from .base import MatchModel
from .helpers import compute_elo, elo_expected


class EloModel(MatchModel):
    """Pure Elo model: maps rating difference to win/draw/loss probabilities.

    Draws are carved out from the expected score using a draw width parameter.
    A match is a draw if the expected score falls within the draw band, calibrated
    from the observed draw rate in the completed matches.
    """

    def __init__(self, k=20, home_elo_advantage=50):
        self.k = k
        self.home_elo_advantage = home_elo_advantage

    def setup(self, standings, completed):
        self.elo, self.home_elo_advantage = compute_elo(
            completed, k=self.k, home_elo_advantage=self.home_elo_advantage
        )

        # Calibrate draw width from observed draw rate
        total = len(completed)
        draw_rate = sum(1 for m in completed if m["home_goals"] == m["away_goals"]) / total
        self.draw_width = draw_rate

    def _match_probs(self, home, away):
        """Compute P(home), P(draw), P(away) from Elo ratings."""
        rating_diff = self.elo[home] + self.home_elo_advantage - self.elo[away]
        exp_home = elo_expected(rating_diff)

        # Allocate draws proportionally: stronger favorite = fewer draws
        # Use a simple model: P(draw) = draw_width * (1 - abs(exp_home - 0.5)*2)
        # This means evenly matched teams draw more often
        p_draw = self.draw_width * (1.0 - abs(exp_home - 0.5) * 2)
        p_draw = max(0.05, min(p_draw, 0.40))  # clamp to reasonable range

        remaining = 1.0 - p_draw
        p_home = remaining * exp_home
        p_away = remaining * (1.0 - exp_home)

        return p_home, p_draw, p_away

    def predict(self, home, away):
        p_home, p_draw, _ = self._match_probs(home, away)

        r = random.random()
        if r < p_home:
            return "home"
        elif r < p_home + p_draw:
            return "draw"
        else:
            return "away"

    def predict_match_detail(self, home, away):
        p_home, p_draw, p_away = self._match_probs(home, away)
        return {
            "p_home": round(p_home, 4),
            "p_draw": round(p_draw, 4),
            "p_away": round(p_away, 4),
            "home_elo": round(self.elo[home], 0),
            "away_elo": round(self.elo[away], 0),
        }

    def team_columns(self, team):
        return [
            ("Elo", f"{self.elo[team]:.0f}"),
        ]

    def __str__(self):
        return (f"EloModel (K={self.k}, home adv: {self.home_elo_advantage} Elo pts, "
                f"draw rate: {self.draw_width:.1%})")
