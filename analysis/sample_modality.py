"""모달리티 태그 검수 표본 추출과 집계 (T3 검수, AI_EVALUATION 8절).

검수 대상은 화면에 쓰는 7개 태그(항체·ADC·mRNA·세포·유전자치료제·올리고·펩타이드·백신)다. '기타'는 화면에
쓰지 않아 검수하지 않는다 (기타만 붙은 기사는 '태그 없음' 층에 넣는다).

층 4개와 표본 수 (근거)
  본문·태그 있음 25 / 제목·태그 있음 25 / 본문·태그 없음 15 / 제목·태그 없음 15 = 80건
  - 히트맵·추이는 태그가 붙은 기사만 세므로, 잘못 붙은 태그(정밀도)가 화면에 직접 영향을 준다.
    그래서 태그 있음 층에 더 많이 뽑는다.
  - 태그 없음 층은 놓친 태그(재현율)를 어림하려고 뽑는다. 화면 숫자가 실제보다 적게 잡히는 정도를 본다.
  - 본문·제목을 나누는 이유: 입력이 달라 오류 양상이 다를 수 있다 (제목만 있는 기사가 약 74%).
  - 층마다 뽑는 비율이 달라 전체 정확도는 층 크기로 가중해 계산한다 (summary()).
판정자는 LLM 결과를 보지 않고(블라인드) 기사만 읽어 태그를 정한다. 그 뒤 LLM 태그와 비교한다.

실행
  python analysis/sample_modality.py --draw      # 표본 추출 → data/eval/modality_sample.csv
  python analysis/sample_modality.py --summary   # judge 칸을 채운 뒤 정확도 집계
final_tags: 블라인드 판정과 LLM 태그가 다른 쌍만 다시 보고 정한 최종 라벨 (같은 쌍은 비워 두면 judge_tags 를 쓴다).
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
from modality_prompt import BODY_CHARS  # noqa: E402
from sample_sentiment import QUERY  # noqa: E402

SEED = 20261118
TAGS = ["항체", "ADC", "mRNA", "세포·유전자치료제", "올리고", "펩타이드", "백신"]
ALLOC = {"본문·태그 있음": 25, "제목·태그 있음": 25, "본문·태그 없음": 15, "제목·태그 없음": 15}
LLM_PATH = ROOT / "data" / "processed" / "modality_llm.csv"
OUT = ROOT / "data" / "eval" / "modality_sample.csv"
COLS = ["sample_id", "stratum", "url", "input_basis", "title", "body_excerpt", "llm_tags", "llm_evidence",
        "judge_tags", "judge_note", "final_tags", "final_note"]


def shown_tags(modalities: str) -> list:
    return [t for t in TAGS if t in modalities.split("; ")]


def population() -> dict:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    news = {r["url"]: dict(r) for r in con.execute(QUERY)}
    con.close()
    strata = {k: [] for k in ALLOC}
    with LLM_PATH.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["error"] or r["url"] not in news:
                continue
            n = news[r["url"]]
            tags = shown_tags(r["modalities"])
            basis = "본문" if r["input_basis"] == "body" else "제목"
            body = (n["body"] or "").strip()
            strata[f"{basis}·{'태그 있음' if tags else '태그 없음'}"].append({
                "url": r["url"], "input_basis": r["input_basis"], "title": n["title"],
                "body_excerpt": body[:BODY_CHARS],   # LLM 에 넣은 것과 같은 범위
                "llm_tags": "; ".join(tags), "llm_evidence": r["evidence"]})
    return strata


def draw() -> None:
    strata = population()
    rng = random.Random(SEED)
    rows = []
    for name, n in ALLOC.items():
        for r in rng.sample(sorted(strata[name], key=lambda x: x["url"]), n):
            rows.append({"stratum": name, **r, "judge_tags": "", "judge_note": "", "final_tags": "", "final_note": ""})
    rng.shuffle(rows)   # 층 순서대로 읽으면 '태그 없음'을 미리 알게 되므로 섞는다
    for i, r in enumerate(rows, 1):
        r["sample_id"] = f"T{i:02d}"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    print(f"표본 {len(rows)}건 → {OUT.relative_to(ROOT)}")
    for name in ALLOC:
        print(f"  {name}: 모집단 {len(strata[name]):,} / 표본 {ALLOC[name]}")


def summary() -> str:
    """블라인드 판정(judge_tags)과 최종 라벨(final_tags, 비어 있으면 judge_tags)로 각각 집계한다."""
    out = []
    for col, title in (("judge_tags", "블라인드 판정 기준"), ("final_tags", "최종 라벨 기준 (불일치 쌍 재검토)")):
        out.append(f"## {title}\n" + _summary(col))
    return "\n\n".join(out)


def _summary(col: str) -> str:
    strata_size = {k: len(v) for k, v in population().items()}
    with OUT.open(encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f)]
    for r in rows:
        r["gold"] = r.get(col, "").strip() or r["judge_tags"]
    judged = [r for r in rows if r["gold"].strip()]
    if not judged:
        return "judge_tags 가 비어 있습니다. 판정 후 다시 실행합니다."
    norm = lambda s: set() if s.strip() in ("", "없음") else {t.strip() for t in s.split(";") if t.strip()}  # noqa: E731
    lines = [f"판정 {len(judged)}/{len(rows)}건"]
    # 기사 단위: 7개 태그 집합이 완전히 같으면 정확
    exact = {}
    for name in ALLOC:
        sub = [r for r in judged if r["stratum"] == name]
        ok = sum(norm(r["llm_tags"]) == norm(r["gold"]) for r in sub)
        exact[name] = (ok, len(sub))
        lines.append(f"  {name}: 태그 집합 일치 {ok}/{len(sub)}")
    total = sum(strata_size.values())
    w = sum(strata_size[k] / total * (ok / n) for k, (ok, n) in exact.items() if n)
    lines.append(f"기사 단위 일치율 (층 크기 가중): {w:.1%}")
    # 태그 단위: LLM 태그 중 맞은 것(정밀도), 판정 태그 중 LLM 이 붙인 것(재현율) — 층 가중
    tp = fp = fn = 0.0
    per = {t: Counter() for t in TAGS}
    for r in judged:
        wt = strata_size[r["stratum"]] / ALLOC[r["stratum"]]
        llm, gold = norm(r["llm_tags"]), norm(r["gold"])
        tp += wt * len(llm & gold)
        fp += wt * len(llm - gold)
        fn += wt * len(gold - llm)
        for t in TAGS:
            per[t]["tp"] += t in llm and t in gold
            per[t]["fp"] += t in llm and t not in gold
            per[t]["fn"] += t in gold and t not in llm
    lines.append(f"태그 정밀도 (가중): {tp / (tp + fp):.1%} · 재현율 (가중): {tp / (tp + fn):.1%}")
    lines.append("태그별 (표본 건수, 가중 없음): 맞음 / 잘못 붙임 / 놓침")
    lines += [f"  {t}: {c['tp']} / {c['fp']} / {c['fn']}" for t, c in per.items()]
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
