
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API_KEY = os.environ.get("ODDS_API_KEY")
if not API_KEY:
    raise RuntimeError("Missing ODDS_API_KEY secret")

BASE_URL = "https://api.the-odds-api.com/v4"
SPORT = "americanfootball_nfl"

params = urllib.parse.urlencode({
    "apiKey": API_KEY,
    "regions": "us",
    "markets": "h2h,spreads,totals",
    "oddsFormat": "american",
    "dateFormat": "iso",
})

url = f"{BASE_URL}/sports/{SPORT}/odds/?{params}"

request = urllib.request.Request(
    url,
    headers={"User-Agent": "Model3Dashboard/3.2"}
)

with urllib.request.urlopen(request, timeout=30) as response:
    games = json.load(response)
    remaining = response.headers.get("x-requests-remaining")
    used = response.headers.get("x-requests-used")

bookmakers = sorted({
    book.get("key", "")
    for game in games
    for book in game.get("bookmakers", [])
})

hard_rock = [
    name for name in bookmakers
    if "hardrock" in name.lower()
    or "hard_rock" in name.lower()
]

output = {
    "updated_at": datetime.now(timezone.utc).isoformat(),
    "sport": SPORT,
    "game_count": len(games),
    "bookmakers": bookmakers,
    "hard_rock_bookmakers": hard_rock,
    "games": games,
}

with open("nfl-odds.json", "w", encoding="utf-8") as file:
    json.dump(output, file, indent=2)

print(f"Games retrieved: {len(games)}")
print(f"Bookmakers: {', '.join(bookmakers)}")
print(f"Hard Rock matches: {hard_rock}")
print(f"API requests used: {used}")
print(f"API requests remaining: {remaining}")
print("Saved nfl-odds.json")
