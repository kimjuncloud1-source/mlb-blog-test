"""
mlb_fetch.py
------------
MLB 전날 경기 결과를 statsapi.mlb.com 에서 가져와서
GitHub Pages (Jekyll/Chirpy 테마 기준) 마크다운 포스트로 저장합니다.

사용법:
  python mlb_fetch.py              # 어제 경기 결과
  python mlb_fetch.py --date 2025-04-10  # 특정 날짜
"""

import requests
import json
import os
import sys
import argparse
from datetime import datetime, timedelta, timezone

# ── 설정 ──────────────────────────────────────────────────────────────────────

# 관심 팀만 필터링하려면 여기에 팀 ID 추가 (비워두면 전체 경기)
# 팀 ID 목록: https://statsapi.mlb.com/api/v1/teams?sportId=1
FAVORITE_TEAMS = []   # 예: [147, 136]  → Yankees, Mariners

# 포스트 저장 경로 (Jekyll 기준)
POSTS_DIR = "_posts"

# ── MLB API 호출 ───────────────────────────────────────────────────────────────

BASE_URL = "https://statsapi.mlb.com/api/v1"

TEAM_EMOJI = {
    "Yankees": "⚾", "Red Sox": "🧦", "Dodgers": "💙", "Giants": "🟠",
    "Cubs": "🐻", "Cardinals": "🐦", "Astros": "🚀", "Braves": "🪓",
}

def get_games(date_str: str) -> list:
    """주어진 날짜의 MLB 경기 목록 반환 (date_str: 'YYYY-MM-DD')"""
    url = f"{BASE_URL}/schedule?sportId=1&date={date_str}&hydrate=linescore,decisions"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    games = []
    for date_obj in data.get("dates", []):
        for game in date_obj.get("games", []):
            games.append(game)
    return games


def parse_game(game: dict) -> dict | None:
    """경기 dict에서 필요한 정보만 추출"""
    status = game.get("status", {}).get("abstractGameState", "")
    if status != "Final":
        return None  # 완료된 경기만

    teams = game.get("teams", {})
    away = teams.get("away", {})
    home = teams.get("home", {})

    away_name = away.get("team", {}).get("teamName", "Unknown")
    home_name = home.get("team", {}).get("teamName", "Unknown")
    away_score = away.get("score", 0)
    home_score = home.get("score", 0)

    winner = home_name if home_score > away_score else away_name
    loser  = away_name if home_score > away_score else home_name

    # 이닝 정보
    linescore = game.get("linescore", {})
    innings_count = linescore.get("currentInning", 9)
    extra = f" ({innings_count}이닝)" if innings_count > 9 else ""

    # 투수 결정 (있을 때만)
    decisions = game.get("decisions", {})
    wp = decisions.get("winner", {}).get("fullName", "")
    lp = decisions.get("loser",  {}).get("fullName", "")
    sv = decisions.get("save",   {}).get("fullName", "")

    emoji = TEAM_EMOJI.get(winner, "⚾")

    return {
        "away": away_name,
        "home": home_name,
        "away_score": away_score,
        "home_score": home_score,
        "winner": winner,
        "loser": loser,
        "extra": extra,
        "wp": wp,
        "lp": lp,
        "sv": sv,
        "emoji": emoji,
        "game_id": game.get("gamePk"),
        "venue": game.get("venue", {}).get("name", ""),
    }


def filter_games(games: list, team_ids: list) -> list:
    """관심 팀 필터 (FAVORITE_TEAMS 비어있으면 전체 반환)"""
    if not team_ids:
        return games
    filtered = []
    for g in games:
        teams = g.get("teams", {})
        ids = [
            teams.get("away", {}).get("team", {}).get("id"),
            teams.get("home", {}).get("team", {}).get("id"),
        ]
        if any(tid in team_ids for tid in ids):
            filtered.append(g)
    return filtered


# ── 마크다운 포스트 생성 ──────────────────────────────────────────────────────

def build_markdown(parsed_games: list, date_str: str) -> str:
    """Jekyll Front Matter + 경기 결과 마크다운 생성"""
    kst_date = datetime.strptime(date_str, "%Y-%m-%d")
    title_date = kst_date.strftime("%Y년 %m월 %d일")

    lines = [
        "---",
        f'title: "MLB 경기 결과 | {title_date}"',
        f"date: {date_str} 09:00:00 +0900",
        'categories: [MLB, 경기결과]',
        'tags: [mlb, baseball, 야구]',
        "---\n",
        f"# ⚾ MLB 경기 결과 — {title_date}\n",
        f"> 총 **{len(parsed_games)}경기** 진행\n",
        "---\n",
    ]

    if not parsed_games:
        lines.append("오늘은 예정된 경기가 없었습니다.\n")
        return "\n".join(lines)

    for g in parsed_games:
        score_line = f"**{g['away']}** {g['away_score']} : {g['home_score']} **{g['home']}**{g['extra']}"
        result_line = f"{g['emoji']} **승리** → {g['winner']}"

        lines.append(f"## {g['away']} @ {g['home']}\n")
        lines.append(f"| 구분 | 내용 |")
        lines.append(f"|------|------|")
        lines.append(f"| 스코어 | {score_line} |")
        lines.append(f"| 결과 | {result_line} |")
        if g["venue"]:
            lines.append(f"| 구장 | {g['venue']} |")
        if g["wp"]:
            lines.append(f"| 승리투수 | {g['wp']} |")
        if g["lp"]:
            lines.append(f"| 패전투수 | {g['lp']} |")
        if g["sv"]:
            lines.append(f"| 세이브 | {g['sv']} |")
        lines.append("")

    lines.append("---")
    lines.append(f"\n*데이터 출처: [MLB Stats API](https://statsapi.mlb.com) | 자동 업데이트*")
    return "\n".join(lines)


# ── 파일 저장 ──────────────────────────────────────────────────────────────────

def save_post(content: str, date_str: str):
    os.makedirs(POSTS_DIR, exist_ok=True)
    filename = f"{POSTS_DIR}/{date_str}-mlb-results.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ 포스트 저장 완료: {filename}")
    return filename


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (기본: 어제)")
    args = parser.parse_args()

    if args.date:
        target_date = args.date
    else:
        # KST 기준 어제 날짜 (UTC+9)
        kst_now = datetime.now(timezone(timedelta(hours=9)))
        yesterday = kst_now - timedelta(days=1)
        target_date = yesterday.strftime("%Y-%m-%d")

    print(f"📅 대상 날짜: {target_date}")

    print("🔄 MLB API 호출 중...")
    raw_games = get_games(target_date)
    filtered  = filter_games(raw_games, FAVORITE_TEAMS)

    parsed = [r for g in filtered if (r := parse_game(g)) is not None]
    print(f"✅ 완료된 경기: {len(parsed)}개")

    md_content = build_markdown(parsed, target_date)
    save_post(md_content, target_date)

    # GitHub Actions 환경에서 사용할 수 있도록 output 변수 설정
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"post_date={target_date}\n")
            f.write(f"game_count={len(parsed)}\n")


if __name__ == "__main__":
    main()
