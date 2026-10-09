"""Free NFL Elo baseline using chronological nflverse schedule data. Python stdlib only."""
import csv, io, json, math, os, urllib.request
from datetime import datetime, timezone
from pathlib import Path
URL='https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv'
OUT=Path(__file__).resolve().parents[1]/'nfl-data.json'
CURRENT=2026
K=20.0
HOME_ELO=55.0
SCALE=25.0

def number(v):
    try: return float(v) if v not in ('',None,'NA') else None
    except (ValueError,TypeError): return None

def probability(diff): return 1/(1+10**(-diff/400))

def load():
    req=urllib.request.Request(URL,headers={'User-Agent':'Model3-NFL-Research/0.1'})
    with urllib.request.urlopen(req,timeout=45) as resp: data=resp.read().decode('utf-8-sig')
    rows=list(csv.DictReader(io.StringIO(data)))
    if not rows or 'home_team' not in rows[0] or 'away_team' not in rows[0]: raise RuntimeError('Unexpected schedule CSV schema')
    return rows

def build(rows):
    rows=[r for r in rows if r.get('season','').isdigit() and 2018<=int(r['season'])<=CURRENT and r.get('game_type') in ('REG','WC','DIV','CON','SB')]
    rows.sort(key=lambda r:(int(r['season']),str(r.get('gameday','')),str(r.get('gametime','')),str(r.get('game_id',''))))
    ratings={}; prev_season=None; games=[]; checked=0; brier=0; abs_margin=0
    for r in rows:
        season=int(r['season']); home=r['home_team'];away=r['away_team']
        if not home or not away: continue
        if prev_season is not None and season!=prev_season:
            ratings={t:1500+(v-1500)*.67 for t,v in ratings.items()}
        prev_season=season
        rh=ratings.get(home,1500);ra=ratings.get(away,1500)
        diff=rh-ra+HOME_ELO; p=probability(diff); margin=diff/SCALE
        hs=number(r.get('home_score'));as_=number(r.get('away_score'))
        done=hs is not None and as_ is not None
        if season==CURRENT:
            games.append({'id':r.get('game_id',''), 'date':r.get('gameday',''), 'week':r.get('week',''), 'home':home,'away':away,'status':'final' if done else 'scheduled','homeScore':hs,'awayScore':as_,'homeWin':round(p,4),'projectedMargin':round(margin,1),'homeElo':round(rh,1),'awayElo':round(ra,1)})
        if done:
            result=1 if hs>as_ else 0 if hs<as_ else .5
            if season>=2023:
                checked+=1;brier+=(p-result)**2;abs_margin+=abs(margin-(hs-as_))
            delta=K*(result-p)
            ratings[home]=rh+delta;ratings[away]=ra-delta
    if not games: raise RuntimeError('No current-season games returned; preserving last successful output')
    return {'schemaVersion':1,'model':'elo-baseline-0.1','generatedAt':datetime.now(timezone.utc).isoformat(),'source':URL,'season':CURRENT,'assumptions':{'initialElo':1500,'homeFieldElo':HOME_ELO,'k':K,'offseasonRegression':.67,'marginPointsPerElo':SCALE},'validation':{'sampleGames':checked,'brier':round(brier/checked,4) if checked else None,'marginMAE':round(abs_margin/checked,2) if checked else None,'note':'Chronological one-step-ahead evaluation 2023 onward; fixed parameters, not independently optimized. Includes only games with final scores.'},'games':games,'ratings':[{'team':k,'elo':round(v,1)} for k,v in sorted(ratings.items(),key=lambda kv:-kv[1])]}

if __name__=='__main__':
    result=build(load())
    OUT.write_text(json.dumps(result,indent=2)+'\n')
    print('Wrote',OUT,'games',len(result['games']),'validated',result['validation']['sampleGames'])
