"""감성(영향) 분류 표본 검수 결과 집계.

입력
  data/eval/sentiment_sample.csv  — 검수자가 annotator_a, annotator_b, label_final 을 채운 표본
  data/processed/sentiment_llm.csv — LLM 결과 (url, label, reason, confidence, input_basis, model, prompt_version, labeled_at)
출력
  data/eval/sentiment_eval_result.md — 검수자 간 일치도, LLM 정확도, 라벨별 정밀도·재현율·F1,
                                       혼동행렬, 입력 유형·언어별 정확도, 오분류 목록
  docs/04_ai/AI_EVALUATION.md 4절과 리포트에 이 결과를 옮긴다.
실행: python analysis/eval_sentiment.py
"""
import csv
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "analysis"))
from sentiment_prompt import LABELS  # noqa: E402

SAMPLE = ROOT / "data" / "eval" / "sentiment_sample.csv"
LLM = ROOT / "data" / "processed" / "sentiment_llm.csv"
OUT = ROOT / "data" / "eval" / "sentiment_eval_result.md"
KST = timezone(timedelta(hours=9))


def read(path: Path) -> list:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def kappa(a: list, b: list) -> float:
    """Cohen's kappa (두 검수자 간 우연 일치를 뺀 일치도)."""
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in LABELS) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def prf(gold: list, pred: list) -> dict:
    out = {}
    for k in LABELS:
        tp = sum(g == k and p == k for g, p in zip(gold, pred))
        fp = sum(g != k and p == k for g, p in zip(gold, pred))
        fn = sum(g == k and p != k for g, p in zip(gold, pred))
        pr = tp / (tp + fp) if tp + fp else 0.0
        rc = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * pr * rc / (pr + rc) if pr + rc else 0.0
        out[k] = (pr, rc, f1, tp + fn)
    return out


def pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def main():
    if not SAMPLE.exists():
        raise SystemExit("표본 파일이 없습니다. 먼저 python analysis/sample_sentiment.py 를 실행하세요.")
    sample = read(SAMPLE)
    bad = [r["sample_id"] for r in sample
           if r["label_final"] and r["label_final"] not in LABELS]
    if bad:
        raise SystemExit(f"label_final 값이 기회/위험/중립이 아닙니다: {bad[:10]}")
    done = [r for r in sample if r["label_final"] in LABELS]
    lines = [f"# 감성(영향) 분류 표본 검수 결과",
             "", f"- 생성: {datetime.now(KST):%Y-%m-%d %H:%M} (KST)",
             f"- 표본 {len(sample)}건 중 정답(label_final) 확정 {len(done)}건", ""]

    # 1. 검수자 간 일치도
    both = [r for r in sample if r["annotator_a"] in LABELS and r["annotator_b"] in LABELS]
    lines += ["## 1. 검수자 간 일치도", ""]
    if both:
        a, b = [r["annotator_a"] for r in both], [r["annotator_b"] for r in both]
        agree = sum(x == y for x, y in zip(a, b)) / len(both)
        lines += [f"- 두 검수자가 모두 라벨링한 {len(both)}건: 일치율 {pct(agree)}, Cohen's kappa {kappa(a, b):.3f}", ""]
    else:
        lines += ["- 두 검수자 라벨이 아직 없습니다.", ""]

    # 2. LLM 정확도
    lines += ["## 2. LLM 정확도", ""]
    llm = {r["url"]: r for r in read(LLM)} if LLM.exists() else {}
    pairs = [(r, llm[r["url"]]) for r in done if r["url"] in llm and llm[r["url"]]["label"] in LABELS]
    missing = len(done) - len(pairs)
    if not pairs:
        lines += [f"- LLM 결과가 없습니다 ({LLM.relative_to(ROOT)}). LLM 라벨링 후 다시 실행하세요.", ""]
    else:
        gold = [r["label_final"] for r, _ in pairs]
        pred = [p["label"] for _, p in pairs]
        acc = sum(g == p for g, p in zip(gold, pred)) / len(pairs)
        versions = sorted({p.get("prompt_version", "") for _, p in pairs})
        models = sorted({p.get("model", "") for _, p in pairs})
        lines += [f"- 비교 {len(pairs)}건 (LLM 결과 없음 {missing}건 제외) · 모델 {', '.join(models)} · 프롬프트 {', '.join(versions)}",
                  f"- **정확도 {pct(acc)}**", "",
                  "| 라벨 | 정밀도 | 재현율 | F1 | 정답 건수 |", "|---|---|---|---|---|"]
        for k, (pr, rc, f1, sup) in prf(gold, pred).items():
            lines.append(f"| {k} | {pct(pr)} | {pct(rc)} | {f1:.3f} | {sup} |")
        lines += ["", "**혼동행렬** (행 = 정답, 열 = LLM)", "",
                  "| 정답 \\ LLM | " + " | ".join(LABELS) + " |", "|---" * (len(LABELS) + 1) + "|"]
        cm = Counter(zip(gold, pred))
        for g in LABELS:
            lines.append(f"| {g} | " + " | ".join(str(cm[(g, p)]) for p in LABELS) + " |")

        # 3. 유형별 정확도
        lines += ["", "## 3. 유형별 정확도", ""]
        for title, key in (("입력 유형", "stratum"), ("판단 근거", "input_basis"),
                           ("대표 키워드", "keyword"), ("키워드 근거", "kw_basis")):
            grp = defaultdict(list)
            for r, p in pairs:
                grp[r[key]].append(r["label_final"] == p["label"])
            lines += [f"**{title}**", "", "| 구분 | 건수 | 정확도 |", "|---|---|---|"]
            for g in sorted(grp):
                lines.append(f"| {g} | {len(grp[g])} | {pct(sum(grp[g]) / len(grp[g]))} |")
            lines.append("")
        grp = defaultdict(list)
        for r, p in pairs:
            grp[p.get("confidence", "")].append(r["label_final"] == p["label"])
        lines += ["**LLM 확신도**", "", "| 확신도 | 건수 | 정확도 |", "|---|---|---|"]
        for g in ("high", "medium", "low"):
            if grp[g]:
                lines.append(f"| {g} | {len(grp[g])} | {pct(sum(grp[g]) / len(grp[g]))} |")

        # 4. 오분류
        wrong = [(r, p) for r, p in pairs if r["label_final"] != p["label"]]
        lines += ["", f"## 4. 오분류 {len(wrong)}건", "",
                  "| ID | 정답 | LLM | 확신도 | 제목 | LLM 이유 | 검수 메모 |", "|---|---|---|---|---|---|---|"]
        for r, p in wrong:
            t = r["title"].replace("|", "/")[:60]
            lines.append(f"| {r['sample_id']} | {r['label_final']} | {p['label']} | {p.get('confidence', '')} "
                         f"| {t} | {p.get('reason', '').replace('|', '/')} | {r['note'].replace('|', '/')} |")

    dist = Counter(r["label_final"] for r in done)
    lines += ["", "## 5. 정답 라벨 분포", ""] + [f"- {k}: {dist[k]}건" for k in LABELS]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"출력: {OUT.relative_to(ROOT)}  (정답 {len(done)}건, LLM 비교 {len(pairs)}건)")


if __name__ == "__main__":
    main()
