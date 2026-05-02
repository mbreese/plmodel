"""Shared helper functions used by multiple models."""

import math
import random
from collections import defaultdict


def poisson_sample(lam):
    """Sample from a Poisson distribution using inverse transform."""
    L = math.exp(-lam)
    k = 0
    p = 1.0
    while True:
        k += 1
        p *= random.random()
        if p < L:
            return k - 1


def negbin_sample(mean, alpha):
    """Sample from a negative binomial distribution.

    Parameterized by mean and overdispersion alpha.
    When alpha -> 0, this converges to Poisson.
    Uses a gamma-Poisson mixture: draw rate from Gamma, then goals from Poisson.
    """
    if alpha <= 0 or mean <= 0:
        return poisson_sample(max(mean, 0.01))

    # Gamma shape and scale from mean and alpha
    # Var = mean + alpha * mean^2, so shape = 1/alpha, scale = mean * alpha
    shape = 1.0 / alpha
    scale = mean * alpha

    # Sample rate from gamma distribution using Marsaglia and Tsang's method
    rate = _gamma_sample(shape, scale)
    return poisson_sample(rate)


def _gamma_sample(shape, scale):
    """Sample from a Gamma distribution. Uses rejection method for shape >= 1,
    and Ahrens-Dieter method for shape < 1."""
    if shape < 1:
        # Boost: Gamma(shape) = Gamma(shape+1) * U^(1/shape)
        return _gamma_sample(shape + 1, scale) * (random.random() ** (1.0 / shape))

    # Marsaglia and Tsang's method for shape >= 1
    d = shape - 1.0 / 3.0
    c = 1.0 / math.sqrt(9.0 * d)
    while True:
        while True:
            x = random.gauss(0, 1)
            v = (1.0 + c * x) ** 3
            if v > 0:
                break
        u = random.random()
        if u < 1.0 - 0.0331 * (x * x) * (x * x):
            return d * v * scale
        if math.log(u) < 0.5 * x * x + d * (1.0 - v + math.log(v)):
            return d * v * scale


def poisson_pmf(k, lam):
    """Probability mass function for Poisson distribution."""
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def compute_strengths(standings, completed, half_life=None, blend=0.7):
    """Compute per-team home/away attack and defense strengths.

    Computes separate home and away strengths for each team, relative to
    league averages. Home advantage is captured implicitly through the
    league-wide home/away goal averages.

    If half_life is set, matches are weighted by exponential decay:
      weight = exp(-ln(2) * age / half_life)

    When using decay, strengths are blended with unweighted season values
    to prevent extreme estimates from short-term streaks:
      strength = blend * weighted + (1 - blend) * season

    Returns (league_avg_home, league_avg_away, home_attack, home_defense,
             away_attack, away_defense) where each dict maps team -> float.
    """
    n = len(completed)

    # Assign weights: most recent match is index n-1, oldest is index 0
    if half_life and half_life > 0:
        decay = math.log(2) / half_life
        weights = [math.exp(-decay * (n - 1 - i)) for i in range(n)]
    else:
        weights = [1.0] * n

    total_weight = sum(weights)
    league_avg_home = sum(w * m["home_goals"] for w, m in zip(weights, completed)) / total_weight
    league_avg_away = sum(w * m["away_goals"] for w, m in zip(weights, completed)) / total_weight

    # Per-team weighted home/away goals for/against
    h_gf = defaultdict(float)  # goals scored at home
    h_ga = defaultdict(float)  # goals conceded at home
    h_w = defaultdict(float)   # weight of home matches
    a_gf = defaultdict(float)  # goals scored away
    a_ga = defaultdict(float)  # goals conceded away
    a_w = defaultdict(float)   # weight of away matches

    for w, m in zip(weights, completed):
        h_gf[m["home"]] += w * m["home_goals"]
        h_ga[m["home"]] += w * m["away_goals"]
        h_w[m["home"]] += w

        a_gf[m["away"]] += w * m["away_goals"]
        a_ga[m["away"]] += w * m["home_goals"]
        a_w[m["away"]] += w

    home_attack = {}
    home_defense = {}
    away_attack = {}
    away_defense = {}

    for team in standings:
        # Home strengths (relative to league home/away averages)
        if h_w[team] > 0:
            home_attack[team] = (h_gf[team] / h_w[team]) / league_avg_home
            home_defense[team] = (h_ga[team] / h_w[team]) / league_avg_away
        else:
            home_attack[team] = 1.0
            home_defense[team] = 1.0

        # Away strengths
        if a_w[team] > 0:
            away_attack[team] = (a_gf[team] / a_w[team]) / league_avg_away
            away_defense[team] = (a_ga[team] / a_w[team]) / league_avg_home
        else:
            away_attack[team] = 1.0
            away_defense[team] = 1.0

    # When using decay, blend with unweighted season values
    if half_life and half_life > 0:
        season_avg_home = sum(m["home_goals"] for m in completed) / n
        season_avg_away = sum(m["away_goals"] for m in completed) / n

        for team in standings:
            home_matches = [m for m in completed if m["home"] == team]
            away_matches = [m for m in completed if m["away"] == team]

            if home_matches:
                nh = len(home_matches)
                s_h_gf = sum(m["home_goals"] for m in home_matches) / nh
                s_h_ga = sum(m["away_goals"] for m in home_matches) / nh
                s_home_atk = s_h_gf / season_avg_home
                s_home_def = s_h_ga / season_avg_away
                home_attack[team] = blend * home_attack[team] + (1 - blend) * s_home_atk
                home_defense[team] = blend * home_defense[team] + (1 - blend) * s_home_def

            if away_matches:
                na = len(away_matches)
                s_a_gf = sum(m["away_goals"] for m in away_matches) / na
                s_a_ga = sum(m["home_goals"] for m in away_matches) / na
                s_away_atk = s_a_gf / season_avg_away
                s_away_def = s_a_ga / season_avg_home
                away_attack[team] = blend * away_attack[team] + (1 - blend) * s_away_atk
                away_defense[team] = blend * away_defense[team] + (1 - blend) * s_away_def

    return league_avg_home, league_avg_away, home_attack, home_defense, away_attack, away_defense


def compute_elo(completed, k=20, home_elo_advantage=50, initial_elo=1500):
    """Compute Elo ratings by replaying completed matches in order.

    Uses margin-of-victory scaling: the K-factor is multiplied by
    ln(1 + goal_difference) so larger wins produce bigger rating changes.

    Args:
        completed: List of completed match dicts (in chronological order)
        k: Base K-factor
        home_elo_advantage: Elo points added to home team's expected score
        initial_elo: Starting Elo for all teams

    Returns (elo_dict, home_elo_advantage) where elo_dict maps team -> current Elo.
    """
    elo = defaultdict(lambda: initial_elo)

    for m in completed:
        home, away = m["home"], m["away"]
        home_r = elo[home] + home_elo_advantage
        away_r = elo[away]

        # Expected scores
        exp_home = 1.0 / (1.0 + 10 ** ((away_r - home_r) / 400))
        exp_away = 1.0 - exp_home

        # Actual scores (1 = win, 0.5 = draw, 0 = loss)
        if m["home_goals"] > m["away_goals"]:
            actual_home, actual_away = 1.0, 0.0
        elif m["home_goals"] == m["away_goals"]:
            actual_home, actual_away = 0.5, 0.5
        else:
            actual_home, actual_away = 0.0, 1.0

        # Margin-of-victory scaling
        goal_diff = abs(m["home_goals"] - m["away_goals"])
        mov_multiplier = math.log(1 + goal_diff) if goal_diff > 0 else 1.0

        # Update ratings
        elo[home] += k * mov_multiplier * (actual_home - exp_home)
        elo[away] += k * mov_multiplier * (actual_away - exp_away)

    return dict(elo), home_elo_advantage


def elo_expected(rating_diff):
    """Expected score given a rating difference (including home advantage)."""
    return 1.0 / (1.0 + 10 ** (-rating_diff / 400))


def estimate_overdispersion(completed):
    """Estimate the overdispersion parameter (alpha) for negative binomial.

    Compares the observed variance of goals to the mean. For Poisson,
    variance == mean. Alpha captures the excess: Var = mean + alpha * mean^2.
    Returns alpha (0 = Poisson, >0 = overdispersed).
    """
    all_goals = []
    for m in completed:
        all_goals.append(m["home_goals"])
        all_goals.append(m["away_goals"])

    mean = sum(all_goals) / len(all_goals)
    var = sum((g - mean) ** 2 for g in all_goals) / len(all_goals)

    # Var = mean + alpha * mean^2 => alpha = (var - mean) / mean^2
    if mean > 0:
        alpha = max((var - mean) / (mean ** 2), 0.0)
    else:
        alpha = 0.0

    return alpha
