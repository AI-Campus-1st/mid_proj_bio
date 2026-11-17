"""공시 RAG 평가 — 질문 20개로 검색 정확도와 거절 정확도를 잰다.

입력: data/eval/rag_questions.csv
      expect = answer(답이 있는 질문) / refuse(거절해야 하는 질문)
      gold_rcept_no = 정답 공시 접수번호 (';' 로 여러 개. 하나라도 맞으면 정답)
      answer_keys   = 답에 들어 있어야 하는 값 (';' 로 여러 개. 쉼표·공백은 무시하고 비교)
출력: data/eval/rag_eval_result.csv (질문별 결과), data/eval/rag_eval_result.md (집계)
지표: 검색 정확도  = 답이 있는 질문 중, LLM 에 넘긴 청크 안에 정답 공시가 있는 비율
      거절 정확도  = 거절해야 하는 질문 중 거절한 비율 / 답이 있는 질문 중 잘못 거절한 비율
      근거 일치율  = 답한 질문 중, 인용한 공시에 정답 공시가 있는 비율
      핵심 값 일치 = 답한 질문 중, 답에 answer_keys 가 모두 들어 있는 비율 (자동 비교. 환각 여부는 사람이 확인)

실행 (질문마다 임베딩 1회 + 답변 LLM 1회, API 비용이 든다)
  python rag/eval_rag.py
  python rag/eval_rag.py --rescore   # 호출 없이, 저장된 결과로 집계만 다시 만든다
"""
import argparse
import csv
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "rag"))
import qa  # noqa: E402

QUESTIONS = ROOT / "data" / "eval" / "rag_questions.csv"
OUT_CSV = ROOT / "data" / "eval" / "rag_eval_result.csv"
OUT_MD = ROOT / "data" / "eval" / "rag_eval_result.md"
KST = timezone(timedelta(hours=9))
COLS = ["qid", "type", "expect", "question", "refused", "stage", "correct_refusal", "top_similarity",
        "gold_rank", "retrieval_hit", "citation_hit", "keys_hit", "answer", "refusal_reason",
        "cited_rcept_no", "retrieved_rcept_no", "gold_rcept_no", "answer_keys"]


def norm(text: str) -> str:
    """비교용 정규화: '2031년 12월 31일' → '2031-12-31', 쉼표·공백 제거, 소문자."""
    text = re.sub(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일",
                  lambda m: f"{m[1]}-{int(m[2]):02d}-{int(m[3]):02d}", text)
    return re.sub(r"[\s,]", "", text).lower()


def keys_hit(row: dict, answer: str) -> int:
    keys = [k for k in row["answer_keys"].split(";") if k]
    return int(all(norm(k) in norm(answer) for k in keys))


def evaluate(row: dict) -> dict:
    r = qa.ask(row["question"])
    gold = [g for g in row["gold_rcept_no"].split(";") if g]
    retrieved = [c["metadata"]["rcept_no"] for c in r.get("retrieved", [])]
    cited = [c["rcept_no"] for c in r.get("citations", [])]
    rank = next((i + 1 for i, no in enumerate(retrieved) if no in gold), "")
    answered = not r["refused"]
    out = {**row, "refused": int(r["refused"]), "stage": r["stage"],
           "correct_refusal": int(r["refused"] == (row["expect"] == "refuse")),
           "top_similarity": r.get("top_similarity", ""),
           "gold_rank": rank, "retrieval_hit": "", "citation_hit": "", "keys_hit": "",
           "answer": r["answer"] if answered else "", "refusal_reason": r.get("refusal_reason") or "",
           "cited_rcept_no": ";".join(cited), "retrieved_rcept_no": ";".join(retrieved)}
    if row["expect"] == "answer":
        out["retrieval_hit"] = int(bool(rank)) if retrieved else 0
        if answered:
            out["citation_hit"] = int(any(c in gold for c in cited))
            out["keys_hit"] = keys_hit(row, r["answer"])
    return out


def pct(n: int, d: int) -> str:
    return f"{n}/{d} ({n / d:.1%})" if d else "0/0"


def report(rows: list) -> str:
    ans = [r for r in rows if r["expect"] == "answer"]
    ref = [r for r in rows if r["expect"] == "refuse"]
    answered = [r for r in ans if not r["refused"]]
    col = qa_collection_info()
    lines = [
        "# 공시 RAG 평가 결과",
        "",
        f"- 집계 시각: {datetime.now(KST).isoformat(timespec='seconds')}",
        f"- 색인: 청크 {col['count']:,}개, 임베딩 `{col['embed_model']}`, 청크 {col['chunk_size']}자 / "
        f"겹침 {col['chunk_overlap']}자",
        f"- 검색: 사건성 공시 검색에서 {qa.N_EVENT}개 + 전체 검색에서 {qa.N_GENERAL}개 "
        f"(검색마다 후보 {qa.N_CANDIDATES}개, 공시당 {qa.MAX_PER_DOC}개까지), 유사도 임계값 {qa.MIN_SIMILARITY}",
        f"- 답변 모델: `{qa.ANSWER_MODEL}` (effort {qa.EFFORT})",
        f"- 질문: {len(rows)}개 (답 있음 {len(ans)}, 거절해야 함 {len(ref)})",
        "",
        "## 집계",
        "",
        "| 지표 | 값 |",
        "|---|---|",
        f"| 검색 정확도 (넘긴 청크 {qa.N_FINAL}개 안에 정답 공시) | {pct(sum(r['retrieval_hit'] == 1 for r in ans), len(ans))} |",
        f"| 거절 정확도 (거절해야 하는 질문을 거절) | {pct(sum(r['refused'] for r in ref), len(ref))} |",
        f"| 잘못된 거절 (답이 있는 질문을 거절) | {pct(sum(r['refused'] for r in ans), len(ans))} |",
        f"| 근거 일치율 (답한 질문 중 정답 공시를 인용) | {pct(sum(r['citation_hit'] == 1 for r in answered), len(answered))} |",
        f"| 핵심 값 일치 (답한 질문 중 answer_keys 포함, 자동 비교) | {pct(sum(r['keys_hit'] == 1 for r in answered), len(answered))} |",
        "",
        "## 질문별 결과",
        "",
        "| qid | 유형 | 기대 | 결과 | 단계 | 최상위 유사도 | 정답 순위 | 인용 일치 | 값 일치 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(f"| {r['qid']} | {r['type']} | {'답변' if r['expect'] == 'answer' else '거절'} | "
                     f"{'거절' if r['refused'] else '답변'} | {r['stage']} | {r['top_similarity']} | "
                     f"{r['gold_rank']} | {r['citation_hit']} | {r['keys_hit']} |")
    wrong = [r for r in rows if not r["correct_refusal"] or r["citation_hit"] == 0 or r["keys_hit"] == 0
             or r["retrieval_hit"] == 0]
    lines += ["", "## 확인이 필요한 질문", ""]
    if not wrong:
        lines.append("없음")
    for r in wrong:
        lines += [f"- **{r['qid']}** {r['question']}",
                  f"  - 결과: {'거절 — ' + r['refusal_reason'] if r['refused'] else r['answer']}",
                  f"  - 정답 공시 {r['gold_rcept_no'] or '(없음)'} / 검색 {r['retrieved_rcept_no'] or '(없음)'}"]
    return "\n".join(lines) + "\n"


def qa_collection_info() -> dict:
    import chromadb

    col = chromadb.PersistentClient(path=str(qa.CHROMA_DIR)).get_collection(qa.COLLECTION)
    return {"count": col.count(), **(col.metadata or {})}


def load_saved() -> list:
    """저장된 질문별 결과를 읽어 값 일치만 다시 계산한다 (API 를 호출하지 않는다)."""
    with OUT_CSV.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in ("refused", "correct_refusal", "retrieval_hit", "citation_hit", "keys_hit"):
            r[k] = int(r[k]) if r[k] != "" else ""
        if r["keys_hit"] != "":
            r["keys_hit"] = keys_hit(r, r["answer"])
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description="공시 RAG 평가")
    ap.add_argument("--rescore", action="store_true",
                    help="API 를 호출하지 않고 저장된 결과(rag_eval_result.csv)로 집계만 다시 만든다")
    args = ap.parse_args()
    if args.rescore:
        rows = load_saved()
    else:
        with QUESTIONS.open(encoding="utf-8-sig", newline="") as f:
            questions = list(csv.DictReader(f))
        rows = []
        for q in questions:
            rows.append(evaluate(q))
            r = rows[-1]
            print(f"{r['qid']} {'거절' if r['refused'] else '답변'}({r['stage']}) 유사도 "
                  f"{r['top_similarity']} 정답순위 {r['gold_rank']}")
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    OUT_MD.write_text(report(rows), encoding="utf-8")
    print(f"저장: {OUT_CSV.relative_to(ROOT)}, {OUT_MD.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
