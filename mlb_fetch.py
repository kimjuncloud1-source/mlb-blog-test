import requests
import os
import sys
import argparse
from datetime import datetime, timedelta, timezone

# ── 설정 ──────────────────────────────────────────────────────────────────────
FAVORITE_TEAMS = [] # 특정 팀만 보고 싶으면 팀 ID를 넣으세요 (예: [119, 147])
POSTS_DIR = "_posts"
BASE_URL = "https://statsapi.mlb.com/api/v1"

# 팀별 이모지 (취향껏 추가 가능)
TEAM_EMOJI = {
    "Yankees": "⚾", "Dodgers": "💙", "Giants": "🟠", "Red Sox": "🧦",
    "Cubs": "🐻", "Braves": "🪓", "Astros": "🚀", "Mets": "🍎"
}

# ── 유틸리티 함수 ──────────────────────────────────────────────────────────────

def post_exists(date_str: str) -> bool:
    """해당 날짜 포스트가 이미 있는지 확인 (폴더 없으면 생성)"""
    if not os.path.exists(POSTS_DIR):
        os.makedirs(POSTS_DIR, exist_ok=True)
        return False
    
    filename_prefix = f"{date_str}-mlb-results"
    for f in os.listdir(POSTS_DIR):
        if f.startswith(filename_prefix):
            return True
    return False

def get_games(date_str: str) -> list:
    """MLB API에서 경기 데이터 가져오기"""
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
        print(f"❌ API 호출 에러: {e}")
        return []

def parse_game(game: dict) -> dict | None:
    """경기 데이터 파싱 (Spring Training 및 Unknown 대응)"""
    status = game.get("status", {}).get("abstractGameState", "")
    if status != "Final":
        return None

    teams = game.get("teams", {})
    away = teams.get("away", {})
    home = teams.get("home", {})

    # 팀명 가져오기 (Spring Training 대응: teamName이 없으면 name 사용)
    away_team = away.get("team", {})
    home_team = home.get("team", {})
    
    # 여러 필드 중 있는 것을 우선적으로 사용
    away_name = away_team.get("teamName") or away_team.get("name") or "Unknown"
    home_name = home_team.get("teamName") or home_team.get("name") or "Unknown"

    away_score = away.get("score", 0)
    home_score = home.get("score", 0)

    # 승자 판별
    if home_score > away_score:
        winner, winner_full = home_name, home_team.get("name", home_name)
    elif away_score > home_score:
        winner, winner_full = away_name, away_team.get("name", away_name)
    else:
        winner, winner_full = "무승부", ""

    # 투수 기록
    decisions = game.get("decisions", {})
    wp = decisions.get("winner", {}).get("fullName", "-")
    lp = decisions.get("loser", {}).get("fullName", "-")

    return {
        "away": away_name,
        "home": home_name,
        "away_score": away_score,
        "home_score": home_score,
        "winner": winner,
        "wp": wp, "lp": lp,
        "venue": game.get("venue", {}).get("name", "Unknown Stadium"),
        "emoji": TEAM_EMOJI.get(winner, "⚾")
    }

# ── 메인 로직 ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args()

    # 날짜 설정 (KST 기준 어제)
    if args.date:
        target_date = args.date
    else:
        kst_now = datetime.now(timezone(timedelta(hours=9)))
        target_date = (kst_now - timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"📅 대상 날짜: {target_date}")

    # 중복 체크
    if post_exists(target_date):
        print("ℹ️ 이미 포스트가 존재합니다. 작업을 종료합니다.")
        return # 여기서 sys.exit(0) 대신 return을 써서 안전하게 종료

    raw_games = get_games(target_date)
    parsed_games = [r for g in raw_games if (r := parse_game(g)) is not None]

    if not parsed_games:
        print("⚠️ 해당 날짜에 완료된 경기가 없습니다.")
        return

    # 마크다운 생성
    content = [
        "---",
        f'title: "MLB 경기 결과 | {target_date}"',
        f"date: {target_date} 09:00:00 +0900",
        "categories: [MLB, Baseball]",
        "---",
        f"\n# ⚾ MLB 경기 결과 ({target_date})\n",
        f"> 총 **{len(parsed_games)}**개의 경기가 완료되었습니다.\n",
        "---"
    ]

    for g in parsed_games:
        content.append(f"### {g['away']} @ {g['home']}")
        content.append(f"- **결과**: {g['emoji']} {g['winner']} 승리 ({g['away_score']} : {g['home_score']})")
        content.append(f"- **구장**: {g['venue']}")
        content.append(f"- **승리/패전**: {g['wp']} / {g['lp']}\n")

    content.append("\n---\n*Data provided by MLB Stats API (Automated Post)*")

    # 파일 저장
    file_path = f"{POSTS_DIR}/{target_date}-mlb-results.md"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(content))
    
    print(f"✅ 성공: {file_path} 생성 완료!")

    # GitHub Actions용 출력
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"post_date={target_date}\n")
            f.write(f"game_count={len(parsed_games)}\n")

if __name__ == "__main__":
    main()
