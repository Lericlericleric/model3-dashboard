"""Model 3.3 NFL research baseline: chronological Elo plus leakage-safe scoring context.

Uses public nflverse schedule CSV and Python standard library only. The existing
homeWin and projectedMargin fields remain Elo-derived for dashboard compatibility.
New score context is descriptive/experimental, NOT a calibrated betting total.
"""
import csv
import io
import json
import math
import urllib.request
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

URL = 'https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv'
OUT = Path(__file__).resolve().parents[1] / 'nfl-data.json'
CURRENT = 2026
K = 20.0
HOME_ELO = 55.0
SCALE = 25.0
WINDOW = 8
PRIOR_GAMES = 4
LEAGUE_PPG = 22.5  # Explicit baseline assumption; not a fitted current-season estimate.


def number(v):
    try:
        x = float(v) if v not in ('', None, 'NA') else None
        return x if x is None or math.isfinite(x) else None
    except (ValueError, TypeError):
        return None


def probability(diff):
    return 1 / (1 + 10 ** (-diff / 400))


def load():
    req = urllib.request.Request(URL, headers={'User-Agent': 'Model3-NFL-Research/0.3'})
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = resp.read().decode('utf-8-sig')
    rows = list(csv.DictReader(io.StringIO(data)))
    if not rows or not {'home_team', 'away_team', 'season', 'gameday'}.issubset(rows[0]):
        raise RuntimeError('Unexpected schedule CSV schema')
    return rows


def mean_or_prior(values, prior):
    """Shrink short histories toward a stated league-wide assumption."""
    values = list(values)
    return (sum(values) + PRIOR_GAMES * prior) / (len(values) + PRIOR_GAMES)


def build(rows):
    rows = [r for r in rows if str(r.get('season', '')).isdigit()
            and 2018 <= int(r['season']) <= CURRENT
            and r.get('game_type') in ('REG', 'WC', 'DIV', 'CON', 'SB')]
    rows.sort(key=lambda r: (int(r['season']), str(r.get('gameday', '')),
                             str(r.get('gametime', '')), str(r.get('game_id', ''))))
    ratings = {}
    scored = defaultdict(lambda: deque(maxlen=WINDOW))
    allowed = defaultdict(lambda: deque(maxlen=WINDOW))
    prev_season = None
    games = []
    checked = 0
    brier = 0.0
    abs_margin = 0.0
    total_checked = 0
    abs_total = 0.0

    for r in rows:
        season = int(r['season'])
        home, away = r['home_team'], r['away_team']
        if not home or not away or home == away:
            continue
        if prev_season is not None and season != prev_season:
            ratings = {t: 1500 + (v - 1500) * .67 for t, v in ratings.items()}
            scored.clear()
            allowed.clear()
        prev_season = season
        rh, ra = ratings.get(home, 1500), ratings.get(away, 1500)
        diff = rh - ra + HOME_ELO
        p = probability(diff)
        margin = diff / SCALE
        # Calculated strictly from games already processed; no future results.
        h_off = mean_or_prior(scored[home], LEAGUE_PPG)
        a_off = mean_or_prior(scored[away], LEAGUE_PPG)
        h_def = mean_or_prior(allowed[home], LEAGUE_PPG)
        a_def = mean_or_prior(allowed[away], LEAGUE_PPG)
        projected_home = (h_off + a_def) / 2
        projected_away = (a_off + h_def) / 2
        projected_total = projected_home + projected_away
        hs, as_ = number(r.get('home_score')), number(r.get('away_score'))
        done = hs is not None and as_ is not None
        if season == CURRENT:
            games.append({
                'id': r.get('game_id', ''), 'date': r.get('gameday', ''),
                'week': r.get('week', ''), 'home': home, 'away': away,
                'status': 'final' if done else 'scheduled',
                'homeScore': hs, 'awayScore': as_,
                'homeWin': round(p, 4), 'projectedMargin': round(margin, 1),
                'homeElo': round(rh, 1), 'awayElo': round(ra, 1),
                'scoringContext': {
                    'projectedHomePoints': round(projected_home, 1),
                    'projectedAwayPoints': round(projected_away, 1),
                    'projectedTotal': round(projected_total, 1),
                    'homeOffensePPG': round(h_off, 1),
                    'awayOffensePPG': round(a_off, 1),
                    'homeDefenseAllowedPPG': round(h_def, 1),
                    'awayDefenseAllowedPPG': round(a_def, 1),
                    'homeSampleGames': len(scored[home]),
                    'awaySampleGames': len(scored[away]),
                    'status': 'experimental-not-calibrated'
                }
            })
        if done:
            result = 1 if hs > as_ else 0 if hs < as_ else .5
            if season >= 2023:
                checked += 1
                brier += (p - result) ** 2
                abs_margin += abs(margin - (hs - as_))
                total_checked += 1
                abs_total += abs(projected_total - (hs + as_))
            delta = K * (result - p)
            ratings[home] = rh + delta
            ratings[away] = ra - delta
            scored[home].append(hs)
            scored[away].append(as_)
            allowed[home].append(as_)
            allowed[away].append(hs)

    if not games:
        raise RuntimeError('No current-season games returned; preserving last successful output')
    return {
        'schemaVersion': 1, 'model': 'elo-baseline-0.1 + scoring-context-0.1',
        'generatedAt': datetime.now(timezone.utc).isoformat(),
        'source': URL, 'season': CURRENT,
        'assumptions': {
            'initialElo': 1500, 'homeFieldElo': HOME_ELO, 'k': K,
            'offseasonRegression': .67, 'marginPointsPerElo': SCALE,
            'scoringWindow': WINDOW, 'scoringPriorGames': PRIOR_GAMES,
            'scoringPriorPPG': LEAGUE_PPG
        },
        'validation': {
            'sampleGames': checked,
            'brier': round(brier / checked, 4) if checked else None,
            'marginMAE': round(abs_margin / checked, 2) if checked else None,
            'experimentalTotalMAE': round(abs_total / total_checked, 2) if total_checked else None,
            'note': 'Chronological one-step-ahead evaluation from 2023; fixed assumptions, not independently optimized or tested for profitability. Score context is a simple rolling average, not a calibrated totals model.'
        },
        'games': games,
        'ratings': [{'team': t, 'elo': round(v, 1)} for t, v in sorted(ratings.items(), key=lambda kv: -kv[1])]
    }


if __name__ == '__main__':
    result = build(load())
    OUT.write_text(json.dumps(result, indent=2) + '\n')
    print('Wrote', OUT, 'games', len(result['games']), 'validated', result['validation']['sampleGames'])
