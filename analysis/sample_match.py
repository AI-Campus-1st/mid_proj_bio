"""뉴스-공시 매칭 검수용 표본 추출 — 연결 50쌍을 층화 무작위로 뽑는다.

목적: docs/04_ai/NEWS_DISCLOSURE_MATCHING.md 6절 "M1 매칭" 평가.
      사람이 쌍마다 "같은 사건 / 관련 / 무관"을 판정해 직접 창 정밀도와 후속 창 관련 비율을 잰다.
      직접 창을 ±3일로 줄인 근거("당일에서 먼 연결은 같은 사건이 아닐 가능성이 크다", 3-2절)도 함께 확인하도록
      직접 창을 당일(day_gap = 0)과 당일 아님(±1~3일)으로 나눠 뽑는다.
입력: data/processed/news_disclosure_links.csv (analysis/match_news_disclosure.py 결과), 통합 DB(기사 제목·공시 원문)
층:   직접·당일 / 직접·±1~3일 / 후속(+4~+90일)  ×  삼성바이오로직스 / 그 외 4개사
      연결의 약 91%가 삼성바이오로직스라 그냥 뽑으면 다른 기업이 거의 안 나온다. 그래서 기업도 층으로 둔다.
      한 칸의 쌍이 모자라면 같은 창의 다른 기업 칸에서 채운다.
출력: data/eval/match_sample.csv (UTF-8 BOM, 엑셀에서 바로 열림)
      검수자는 judge_a, judge_b 에 각자 판정을 적고, 둘이 다르면 합의해 label_final 을 채운다.
      판정 값: 같은 사건 / 관련 / 무관
        같은 사건 = 기사가 그 공시의 사건(같은 계약·투자·결정)을 다룬다
        관련     = 같은 사건은 아니지만 같은 기업의 같은 종류 사업 활동이라 함께 볼 만하다
        무관     = 기업만 같고 내용이 이어지지 않는다
      judge_claude·claude_confidence·claude_reason 은 Claude 의 1차 판정이다 (2026-11-18, 기사 본문·공시 원문을
      읽고 판정). 사람 판정이 아니므로 label_final 을 사람이 확인해 채운다.
실행: python analysis/sample_match.py [--force]
      판정이 이미 적힌 파일은 덮어쓰지 않는다. 새로 뽑으려면 --force (기존 판정 삭제).
      python analysis/sample_match.py --summary
      층별 판정 집계만 출력한다. label_final 이 있으면 그 값을, 없으면 judge_claude 를 센다.
주의: 층마다 뽑는 비율이 다르므로 50쌍 전체의 비율을 그대로 전체 정밀도로 쓰면 안 된다. 층별로 본다.
"""
import csv
import random
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "collect"))
from config import DB_PATH  # noqa: E402

LINKS = ROOT / "data" / "processed" / "news_disclosure_links.csv"
OUT = ROOT / "data" / "eval" / "match_sample.csv"
SEED = 20261117          # 고정 시드 — 입력 파일이 같으면 다시 실행해도 같은 표본이 나온다
BIG = "삼성바이오로직스"
EXCERPT_CHARS = 400      # 공시 원문 앞부분을 이만큼 함께 보여 준다
# 층별 표본 수: (창 구분, 삼성바이오로직스, 그 외)
PLAN = [("direct_same_day", 10, 5), ("direct_near", 10, 5), ("follow", 12, 8)]
STRATUM_KO = {"direct_same_day": "직접·당일", "direct_near": "직접·±1~3일", "follow": "후속"}
JUDGE_COLS = ["judge_claude", "claude_confidence", "claude_reason", "judge_a", "judge_b", "label_final", "note"]
LABELS = ["같은 사건", "관련", "무관"]
COLS = ["pair_id", "stratum", "window", "day_gap", "corp_name",
        "news_date", "news_title", "press", "news_keyword", "kw_low_confidence", "news_url",
        "rcept_date", "report_nm", "event_class", "is_amended", "disclosure_excerpt", "dart_url",
        "rcept_no"] + JUDGE_COLS


def stratum_of(row: dict) -> str:
    if row["window"] == "follow":
        return "follow"
    return "direct_same_day" if int(row["day_gap"]) == 0 else "direct_near"


def pick(links: list) -> list:
    cells = defaultdict(list)
    for r in links:
        cells[(stratum_of(r), r["corp_name"] == BIG)].append(r)
    rng = random.Random(SEED)
    out = []
    for name, n_big, n_other in PLAN:
        big, other = cells[(name, True)], cells[(name, False)]
        take_other = min(n_other, len(other))
        take_big = min(n_big + (n_other - take_other), len(big))     # 그 외가 모자라면 삼성에서 채운다
        take_other = min(take_other + (n_big - min(n_big, len(big))), len(other))
        for pool, k in ((big, take_big), (other, take_other)):
            pool = sorted(pool, key=lambda r: (r["url"], r["corp_code"], r["rcept_no"]))
            out += [dict(r, stratum=name) for r in rng.sample(pool, k)]
    return out


def enrich(rows: list) -> list:
    """기사 제목·매체와 공시 원문 앞부분·DART 링크를 DB에서 붙인다."""
    con = sqlite3.connect(DB_PATH)
    result = []
    for i, r in enumerate(rows, 1):
        news = con.execute("SELECT title, press FROM news WHERE url = ? AND dup_of IS NULL",
                           (r["url"],)).fetchone()
        disc = con.execute(
            "SELECT d.url, (SELECT text FROM disclosure_documents x WHERE x.rcept_no = d.rcept_no AND x.seq = 1) "
            "FROM disclosures d WHERE d.rcept_no = ?", (r["rcept_no"],)).fetchone()
        if not news or not disc:
            sys.exit(f"DB에서 찾지 못함: {r['url'][:80]} / {r['rcept_no']}\n"
                     "links 파일과 DB가 같은 빌드인지 확인한다 (python db/build_db.py 후 매칭을 다시 실행).")
        text = " ".join((disc[1] or "(원문 없음)").split())
        result.append({
            "pair_id": f"M{i:02d}", "stratum": STRATUM_KO[r["stratum"]], "window": r["window"],
            "day_gap": r["day_gap"], "corp_name": r["corp_name"],
            "news_date": r["published_date"], "news_title": news[0], "press": news[1] or "",
            "news_keyword": r["news_keyword"], "kw_low_confidence": r["kw_low_confidence"],
            "news_url": r["url"],
            "rcept_date": r["rcept_date"], "report_nm": r["report_nm"], "event_class": r["event_class"],
            "is_amended": r["is_amended"], "disclosure_excerpt": text[:EXCERPT_CHARS],
            "dart_url": disc[0], "rcept_no": r["rcept_no"],
            **{c: "" for c in JUDGE_COLS},
        })
    con.close()
    return result


def has_judgments() -> bool:
    if not OUT.exists():
        return False
    with OUT.open(encoding="utf-8-sig", newline="") as f:
        return any(any((r.get(c) or "").strip() for c in JUDGE_COLS) for r in csv.DictReader(f))


def summary() -> str:
    """층 × 기업 × 판정 집계. label_final 이 비어 있으면 judge_claude 를 쓴다."""
    with OUT.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    n_final = sum(1 for r in rows if r["label_final"].strip())
    source = "label_final" if n_final == len(rows) else ("judge_claude" if n_final == 0 else None)
    if source is None:
        return f"label_final 이 {n_final}/{len(rows)}개만 채워져 있다. 다 채운 뒤 집계한다."
    lines = [f"판정 출처: {source} ({len(rows)}쌍)", "층 | 기업 | n | " + " | ".join(LABELS)]
    for name, _, _ in PLAN:
        ko = STRATUM_KO[name]
        for label, cond in (("삼성", lambda r: r["corp_name"] == BIG), ("그 외", lambda r: r["corp_name"] != BIG),
                            ("계", lambda r: True)):
            sub = [r for r in rows if r["stratum"] == ko and cond(r)]
            c = Counter(r[source] for r in sub)
            lines.append(f"{ko} | {label} | {len(sub)} | " + " | ".join(str(c[x]) for x in LABELS))
    return "\n".join(lines)


def main() -> None:
    if "--summary" in sys.argv:
        print(summary())
        return
    if has_judgments() and "--force" not in sys.argv:
        sys.exit(f"{OUT.relative_to(ROOT)} 에 판정이 적혀 있어 덮어쓰지 않는다. 새로 뽑으려면 --force.")
    if not LINKS.exists():
        sys.exit(f"매칭 결과가 없다: {LINKS.relative_to(ROOT)}. 먼저 python analysis/match_news_disclosure.py")
    with LINKS.open(encoding="utf-8-sig", newline="") as f:
        links = list(csv.DictReader(f))
    pop = Counter((stratum_of(r), r["corp_name"] == BIG) for r in links)
    rows = enrich(pick(links))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    got = Counter((r["stratum"], r["corp_name"] == BIG) for r in rows)
    print(f"연결 {len(links):,}쌍 → 표본 {len(rows)}쌍 (시드 {SEED})")
    print("층 | 전체(삼성/그 외) | 표본(삼성/그 외)")
    for name, _, _ in PLAN:
        ko = STRATUM_KO[name]
        print(f"{ko} | {pop[(name, True)]:,} / {pop[(name, False)]:,} | {got[(ko, True)]} / {got[(ko, False)]}")
    print(f"저장: {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
