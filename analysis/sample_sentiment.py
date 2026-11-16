"""감성(영향) 분류 검수용 표본 추출 — 층화 무작위 표본 (LLM 결과와 무관하게 먼저 뽑는다).

대상: 대표 CDMO 키워드가 있고 중복이 아닌 기사 (docs/04_ai/AI_CLASSIFICATION.md 2-4절과 같은 범위)
층:   입력 유형 3개(본문 / 제목·한국어 / 제목·영어) × 대표 키워드 6개 = 18개 층
배분: 층마다 최소 MIN_PER 건을 먼저 주고, 나머지는 층 크기에 비례해 나눈다 (작은 층도 정확도를 볼 수 있게)
출력: data/eval/sentiment_sample.csv (UTF-8 BOM, 엑셀에서 바로 열림)
      검수자는 annotator_a, annotator_b 에 각자 라벨(기회/위험/중립)을 적고,
      둘이 다르면 합의해 label_final 을 채운다. LLM 결과는 이 파일에 넣지 않는다 (블라인드).
실행: python analysis/sample_sentiment.py [표본 수, 기본 180] [--force]
      검수 라벨이 이미 적힌 파일은 덮어쓰지 않는다. 새로 뽑으려면 --force (기존 라벨 삭제).
"""
import csv
import random
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "collect"))
sys.path.insert(0, str(ROOT / "analysis"))
from config import DB_PATH  # noqa: E402
from sentiment_prompt import BODY_CHARS, PROMPT_VERSION, input_basis  # noqa: E402

OUT = ROOT / "data" / "eval" / "sentiment_sample.csv"
SEED = 20261116  # 고정 시드 — 다시 실행해도 같은 표본이 나온다 (DB가 같을 때)
MIN_PER = 5

QUERY = """
SELECT n.url, n.title, n.body, n.lang, n.origin, n.published_date, n.press,
       k.keyword, n.cdmo_kw_basis
FROM news n
JOIN news_cdmo_keywords k ON k.news_id = n.news_id AND k.is_primary = 1
WHERE n.dup_of IS NULL
ORDER BY n.url
"""


def group(row) -> str:
    if (row["body"] or "").strip():
        return "본문"
    return "제목·영어" if row["lang"] == "en" else "제목·한국어"


def allocate(sizes: dict, n: int) -> dict:
    """층별 표본 수: 최소 MIN_PER(층 크기 한도) + 나머지를 크기 비례로. 반올림 오차는 큰 층부터 보정."""
    alloc = {s: min(MIN_PER, size) for s, size in sizes.items()}
    rest = n - sum(alloc.values())
    if rest < 0:
        raise SystemExit(f"표본 수 {n} 이 최소 배분 {sum(alloc.values())} 보다 작습니다.")
    room = {s: sizes[s] - alloc[s] for s in sizes}
    total = sum(room.values())
    extra = {s: int(rest * room[s] / total) if total else 0 for s in sizes}
    for s in sorted(sizes, key=lambda s: -room[s]):
        if sum(extra.values()) >= rest:
            break
        if extra[s] < room[s]:
            extra[s] += 1
    return {s: alloc[s] + min(extra[s], room[s]) for s in sizes}


def labeled_count() -> int:
    """이미 검수 라벨이 적힌 행 수. 라벨이 있으면 덮어쓰지 않는다."""
    if not OUT.exists():
        return 0
    with OUT.open(encoding="utf-8-sig", newline="") as f:
        return sum(any((v or "").strip() for k, v in r.items()
                       if k and (k.startswith("annotator_") or k == "label_final"))
                   for r in csv.DictReader(f))


def main():
    args = [a for a in sys.argv[1:] if a != "--force"]
    n = int(args[0]) if args else 180
    if labeled_count() and "--force" not in sys.argv:
        raise SystemExit(f"{OUT.relative_to(ROOT)} 에 검수 라벨이 {labeled_count()}건 있어 덮어쓰지 않습니다. "
                         "새로 뽑으려면 --force 를 붙이세요 (기존 라벨은 사라집니다).")
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(QUERY).fetchall()
    con.close()
    strata = defaultdict(list)
    for r in rows:
        strata[(group(r), r["keyword"])].append(r)
    plan = allocate({s: len(v) for s, v in strata.items()}, n)

    rng = random.Random(SEED)
    picked = []
    for s in sorted(strata):
        for r in rng.sample(strata[s], plan[s]):
            picked.append((s, r))
    rng.shuffle(picked)  # 검수 순서가 층별로 몰리지 않게 섞는다

    OUT.parent.mkdir(parents=True, exist_ok=True)
    cols = ["sample_id", "url", "stratum", "keyword", "lang", "origin", "published_date", "press",
            "input_basis", "kw_basis", "title", "body_excerpt",
            "annotator_a", "annotator_b", "label_final", "note"]
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for i, ((g, kw), r) in enumerate(picked, 1):
            body = (r["body"] or "").strip()
            w.writerow({
                "sample_id": f"S{i:03d}", "url": r["url"], "stratum": g, "keyword": kw,
                "lang": r["lang"], "origin": r["origin"], "published_date": r["published_date"],
                "press": r["press"], "input_basis": input_basis(body), "kw_basis": r["cdmo_kw_basis"],
                "title": r["title"], "body_excerpt": body[:BODY_CHARS],
                "annotator_a": "", "annotator_b": "", "label_final": "", "note": ""})

    print(f"대상 {len(rows)}건 → 표본 {len(picked)}건 (seed={SEED}, prompt={PROMPT_VERSION})")
    print(f"출력: {OUT.relative_to(ROOT)}")
    print("층 | 모집단 | 표본")
    for s in sorted(strata):
        print(f"  {s[0]} / {s[1]} | {len(strata[s])} | {plan[s]}")


if __name__ == "__main__":
    main()
