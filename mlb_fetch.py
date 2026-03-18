import requests
import os
import argparse
from datetime import datetime, timedelta, timezone

BASE_URL = "https://statsapi.mlb.com/api/v1"
OUTPUT_DIR = "site"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "index.html")

def get_games(date_str):
    url = f"{BASE_URL}/schedule?sportId=1&date={date_str}&hydrate=linescore,decisions,team"
    data = requests.get(url).json()
    games = []
    for d in data.get("dates", []):
        games.extend(d.get("games", []))
    return games

def parse_game(game):
    if game["status"]["abstractGameState"] != "Final":
        return None

    away = game["teams"]["away"]["team"]["name"]
    home = game["teams"]["home"]["team"]["name"]
    away_score = game["teams"]["away"]["score"]
    home_score = game["teams"]["home"]["score"]

    return f"{away} {away_score} : {home_score} {home}"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args()

    if args.date:
        date = args.date
    else:
        kst = datetime.now(timezone(timedelta(hours=9)))
        date = (kst - timedelta(days=1)).strftime("%Y-%m-%d")

    games = get_games(date)
    results = [parse_game(g) for g in games if parse_game(g)]

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    html = f"<h1>MLB 경기 결과 ({date})</h1>"
    for r in results:
        html += f"<p>{r}</p>"

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print("완료")

if __name__ == "__main__":
    main()
