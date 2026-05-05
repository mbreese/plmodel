#!/usr/bin/env python3
"""Fetch match data from football-data.org API.

Usage:
    python fetch.py PL ELC PD
    python fetch.py PL --season 2024
    python fetch.py --list

Fetches all matches (completed + scheduled) for each competition and saves
to data/{competition}.csv in a format compatible with load_fixtures().

Respects the API rate limit of 10 requests per minute.
"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.request
import urllib.error


API_BASE = "https://api.football-data.org/v4"
API_KEY_FILE = ".api_key"

# Minimum interval between requests (seconds). Free tier allows 10 req/min.
MIN_REQUEST_INTERVAL = 6.5  # ~9 req/min, with margin


class RateLimitedClient:
    """HTTP client that enforces a minimum interval between requests."""

    def __init__(self, api_key, min_interval=MIN_REQUEST_INTERVAL):
        self.api_key = api_key
        self.min_interval = min_interval
        self.last_request_time = 0

    def get(self, url):
        """Make a GET request, waiting if necessary to respect rate limits."""
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.min_interval:
            wait = self.min_interval - elapsed
            print(f"  Rate limit: waiting {wait:.1f}s...")
            time.sleep(wait)

        req = urllib.request.Request(url)
        req.add_header("X-Auth-Token", self.api_key)

        try:
            self.last_request_time = time.time()
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                # Rate limited — wait and retry
                retry_after = int(e.headers.get("X-RequestCounter-Reset", 60))
                print(f"  Rate limited. Waiting {retry_after}s...")
                time.sleep(retry_after)
                return self.get(url)
            else:
                body = e.read().decode() if e.fp else ""
                print(f"  API error {e.code}: {body}", file=sys.stderr)
                raise


def load_api_key():
    """Load API key from environment variable or .api_key file."""
    key = os.environ.get("FOOTBALL_DATA_API_KEY", "").strip()

    if not key and os.path.exists(API_KEY_FILE):
        with open(API_KEY_FILE) as f:
            key = f.read().strip()

    if not key:
        print("Error: No API key found.", file=sys.stderr)
        print("Set FOOTBALL_DATA_API_KEY environment variable, or", file=sys.stderr)
        print(f"save your key to '{API_KEY_FILE}'", file=sys.stderr)
        print("Get a free key at https://www.football-data.org/client/register", file=sys.stderr)
        sys.exit(1)

    return key


def fetch_competitions(client):
    """Fetch list of available competitions."""
    data = client.get(f"{API_BASE}/competitions")
    return data["competitions"]


def fetch_matches(client, competition, season=None):
    """Fetch all matches for a competition.

    Returns the full API response including match details.
    """
    url = f"{API_BASE}/competitions/{competition}/matches"
    if season:
        url += f"?season={season}"
    return client.get(url)


def matches_to_csv(matches_data, output_path):
    """Convert API match data to CSV format compatible with load_fixtures().

    Includes both completed and scheduled matches. Scheduled matches have
    empty score columns so load_fixtures() treats them as remaining fixtures.
    """
    matches = matches_data.get("matches", [])

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Date", "Time", "Matchday", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"])

        for m in matches:
            home = m["homeTeam"]["shortName"]
            away = m["awayTeam"]["shortName"]

            # Parse date/time from UTC
            utc_date = m.get("utcDate", "")
            if utc_date:
                date_str = utc_date[:10]  # YYYY-MM-DD
                time_str = utc_date[11:16]  # HH:MM
            else:
                date_str = ""
                time_str = ""

            matchday = m.get("matchday", "")

            status = m.get("status", "")
            score = m.get("score", {})
            full_time = score.get("fullTime", {})

            if status == "FINISHED" and full_time.get("home") is not None:
                hg = full_time["home"]
                ag = full_time["away"]
                if hg > ag:
                    ftr = "H"
                elif hg == ag:
                    ftr = "D"
                else:
                    ftr = "A"
                writer.writerow([date_str, time_str, matchday, home, away, hg, ag, ftr])
            else:
                # Scheduled/postponed — no scores
                writer.writerow([date_str, time_str, matchday, home, away, "", "", ""])

    finished = sum(1 for m in matches if m.get("status") == "FINISHED")
    remaining = len(matches) - finished
    print(f"  Saved {len(matches)} matches ({finished} finished, {remaining} remaining)")


def fetch_deductions(client, competition, season=None):
    """Fetch standings and detect point deductions.

    Compares 3*W + D against reported points to infer deductions.
    Returns a list of (team, points_deducted) tuples, or empty list if none.
    """
    url = f"{API_BASE}/competitions/{competition}/standings"
    if season:
        url += f"?season={season}"
    data = client.get(url)

    deductions = []
    for entry in data.get("standings", []):
        if entry.get("type") != "TOTAL":
            continue
        for team in entry.get("table", []):
            expected = 3 * team["won"] + team["draw"]
            actual = team["points"]
            if expected > actual:
                name = team["team"]["shortName"]
                deductions.append((name, expected - actual))

    return deductions


def write_deductions(deductions, output_path):
    """Write deductions to a CSV file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["team", "points"])
        for team, pts in deductions:
            writer.writerow([team, pts])
    print(f"  Deductions: {', '.join(f'{t} (-{p})' for t, p in deductions)}")


def list_competitions(client):
    """Print available competitions."""
    comps = fetch_competitions(client)
    print(f"\n{'Code':<8} {'Name':<40} {'Country'}")
    print("-" * 65)
    for c in sorted(comps, key=lambda x: (x.get("area", {}).get("name", ""), x.get("name", ""))):
        code = c.get("code", "?")
        name = c.get("name", "?")
        country = c.get("area", {}).get("name", "?")
        print(f"{code:<8} {name:<40} {country}")


def main():
    parser = argparse.ArgumentParser(
        description="Fetch match data from football-data.org API"
    )
    parser.add_argument(
        "competitions", nargs="*",
        help="Competition codes to fetch (e.g., PL ELC PD)"
    )
    parser.add_argument(
        "--season", type=int, default=None,
        help="Season year (e.g., 2025 for 2025/26). Defaults to current season."
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List available competitions and exit"
    )
    parser.add_argument(
        "--output-dir", default="data",
        help="Output directory for CSV files (default: data)"
    )
    args = parser.parse_args()

    api_key = load_api_key()
    client = RateLimitedClient(api_key)

    if args.list:
        list_competitions(client)
        return

    if not args.competitions:
        parser.error("Specify one or more competition codes (e.g., PL ELC PD), or use --list")

    for comp in args.competitions:
        print(f"\nFetching {comp}...")
        try:
            data = fetch_matches(client, comp, season=args.season)
        except Exception as e:
            print(f"  Error fetching {comp}: {e}", file=sys.stderr)
            continue

        competition_name = data.get("competition", {}).get("name", comp)
        season_info = data.get("filters", {}).get("season", "")
        print(f"  Competition: {competition_name}")
        if season_info:
            print(f"  Season: {season_info}")

        output_path = os.path.join(args.output_dir, f"{comp}.csv")
        matches_to_csv(data, output_path)
        print(f"  Written to {output_path}")

        # Fetch standings to detect deductions
        try:
            deductions = fetch_deductions(client, comp, season=args.season)
            deductions_path = os.path.join(args.output_dir, f"{comp}-deductions.csv")
            if deductions:
                write_deductions(deductions, deductions_path)
            elif os.path.exists(deductions_path):
                os.remove(deductions_path)
                print(f"  No deductions (removed {deductions_path})")
            else:
                print(f"  No deductions")
        except Exception as e:
            print(f"  Warning: could not fetch deductions: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
