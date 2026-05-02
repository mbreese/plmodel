import random

from .base import MatchModel


class SeasonRateModel(MatchModel):
    """Derives home/draw/away rates from this season's completed results."""

    def setup(self, standings, completed):
        total = len(completed)
        if total == 0:
            # Fall back to global rates if no completed matches
            self.home_win_rate = 0.46
            self.draw_rate = 0.25
            self.away_win_rate = 0.29
            self.home_threshold = 0.46
            self.draw_threshold = 0.71
            return

        home_wins = sum(1 for m in completed if m["home_goals"] > m["away_goals"])
        draws = sum(1 for m in completed if m["home_goals"] == m["away_goals"])

        self.home_win_rate = home_wins / total
        self.draw_rate = draws / total
        self.away_win_rate = 1.0 - self.home_win_rate - self.draw_rate
        self.home_threshold = self.home_win_rate
        self.draw_threshold = self.home_threshold + self.draw_rate

    def __str__(self):
        return (f"SeasonRateModel (home: {self.home_win_rate:.1%}, "
                f"draw: {self.draw_rate:.1%}, "
                f"away: {self.away_win_rate:.1%})")

    def predict_match_detail(self, home, away):
        return {
            "p_home": round(self.home_win_rate, 4),
            "p_draw": round(self.draw_rate, 4),
            "p_away": round(self.away_win_rate, 4),
        }

    def predict(self, home, away):
        r = random.random()
        if r < self.home_threshold:
            return "home"
        elif r < self.draw_threshold:
            return "draw"
        else:
            return "away"
