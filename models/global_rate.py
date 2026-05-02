import random

from .base import MatchModel


class GlobalRateModel(MatchModel):
    """Predicts match outcomes using league-wide historical base rates."""

    def __init__(self, home_win_rate=0.46, draw_rate=0.25, away_win_rate=0.29):
        self.home_win_rate = home_win_rate
        self.draw_rate = draw_rate
        self.away_win_rate = away_win_rate
        self.home_threshold = home_win_rate
        self.draw_threshold = home_win_rate + draw_rate

    def __str__(self):
        return (f"GlobalRateModel (home: {self.home_win_rate:.1%}, "
                f"draw: {self.draw_rate:.1%}, "
                f"away: {self.away_win_rate:.1%})")

    def predict_match_detail(self, home, away):
        return {
            "p_home": self.home_win_rate,
            "p_draw": self.draw_rate,
            "p_away": self.away_win_rate,
        }

    def predict(self, home, away):
        r = random.random()
        if r < self.home_threshold:
            return "home"
        elif r < self.draw_threshold:
            return "draw"
        else:
            return "away"
