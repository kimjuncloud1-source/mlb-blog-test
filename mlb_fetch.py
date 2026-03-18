import requests
import os
import sys
import argparse
from datetime import datetime, timedelta, timezone

# ── 설정 ──────────────────────────────────────────────────────────────────────
# 관심 팀만 필터링하려면 여기에 팀 ID 추가 (예: [119, 147])
FAVORITE_TEAMS = []
POSTS_DIR = "_posts"
BASE_URL = "https://statsapi.mlb.com/api/v1"

TEAM_EMOJI = {
    "Yankees": "⚾", "Dodgers": "💙", "Giants": "🟠", "Red Sox": "🧦",
    "Cubs": "🐻", "Cardinals": "🐦", "Astros": "🚀", "Braves": "🪓"
}

# ── 유틸 ──────────────────────────────────────────────────────────────────────

def post_exists(date_str: str) -> bool:
    """해당 날짜 포스트가 이미 있는지 확인"""
    if not os.path.exists(POSTS_DIR):
        os.makedirs(POSTS_DIR, exist_ok=True)
        return False
    filename_prefix = f"{date_str}-mlb-results"
    for f in os.listdir(POSTS_DIR):
        if f.startswith(filename_prefix):
            return True
    return False

def get_games(date_str: str) -> list:
    """MLB API 호출"""
    url = f"{BASE_URL}/schedule?sportId=1&date={date_str}&hydrate=linescore,decisions,team"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        games = []
        for d in data.get("dates", []):
            games.extend(d.get("games", []))
        return games
    except Exception as e:
        print(f"❌ API 에러: {e}")
        return []

def parse_game(game: dict) -> dict | None:
    """경기 데이터 정리 (시범 경기/정규 시즌 모두 대응)"""
    status = game.get("status", {}).get("abstractGameState", "")
    if status != "Final":
        return None

    teams = game.get("teams", {})
    away_team = teams.get("away", {}).get("team", {})
    home_team = teams.get("home", {}).get("team", {})

    # 팀 이름 가져오기 (시범 경기 데이터 구조 대응)
    away_name = away_team.get("teamName") or away_team.get("name") or "Unknown"
    home_name = home_team.get("teamName") or home_team.get("name") or "Unknown"

    away_score = teams.get("away", {}).get("score", 0)
    home_score = teams.get("home", {}).get("score", 0)

    winner = home_name if home_score > away_score else away_name
    if home_score == away_score: winner = "무승부"

    decisions = game.get("decisions", {})
    wp = decisions.get("winner", {}).get("fullName", "-")
    lp = decisions.get("loser", {}).get("fullName", "-")

    return {
        "away": away_name, "home": home_name,
        "away_score": away_score, "home_score": home_score,
        "winner": winner, "wp": wp, "lp": lp,
        "venue": game.get("venue", {}).get("name", ""),
        "emoji": TEAM_EMOJI.get(winner, "⚾")
    }

# ── 메인 ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args()

    if args.date:
        target_date = args.date
    else:
        kst_now = datetime.now(timezone(timedelta(hours=9)))
        target_date = (kst_now - timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"📅 대상 날짜: {target_date}")

    if post_exists(target_date):
        print("ℹ️ 이미 포스트가 존재합니다. 생략합니다.")
        return

    raw_games = get_games(target_date)
    parsed = [r for g in raw_games if (r := parse_game(g)) is not None]

    if not parsed:
        print("⚠️ 완료된 경기가 없습니다.")
        return

    # 마크다운 내용 생성
    lines = [
        "---",
        f'title: "MLB 경기 결과 | {target_date}"',
        f"date: {target_date} 09:00:00 +0900",
        "categories: [MLB, 경기결과]",
        "---",
        f"\n# ⚾ MLB 경기 결과 ({target_date})\n",
        f"오늘 총 **{len(parsed)}**경기가 종료되었습니다.\n"
    ]

    for g in parsed:
        lines.append(f"### {g['away']} @ {g['home']}")
        lines.append(f"- **결과**: {g['emoji']} {g['winner']} 승리 ({g['away_score']}:{g['home_score']})")
        lines.append(f"- **승리/패전**: {g['wp']} / {g['lp']}")
        lines.append(f"- **구장**: {g['venue']}\n")

    lines.append("\n---\n*Data from MLB Stats API (Auto-posted)*")

    # 파일 저장
    os.makedirs(POSTS_DIR, exist_ok=True)
    file_path = f"{POSTS_DIR}/{target_date}-mlb-results.md"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"✅ 생성 완료: {file_path}")

    # GitHub Actions 출력을 위한 설정
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"post_date={target_date}\n")
            f.write(f"game_count={len(parsed)}\n")

if __name__ == "__main__":
    main()
