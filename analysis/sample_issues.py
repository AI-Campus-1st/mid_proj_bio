"""이슈 추출(T2) 검수 표본 추출과 집계 (AI_EVALUATION 9절).

검수 대상: data/processed/issues_llm.csv (issue-v1, 4,727건)의 이슈 이름·이슈 유형, 그리고
data/processed/issue_groups.csv (issue-group-v1)가 그 이름을 묶은 대표 이름(issue_group).

층 4개와 표본 수 (근거)
  묶음 기사 5건 이상 × 본문 있음 10 / × 제목만 10 / 묶음 기사 5건 미만 × 본문 있음 5 / × 제목만 5 = 30건
  - 묶음 크기로 나눈 이유: 화면(S1 이슈 목록, 부상 이슈)에 이름이 보이는 것은 기사가 여럿 모인 묶음이다.
    여기서 이름이 틀리거나 다른 사건이 잘못 합쳐지면 화면에 바로 나온다. 그래서 5건 이상 묶음에 더 뽑는다.
    5건은 부상 이슈 최소 기사 수로 추천한 값과 같다 (hanju.md 2026-11-18).
  - 본문·제목으로 나눈 이유: LLM 입력이 달라 오류 양상이 다를 수 있다 (제목만 있는 기사 약 74%).
  - 30건: 판정이 사람 몫이고 남은 시간이 짧아 처음 60건에서 절반으로 줄였다 (2026-11-18). 층마다 비율이 달라
    전체 수치는 층 크기로 가중한다(summary()). 층 하나에 5~10건이라 수치는 경향으로만 본다.
  - 이전 표본(data/eval/issue_review_sample.csv, 이슈 유형별 6건)은 뽑은 코드가 없어 다시 만들 수 없고,
    LLM 결과를 보며 판정해 이 표본으로 대신한다.

판정 칸 (사람이 채운다. 비워 둔 칸은 집계에서 뺀다)
  judge_issue : 정확 / 부분 / 오류 — 이슈 이름이 기사의 핵심 사건을 가리키는가
  judge_type  : 정확 / 오류        — 이슈 유형(8종)이 맞는가
  judge_group : 정확 / 오류        — 대표 이름(issue_group)이 원래 이름과 같은 사건인가 (원래 이름과 같으면 정확)
  판정 기준은 AI_EVALUATION 9-2절.

실행
  python analysis/sample_issues.py --draw      # 표본 추출 → data/eval/issue_sample.csv
  python analysis/sample_issues.py --summary   # 판정 칸을 채운 뒤 정확도 집계
"""
import argparse
import csv
import random
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "collect"))
sys.path.insert(0, str(ROOT / "analysis"))
from config import DB_PATH  # noqa: E402
from issue_prompt import BODY_CHARS  # noqa: E402
from sample_sentiment import QUERY  # noqa: E402

SEED = 20261118
BIG = 5   # 묶음 기사 수 기준
# 2026-11-18: 판정 시간이 부족해 60건(20/20/10/10)에서 절반으로 줄였다. 묶음 5건 이상에 두 배를 주는 비율은 유지
ALLOC = {"묶음 5건 이상·본문": 10, "묶음 5건 이상·제목": 10, "묶음 5건 미만·본문": 5, "묶음 5건 미만·제목": 5}
ISSUES_PATH = ROOT / "data" / "processed" / "issues_llm.csv"
GROUPS_PATH = ROOT / "data" / "processed" / "issue_groups.csv"
OUT = ROOT / "data" / "eval" / "issue_sample.csv"
COLS = ["review_id", "stratum", "url", "lang", "title", "body_head", "issue", "issue_type", "keywords",
        "issue_group", "group_size", "judge_issue", "judge_type", "judge_group", "note", "reviewer"]
LABELS = {"judge_issue": ("정확", "부분", "오류"), "judge_type": ("정확", "오류"), "judge_group": ("정확", "오류")}


def population() -> dict:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    news = {r["url"]: dict(r) for r in con.execute(QUERY)}
    con.close()
    with GROUPS_PATH.open(encoding="utf-8-sig", newline="") as f:
        group = {r["issue_norm"]: r["issue_group"] for r in csv.DictReader(f)}
    with ISSUES_PATH.open(encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["issue"] and r["url"] in news]
    for r in rows:
        r["issue_group"] = group.get(r["issue_norm"], r["issue"])
    size = Counter(r["issue_group"] for r in rows)
    strata = {k: [] for k in ALLOC}
    for r in rows:
        n = news[r["url"]]
        body = (n["body"] or "").strip()
        name = f"묶음 5건 {'이상' if size[r['issue_group']] >= BIG else '미만'}·{'본문' if body else '제목'}"
        strata[name].append({
            "url": r["url"], "lang": n["lang"], "title": n["title"],
            "body_head": body[:BODY_CHARS],     # LLM 에 넣은 것과 같은 범위
            "issue": r["issue"], "issue_type": r["issue_type"], "keywords": r["keywords"],
            "issue_group": r["issue_group"], "group_size": size[r["issue_group"]]})
    return strata


def draw() -> None:
    if OUT.exists():
        sys.exit(f"{OUT.relative_to(ROOT)} 이 이미 있습니다. 판정을 덮어쓰지 않도록 멈춥니다 (지운 뒤 다시 실행).")
    strata = population()
    rng = random.Random(SEED)
    rows = []
    for name, n in ALLOC.items():
        for r in rng.sample(sorted(strata[name], key=lambda x: x["url"]), n):
            rows.append({"stratum": name, **r, "judge_issue": "", "judge_type": "", "judge_group": "",
                         "note": "", "reviewer": ""})
    rng.shuffle(rows)   # 층 순서대로 읽으면 묶음 크기를 미리 알게 되므로 섞는다
    for i, r in enumerate(rows, 1):
        r["review_id"] = f"I{i:02d}"
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
    total = sum(size.values())
    with OUT.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    lines = []
    for col, labels in LABELS.items():
        judged = [r for r in rows if r[col].strip()]
        bad = [r for r in judged if r[col].strip() not in labels]
        if bad:
            lines.append(f"[{col}] 허용되지 않은 값 {len(bad)}건: {sorted({r[col] for r in bad})} — 허용 {labels}")
            continue
        if not judged:
            lines.append(f"[{col}] 판정 없음")
            continue
        lines.append(f"[{col}] 판정 {len(judged)}/{len(rows)}건")
        weighted = 0.0
        for name in ALLOC:
            sub = [r for r in judged if r["stratum"] == name]
            if not sub:
                continue
            cnt = Counter(r[col] for r in sub)
            ok = cnt["정확"] / len(sub)
            weighted += size[name] / total * ok
            lines.append(f"  {name}: " + " · ".join(f"{k} {cnt[k]}" for k in labels) + f" (정확 {ok:.0%})")
        lines.append(f"  정확 비율 (층 크기 가중): {weighted:.1%}"
                     + (" — 판정하지 않은 층이 있어 과소 추정" if len({r['stratum'] for r in judged}) < len(ALLOC) else ""))
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
