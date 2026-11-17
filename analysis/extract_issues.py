"""LLM 핵심 이슈·이슈 키워드 추출 (T2) — 기사마다 이슈 이름·유형·키워드를 붙인다.

대상: 감성 분류와 같은 범위 (대표 CDMO 키워드가 있고 중복이 아닌 기사). sample_sentiment.QUERY 를 그대로 쓴다.
방식: analysis/label_sentiment.py 와 같다. Chat Completions API 를 기사마다 한 번씩 동시에 호출하고,
      구조화 출력으로 JSON 형식을 강제한 뒤 parse_response() 로 한 번 더 검증한다.
출력: data/processed/issues_llm.csv (기사 URL 키). 같은 모델·프롬프트 버전으로 성공한 기사는 건너뛴다.
      SAVE_EVERY 건마다 중간 저장하므로, 끊겨도 같은 명령을 다시 실행하면 남은 기사만 처리한다.
      issue_norm 은 이슈 이름의 표기 차이(공백·문장부호)를 없앤 묶음 키다.

실행 (먼저 --dry-run 으로 건수와 예상 비용을 확인한다. 실제 호출은 API 비용이 든다)
  python analysis/extract_issues.py --sample --dry-run   # 감성 검수 표본 180건만, 호출하지 않고 확인
  python analysis/extract_issues.py --sample             # 표본 180건만 추출해 저장
  python analysis/extract_issues.py --all                # 전체 (이미 끝난 기사는 제외)
  python analysis/extract_issues.py --summary            # 저장된 결과의 이슈별 기사 수만 출력 (호출 없음)
API 키: 환경변수 OPENAI_API_KEY, 없으면 .env 의 OPENAI_API_KEY.

한계: 이슈 이름은 기사마다 따로 뽑으므로 같은 사건이 다른 이름으로 나뉠 수 있다
      ("미국 생물보안법" / "생물보안법 통과"). 묶음 정확도는 표본 검수로 확인해야 한다.
"""
import argparse
import csv
import json
import os
import sqlite3
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import openai

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "collect"))
sys.path.insert(0, str(ROOT / "analysis"))
from config import DB_PATH  # noqa: E402
from issue_prompt import (OUTPUT_SCHEMA, PROMPT_VERSION, SYSTEM_PROMPT,  # noqa: E402
                          build_user_prompt, input_basis, normalize_issue, parse_response)
from label_sentiment import KST, PRICE, load_api_key, rel  # noqa: E402
from sample_sentiment import OUT as SAMPLE_PATH  # noqa: E402
from sample_sentiment import QUERY  # noqa: E402

MODEL = "gpt-6-luna"    # 감성 분류와 같은 모델
EFFORT = "low"
MAX_TOKENS = 2048       # 추론(reasoning) 토큰도 여기에 포함된다
WORKERS = 8             # 동시 호출 수
SAVE_EVERY = 200        # 이 건수마다 중간 저장
OUT = Path(os.environ.get("ISSUES_LLM_OUT", ROOT / "data" / "processed" / "issues_llm.csv"))
COLS = ["url", "issue", "issue_norm", "issue_type", "keywords", "confidence", "input_basis",
        "model", "prompt_version", "extracted_at", "error"]


def targets(sample_only: bool, db_path=None) -> list:
    con = sqlite3.connect(db_path or DB_PATH)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(QUERY)]
    con.close()
    if sample_only:
        with SAMPLE_PATH.open(encoding="utf-8-sig", newline="") as f:
            urls = {r["url"] for r in csv.DictReader(f)}
        rows = [r for r in rows if r["url"] in urls]
        if len(rows) != len(urls):
            print(f"주의: 표본 {len(urls)}건 중 {len(rows)}건만 DB에서 찾았습니다 (DB 재빌드로 기사 구성이 바뀌었을 수 있음).")
    return rows


def read_out() -> dict:
    if not OUT.exists():
        return {}
    with OUT.open(encoding="utf-8-sig", newline="") as f:
        return {r["url"]: r for r in csv.DictReader(f)}


def done_urls(model: str) -> set:
    """같은 모델·프롬프트 버전으로 이슈가 이미 붙은 URL."""
    return {u for u, r in read_out().items()
            if r["issue"] and r["prompt_version"] == PROMPT_VERSION and r["model"] == model}


def user_prompt(r: dict) -> str:
    return build_user_prompt(r["title"], r["body"], r["lang"], r["published_date"], r["press"],
                             r.get("keyword"))


def make_params(r: dict, model: str, effort: str) -> dict:
    return {
        "model": model,
        "max_completion_tokens": MAX_TOKENS,
        "reasoning_effort": effort,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt(r)},
        ],
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "issue_extraction", "strict": True, "schema": OUTPUT_SCHEMA}},
    }


def estimate(rows: list, model: str) -> str:
    """대략적인 비용 추정 (글자 수 기반, 실제와 다를 수 있음)."""
    chars = sum(len(user_prompt(r)) for r in rows) + len(SYSTEM_PROMPT) * len(rows)
    in_tok = chars * 0.9          # 한국어는 대략 글자당 0.7~1 토큰
    out_tok = len(rows) * 400     # JSON + 낮은 effort의 추론 토큰을 넉넉히 잡은 값
    if model not in PRICE:
        return (f"입력 약 {in_tok / 1e6:.1f}M 토큰, 출력 약 {out_tok / 1e6:.2f}M 토큰 "
                f"(모델 {model} 의 단가 미등록 — 비용 미계산)")
    pin, pout = PRICE[model]
    usd = (in_tok * pin + out_tok * pout) / 1e6
    return f"입력 약 {in_tok / 1e6:.1f}M 토큰, 출력 약 {out_tok / 1e6:.2f}M 토큰 → 약 ${usd:.1f} (대략치)"


def extract_one(client, r: dict, model: str, effort: str) -> dict:
    """기사 한 건의 이슈를 뽑는다. 실패하면 issue 를 비우고 error 에 사유를 남긴다."""
    row = {"url": r["url"], "issue": "", "issue_norm": "", "issue_type": "", "keywords": "",
           "confidence": "", "input_basis": input_basis(r["body"]), "model": model,
           "prompt_version": PROMPT_VERSION,
           "extracted_at": datetime.now(KST).isoformat(timespec="seconds"), "error": ""}
    try:
        res = client.chat.completions.create(**make_params(r, model, effort))
    except openai.OpenAIError as e:
        row["error"] = f"errored:{type(e).__name__}"
        return row
    ch = res.choices[0]
    if getattr(ch.message, "refusal", None):
        row["error"] = "refusal"
    elif ch.finish_reason == "length":
        row["error"] = "max_tokens"
    else:
        try:
            row.update(parse_response(ch.message.content or ""))
            row["issue_norm"] = normalize_issue(row["issue"])
        except (ValueError, json.JSONDecodeError) as e:
            row["error"] = f"parse:{e}"[:200]
    return row


def merge(new: dict) -> None:
    """기존 결과에 합친다. 같은 URL은 새 결과로 바꾸되, 새 결과가 실패면 기존 성공 결과를 남긴다."""
    old = read_out()
    for url, r in new.items():
        if r["issue"] or not (url in old and old[url]["issue"]):
            old[url] = r
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(sorted(old.values(), key=lambda r: r["url"]))


def run(client, rows: list, model: str, effort: str) -> None:
    done, n_ok, n_fail = {}, 0, 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(extract_one, client, r, model, effort) for r in rows]
        for i, f in enumerate(as_completed(futs), 1):
            row = f.result()
            done[row["url"]] = row
            n_ok += bool(row["issue"])
            n_fail += not row["issue"]
            if i % SAVE_EVERY == 0 or i == len(futs):
                merge(done)
                done = {}
                print(f"  {datetime.now(KST):%H:%M:%S} {i}/{len(futs)}건 — 성공 {n_ok}, 실패 {n_fail}", flush=True)
    print(f"결과 저장: 성공 {n_ok}건, 실패 {n_fail}건 → {rel(OUT)}")
    if n_fail:
        print("실패한 기사는 같은 명령을 다시 실행하면 그것만 다시 처리됩니다.")


def summary(top: int = 30) -> str:
    """저장된 결과의 이슈별·유형별 기사 수와 자주 나온 키워드."""
    rows = [r for r in read_out().values() if r["issue"]]
    if not rows:
        return f"결과가 없습니다: {rel(OUT)}"
    name = {}                      # 묶음 키 → 가장 많이 쓰인 표기
    for r in rows:
        name.setdefault(r["issue_norm"], Counter())[r["issue"]] += 1
    by_issue = Counter(r["issue_norm"] for r in rows)
    by_type = Counter(r["issue_type"] for r in rows)
    kws = Counter(k for r in rows for k in r["keywords"].split("; ") if k)
    single = sum(1 for n in by_issue.values() if n == 1)
    lines = [f"기사 {len(rows):,}건 · 이슈 {len(by_issue):,}개 (기사 1건뿐인 이슈 {single:,}개)", "",
             "[이슈 유형]"]
    lines += [f"  {t}: {n:,}" for t, n in by_type.most_common()]
    lines += ["", f"[기사 수 상위 이슈 {top}개]"]
    lines += [f"  {n:>4,}  {name[k].most_common(1)[0][0]}" for k, n in by_issue.most_common(top)]
    lines += ["", f"[자주 나온 키워드 {top}개]"]
    lines += [f"  {n:>4,}  {k}" for k, n in kws.most_common(top)]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--sample", action="store_true", help="감성 검수 표본(data/eval/sentiment_sample.csv)만")
    g.add_argument("--all", action="store_true", help="처리 범위 전체")
    g.add_argument("--summary", action="store_true", help="저장된 결과 요약만 출력 (호출 없음)")
    ap.add_argument("--dry-run", action="store_true", help="호출하지 않고 건수·예상 비용·예시 프롬프트만 출력")
    ap.add_argument("--limit", type=int, help="앞에서 N건만 (시험용)")
    ap.add_argument("--model", default=MODEL, help=f"기본 {MODEL}")
    ap.add_argument("--effort", default=EFFORT, choices=["low", "medium", "high"], help=f"기본 {EFFORT}")
    a = ap.parse_args()

    if a.summary:
        print(summary())
        return
    if not DB_PATH.exists():
        raise SystemExit(f"DB가 없습니다: {DB_PATH}\n"
                         "python db/build_db.py 로 만들거나 팀원에게 파일을 받아 같은 위치에 둡니다.")
    rows = targets(a.sample)
    skip = done_urls(a.model)
    rows = [r for r in rows if r["url"] not in skip]
    if a.limit:
        rows = rows[:a.limit]
    print(f"대상 {len(rows)}건 (이미 완료 {len(skip)}건 제외) · 모델 {a.model} · effort {a.effort} · {PROMPT_VERSION}")
    if not rows:
        return
    print(estimate(rows, a.model))
    if a.dry_run:
        print("\n[예시 요청 — 첫 기사]\n" + user_prompt(rows[0]))
        return

    load_api_key()
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY 가 없습니다. 환경변수나 .env 에 넣어 주세요.")
    client = openai.OpenAI(max_retries=5, timeout=120)
    run(client, rows, a.model, a.effort)
    print("\n" + summary())


if __name__ == "__main__":
    main()
