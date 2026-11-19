"""영어 제목 번역(T4) 품질 검수 표본 추출과 집계 (AI_EVALUATION 10절).

검수 대상: data/processed/title_ko.csv (translate-v3, 797건)의 번역 제목(title_ko).

층 3개와 표본 수: 숫자 포함 10 / 표기 목록 이름 포함(숫자 없음) 10 / 둘 다 없음 10 = 30건.
층 나누는 기준과 이유는 AI_EVALUATION 10-1절. 전체 수치는 층 크기로 가중한다(summary()).

판정 칸 (사람이 채운다. 비워 둔 칸은 집계에서 뺀다)
  judge_meaning : 정확 / 부분 / 오류
  judge_number  : 정확 / 오류 / 해당없음
  judge_name    : 정확 / 오류 / 해당없음
  판정 기준은 AI_EVALUATION 10-2절.

실행
  python analysis/sample_translations.py --draw      # 표본 추출 → data/eval/translation_sample.csv
  python analysis/sample_translations.py --summary   # 판정 칸을 채운 뒤 정확도 집계
"""
import argparse
import csv
import random
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "analysis"))
from translate_prompt import NAME_KO  # noqa: E402

SEED = 20261119
ALLOC = {"숫자 포함": 10, "표기 목록 이름 포함": 10, "숫자·목록 이름 없음": 10}
SRC = ROOT / "data" / "processed" / "title_ko.csv"
OUT = ROOT / "data" / "eval" / "translation_sample.csv"
COLS = ["review_id", "stratum", "url", "title", "title_ko", "glossary", "judge_meaning", "judge_number",
        "judge_name", "note", "reviewer"]
LABELS = {"judge_meaning": ("정확", "부분", "오류"), "judge_number": ("정확", "오류", "해당없음"),
          "judge_name": ("정확", "오류", "해당없음")}
NA = "해당없음"


def glossary_hits(title: str) -> list:
    low = title.lower()
    return [f"{en} → {ko}" for en, ko in NAME_KO.items() if en.lower() in low]


def stratum(title: str) -> str:
    if re.search(r"\d", title):
        return "숫자 포함"
    return "표기 목록 이름 포함" if glossary_hits(title) else "숫자·목록 이름 없음"


def population() -> dict:
    with SRC.open(encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["title_ko"].strip()]
    strata = {k: [] for k in ALLOC}
    for r in rows:
        strata[stratum(r["title"])].append({"url": r["url"], "title": r["title"], "title_ko": r["title_ko"],
                                            "glossary": "; ".join(glossary_hits(r["title"]))})
    return strata


def draw() -> None:
    if OUT.exists():
        sys.exit(f"{OUT.relative_to(ROOT)} 이 이미 있습니다. 판정을 덮어쓰지 않도록 멈춥니다 (지운 뒤 다시 실행).")
    strata = population()
    rng = random.Random(SEED)
    rows = []
    for name, n in ALLOC.items():
        for r in rng.sample(sorted(strata[name], key=lambda x: x["url"]), n):
            # 숫자가 없는 층은 숫자 판정이 필요 없다
            rows.append({"stratum": name, **r, "judge_meaning": "",
                         "judge_number": "" if name == "숫자 포함" else NA,
                         "judge_name": "", "note": "", "reviewer": ""})
    rng.shuffle(rows)
    for i, r in enumerate(rows, 1):
        r["review_id"] = f"T{i:02d}"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    print(f"표본 {len(rows)}건 → {OUT.relative_to(ROOT)}")
    for name in ALLOC:
        print(f"  {name}: 모집단 {len(strata[name]):,} / 표본 {ALLOC[name]}")


def summary() -> str:
    size = {k: len(v) for k, v in population().items()}
    with OUT.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    lines = []
    for col, labels in LABELS.items():
        filled = [r for r in rows if r[col].strip()]
        bad = [r for r in filled if r[col].strip() not in labels]
        if bad:
            lines.append(f"[{col}] 허용되지 않은 값 {len(bad)}건: {sorted({r[col] for r in bad})} — 허용 {labels}")
            continue
        judged = [r for r in filled if r[col].strip() != NA]
        if not judged:
            lines.append(f"[{col}] 판정 없음")
            continue
        lines.append(f"[{col}] 판정 {len(judged)}건 (해당없음 {len(filled) - len(judged)}건 제외)")
        shown = [k for k in labels if k != NA]
        weighted, weight = 0.0, 0
        for name in ALLOC:
            sub = [r for r in judged if r["stratum"] == name]
            if not sub:
                continue
            cnt = Counter(r[col] for r in sub)
            ok = cnt["정확"] / len(sub)
            weighted += size[name] * ok
            weight += size[name]
            lines.append(f"  {name}: " + " · ".join(f"{k} {cnt[k]}" for k in shown) + f" (정확 {ok:.0%})")
        # 해당없음뿐인 층은 그 판정의 모집단이 아니므로 가중에서 뺀다
        lines.append(f"  정확 비율 (판정한 층의 크기 가중): {weighted / weight:.1%}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--draw", action="store_true")
    g.add_argument("--summary", action="store_true")
    a = ap.parse_args()
    if a.draw:
        draw()
    else:
        print(summary())


if __name__ == "__main__":
    main()
