from abc import ABC, abstractmethod


class MatchModel(ABC):
    """Base class for match outcome prediction models.

    Subclasses implement predict() to return the outcome of a single match.
    The model receives the full current standings at initialization time so
    team-specific models can use that context.
    """

    def setup(self, standings, completed):
        """Called once before simulation begins. Override to precompute per-team stats."""
        pass

    @abstractmethod
    def predict(self, home, away):
        """Predict the outcome of a match.

        Returns one of: "home", "draw", "away"
        """
        pass

    def predict_score(self, home, away):
        """Predict actual scoreline as (home_goals, away_goals).

        Override in models that generate scorelines (Poisson-based).
        Returns None by default, meaning no scoreline is available.
        """
        return None

    def team_columns(self, team):
        """Return a list of (header, value) pairs for extra per-team columns.

        Override in subclasses to add model-specific columns to the output table.
        """
        return []

    def predict_match_detail(self, home, away):
        """Return detailed prediction info for a specific match.

        Override in subclasses. Returns a dict with model-specific data:
        - p_home, p_draw, p_away: outcome probabilities
        - home_xg, away_xg: expected goals (if applicable)
        - mode_score: most likely scoreline [h, a] (if applicable)
        - home_goals_ci, away_goals_ci: 95% CI for goals [lo, hi] (if applicable)
        - team strengths (model-specific)
        """
        return None
