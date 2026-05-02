# PLmodel — Monte Carlo League Simulator

A Monte Carlo simulation tool for predicting final league standings in soccer (football) leagues. Given a set of completed match results, it builds the current table, identifies remaining fixtures, and simulates the rest of the season thousands of times to estimate each team's probability of finishing in every position.

## Data Source

Match data can be fetched from the [football-data.org](https://www.football-data.org/) API using the included `fetch.py` script, or loaded from CSV files in the [football-data.co.uk](https://www.football-data.co.uk/englandm.php) format.

### football-data.org API

Register for a free API key at [football-data.org](https://www.football-data.org/client/register) and save it to `.api_key` in the project root.

```
# List available competitions
python fetch.py --list

# Fetch one or more leagues (respects 10 req/min rate limit)
python fetch.py PL ELC PD

# Fetch a specific season
python fetch.py PL --season 2024
```

Available competition codes include:
- **PL** — Premier League
- **ELC** — Championship
- **PD** — La Liga (Primera Division)
- **BL1** — Bundesliga
- **SA** — Serie A
- **FL1** — Ligue 1

Data is saved to `data/{code}.csv` with columns for date, time, matchday, teams, and scores. Scheduled (unplayed) matches are included with empty score columns.

### CSV Format

The tool auto-detects multiple CSV formats:
- football-data.org (via `fetch.py`): `Date`, `Time`, `Matchday`, `HomeTeam`, `AwayTeam`, `FTHG`, `FTAG`, `FTR`
- football-data.co.uk: `Div`, `Date`, `Time`, `HomeTeam`, `AwayTeam`, `FTHG`, `FTAG`, ...
- Simple format: `home`, `away`, `home_goals`, `away_goals`

Rows with scores are completed matches. Rows without scores are remaining fixtures. Any home/away pair not present in the file at all is also added as a remaining fixture.

### Point Deductions

Point deductions are supported via a companion CSV file named `{fixtures}-deductions.csv`. For example, for `data/ELC.csv`, the deductions file is `data/ELC-deductions.csv`:

```csv
team,points
Sheffield Weds,18
Leicester,6
```

Deductions are automatically applied when building the standings table. If no deductions file exists, none are applied.

## Usage

### Makefile

The simplest way to run everything:

```
make                          # fetch latest data + run all simulations
make fetch                    # fetch latest data only
make reports                  # run all simulations (no fetch)
make PL                       # run just Premier League
make html-only                # regenerate HTML from saved predictions (instant)
make clean                    # remove predictions and HTML

make ITERATIONS=10000         # override iteration count (default: 100000)
make HALF_LIFE=19             # override half-life (default: 10)
```

### CLI

```
# Single model, console output
python plmodel.py --fixtures data/PL.csv --model poisson --iterations 10000

# HTML report with all models (also saves predictions JSON)
python plmodel.py --fixtures data/PL.csv --html html/PL-predictions.html --iterations 100000

# With exponential decay weighting
python plmodel.py --fixtures data/PL.csv --html html/PL-predictions.html --half-life 10

# Championship with custom cutoffs
python plmodel.py --fixtures data/ELC.csv --html html/ELC-predictions.html --top 6 --bottom 3

# Regenerate HTML from saved predictions (no simulation needed)
python plmodel.py --report predictions/PL.json --html html/PL-predictions.html

# Detailed position distribution for one team
python plmodel.py --fixtures data/PL.csv --model dixoncoles --team Arsenal
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--fixtures` | (required) | Path to fixtures CSV |
| `--model` | `global` | Prediction model (see below) |
| `--iterations` | `10000` | Number of Monte Carlo simulations |
| `--top` | `4` | Top N positions to highlight (e.g., Champions League) |
| `--bottom` | `3` | Bottom N positions to highlight (e.g., relegation) |
| `--half-life` | None | Exponential decay half-life in matches (poisson/dixoncoles/negbin) |
| `--team` | None | Show full position distribution for a specific team |
| `--html` | None | Path for HTML report output (runs all models, saves predictions JSON) |
| `--report` | None | Regenerate HTML from a saved predictions JSON (no simulation) |

## Output

### Summary Table

For each team, the simulator reports:

- **Avg Pos** — mean finishing position across all simulations
- **95% CI** — the range of positions covering 95% of simulations (2.5th to 97.5th percentile)
- **Pts CI** — 95% confidence interval for final points (score-producing models only)
- **GD CI** — 95% confidence interval for final goal difference (score-producing models only)
- **1st** — probability of winning the league
- **Top N** — probability of finishing in the top N (default: top 4)
- **Bot N** — probability of finishing in the bottom N (default: bottom 3)
- **Last** — probability of finishing last

Models that compute per-team parameters also show extra columns (attack/defense strength, Elo rating).

The current standings table includes full tiebreaker information: points, goal difference (GD), and goals for (GF), sorted by points → GD → GF.

### Team Detail View

In the HTML report, clicking on any team name opens a detail view showing:

- **Completed matches**: matchday, date, opponent (H/A), score, result (W/D/L)
- **Upcoming matches**: matchday, date, opponent, plus per-model predictions:
  - Win/draw/loss probability bar and percentages
  - Most likely scoreline (score-producing models)
  - Expected goals (xG) for each team
  - 95% CI for each team's goals
  - Elo ratings (Elo-based models)
  - Attack/defense strengths (Poisson-based models)

### Predictions JSON

When generating an HTML report, predictions are also saved to `predictions/{league}.json`. This allows regenerating the HTML report instantly with `--report` without re-running simulations. The JSON contains all simulation results, standings, fixture data, and per-match predictions from each model.

## Models

### `global` — Global Rate Model

The simplest model. Uses fixed league-wide historical base rates for all matches regardless of which teams are playing:

- Home win: 46%
- Draw: 25%
- Away win: 29%

These are historical Premier League averages. No per-team differentiation — every match has the same outcome probabilities.

### `season` — Season Rate Model

Same structure as the global model, but derives the home/draw/away rates from the current season's completed results rather than using historical defaults. If the current season has more draws or fewer home wins than average, the model reflects that.

### `poisson` — Poisson Model

The standard approach in football analytics. Computes separate **home and away attack/defense strengths** for each team, relative to league-wide home and away goal averages:

- `home_attack = (team home goals per match) / league avg home goals per match`
- `home_defense = (team home goals conceded per match) / league avg away goals per match`
- `away_attack = (team away goals per match) / league avg away goals per match`
- `away_defense = (team away goals conceded per match) / league avg home goals per match`

Home advantage is captured implicitly through the league-wide averages (home teams typically score more than away teams) rather than as a separate multiplier.

For each simulated match, expected goals are:

- `home_xG = home_attack[home_team] * away_defense[away_team] * league_avg_home`
- `away_xG = away_attack[away_team] * home_defense[home_team] * league_avg_away`

Actual goals are drawn from Poisson distributions with these means, producing realistic scorelines.

Supports `--half-life` for exponential decay weighting (see below).

### `dixoncoles` — Dixon-Coles Model

An extension of the Poisson model from Dixon & Coles (1997). Standard Poisson assumes home and away goals are independent, but in practice low-scoring results (0-0, 1-0, 0-1, 1-1) occur more often than independent Poisson predicts.

Dixon-Coles adds a correction factor **rho** applied to these four scorelines:

| Scoreline | Correction |
|-----------|-----------|
| 0-0 | `1 - rho * home_xG * away_xG` |
| 1-0 | `1 + rho * away_xG` |
| 0-1 | `1 + rho * home_xG` |
| 1-1 | `1 - rho` |

Rho is estimated from the season's data via grid search over log-likelihood, constrained to be non-positive (typically around -0.03 to -0.16). The estimation uses equal weight across all matches regardless of the `--half-life` setting, since rho captures a structural property of football scoring rather than team-specific form. When rho is negative, draws and 0-0 results become more likely.

Uses the same home/away attack/defense split as the Poisson model. Supports `--half-life`.

### `negbin` — Negative Binomial Model

Similar structure to the Poisson model but uses a **negative binomial distribution** to account for potential overdispersion in goal scoring. In theory, football goals can have higher variance than Poisson predicts (more blowouts and more 0-0s). The negative binomial adds an overdispersion parameter **alpha** estimated from the data:

- When alpha = 0, this is equivalent to the Poisson model
- When alpha > 0, the variance is higher: `Var = mean + alpha * mean²`

Implemented as a gamma-Poisson mixture: for each match, the scoring rate is drawn from a Gamma distribution, then goals from a Poisson with that rate.

In practice, testing across Premier League, Championship, and La Liga data shows alpha ≈ 0, meaning goals are well-described by Poisson once team-specific attack/defense strengths are accounted for. The apparent overdispersion seen in some studies is likely an artifact of pooling heterogeneous team strengths.

Uses the same home/away attack/defense split as the Poisson model. Supports `--half-life`.

### `elo` — Elo Model

Computes Elo ratings by replaying all completed matches in chronological order. Uses **margin-of-victory scaling**: the K-factor is multiplied by `ln(1 + goal_difference)` so larger wins produce proportionally bigger rating changes.

Key parameters:
- **K-factor** (20): base value controlling how much each result moves the rating
- **Home advantage** (50 Elo points): added to the home team's rating for expected score calculation

For prediction, the Elo rating difference is mapped to win/draw/loss probabilities. The draw rate is calibrated from the season's observed draw frequency, with evenly-matched teams drawing more often than mismatches.

Elo has implicit time-weighting — recent results are reflected in the current ratings through the chain of updates, so no explicit `--half-life` is needed.

Does not produce scorelines.

### `elopoisson` — Elo-Poisson Hybrid

Combines Elo's strength ordering with Poisson's ability to generate scorelines. Uses margin-of-victory Elo ratings to derive expected goals:

- `home_xG = (league_avg_home + league_avg_away) * elo_expected(rating_diff)`
- `away_xG = (league_avg_home + league_avg_away) * (1 - elo_expected(rating_diff))`

This gives scorelines and goal differences while benefiting from Elo's implicit time-weighting. The trade-off versus the Poisson model is that Elo collapses attack and defense into a single number — a team that scores many but concedes many looks the same as a team that does neither.

## Home/Away Strength Split

The Poisson, Dixon-Coles, and Negative Binomial models compute **separate home and away strengths** for each team. This captures the fact that teams often perform very differently at home versus away — some teams are dominant at home but poor travellers, and vice versa.

Home advantage is captured implicitly through the league-wide home and away goal averages rather than a single multiplier. In a typical season, the league average for home goals is higher than for away goals (e.g., 1.50 vs 1.24), and the per-team strengths are relative to these baselines.

## Exponential Decay (Half-Life)

The `--half-life` option (for `poisson`, `dixoncoles`, and `negbin`) applies exponential decay weighting to matches when computing attack/defense strengths:

```
weight = exp(-ln(2) * age / half_life)
```

Where `age` is measured in number of matches (0 = most recent). A half-life of 10 means a match from 10 games ago counts half as much as the most recent match:

| Age (matches ago) | Weight (hl=10) | Weight (hl=19) |
|---|---|---|
| 0 | 1.00 | 1.00 |
| 5 | 0.71 | 0.83 |
| 10 | 0.50 | 0.69 |
| 19 | 0.27 | 0.50 |
| 30 | 0.13 | 0.33 |
| 38 | 0.07 | 0.25 |

### Blending with Season Values

To prevent extreme strength estimates from short-term streaks, decay-weighted strengths are **blended** with unweighted season values using a 70/30 mix:

```
strength = 0.7 * decay_weighted + 0.3 * season_average
```

This acts as Bayesian shrinkage — even in terrible form, a team's strength is pulled 30% toward their season-long baseline, preventing absurdly low attack ratings from a brief goal drought.

## Goal Difference Tiebreaker

Models that produce scorelines (`poisson`, `dixoncoles`, `negbin`, `elopoisson`) automatically use goal difference as a tiebreaker when teams finish on equal points, matching real league rules. Models without scorelines (`global`, `season`, `elo`) break ties randomly.

## Project Structure

```
plmodel.py          CLI entry point
simulate.py         Data loading, standings calculation, simulation engine
report.py           HTML report generator
fetch.py            football-data.org API client
Makefile            Build automation
models/
  __init__.py       Model registry
  base.py           MatchModel abstract base class
  helpers.py        Shared utilities (Poisson/NegBin sampling, strength computation, Elo)
  global_rate.py    GlobalRateModel
  season_rate.py    SeasonRateModel
  poisson.py        PoissonModel
  dixon_coles.py    DixonColesModel
  negbin.py         NegBinModel
  elo.py            EloModel
  elo_poisson.py    EloPoissonModel
predictions.py      Prediction data serialization (save/load JSON)
```

## Adding a New Model

1. Create `models/yourmodel.py`
2. Subclass `MatchModel` from `models.base`
3. Implement `setup(standings, completed)` and `predict(home, away)`
4. Optionally implement `predict_score(home, away)` for scoreline generation and GD tiebreakers
5. Optionally implement `predict_match_detail(home, away)` for per-match predictions in team detail view
6. Optionally implement `team_columns(team)` for extra output columns
7. Add to `MODELS` dict in `models/__init__.py`
