#!/usr/bin/env python3
"""Download public Sleeper NFL player metadata; never includes private projections."""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

URL = 'https://api.sleeper.app/v1/players/nfl'
OUT = Path(os.environ.get('SLEEPER_OUTPUT', 'sleeper-players.json'))
FIELDS = ('full_name', 'first_name', 'last_name', 'team', 'position', 'fantasy_positions', 'active', 'status', 'injury_status', 'practice_participation', 'depth_chart_position', 'depth_chart_order', 'espn_id', 'gsis_id', 'sportradar_id')


def transform(data):
    if not isinstance(data, dict) or len(data) < 100:
        raise ValueError('Sleeper player feed was empty or unexpectedly small')
    players = []
    for player_id, player in data.items():
        if not isinstance(player, dict):
            continue
        if player.get('position') not in ('QB', 'RB', 'WR', 'TE', 'K'):
            continue
        name = player.get('full_name') or ' '.join(filter(None, [player.get('first_name'), player.get('last_name')]))
        if not name:
            continue
        row = {'sleeper_id': str(player_id), **{key: player.get(key) for key in FIELDS}}
        row['full_name'] = name
        players.append(row)
    if len(players) < 100:
        raise ValueError('Too few eligible NFL players returned')
    players.sort(key=lambda x: (x['full_name'].lower(), x['sleeper_id']))
    return {'source': 'Sleeper public NFL players API', 'source_url': URL, 'updated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'player_count': len(players), 'players': players, 'notes': 'Metadata and injury-status indicators only; not official injury reports or weekly statistical projections.'}


def main():
    req = urllib.request.Request(URL, headers={'User-Agent': 'Model33-NFLResearch/1.0', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=45) as response:
        data = json.load(response)
    result = transform(data)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(OUT.suffix + '.tmp')
    tmp.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    tmp.replace(OUT)
    print(f"Saved {result['player_count']} player records to {OUT}")


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Sleeper update failed: {exc}', file=sys.stderr)
        sys.exit(1)
