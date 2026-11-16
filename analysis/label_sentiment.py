"""LLM 감성(영향) 분류 — OpenAI API로 기회/위험/중립 라벨을 붙인다.

대상: docs/04_ai/AI_CLASSIFICATION.md 2-4절 범위 (대표 CDMO 키워드가 있고 중복이 아닌 기사, 4,727건)
방식: Chat Completions API 를 기사마다 한 번씩 동시에(WORKERS개) 호출한다.
      구조화 출력(response_format json_schema)으로 JSON 형식을 강제하고, parse_response() 로 한 번 더 검증한다.
출력: data/processed/sentiment_llm.csv (기사 URL 키). 이미 같은 모델·프롬프트 버전으로 성공한 기사는 건너뛴다.
      SAVE_EVERY 건마다 중간 저장하므로, 중간에 끊겨도 같은 명령을 다시 실행하면 남은 기사만 처리한다.

실행 (먼저 --dry-run 으로 건수와 예상 비용을 확인한다. 실제 호출은 API 비용이 든다)
  python analysis/label_sentiment.py --sample --dry-run   # 검수 표본 180건만, 호출하지 않고 확인
  python analysis/label_sentiment.py --sample             # 검수 표본 180건만 분류해 저장
  python analysis/label_sentiment.py --all                # 전체 4,727건 (이미 끝난 기사는 제외)
API 키: 환경변수 OPENAI_API_KEY, 없으면 .env 의 OPENAI_API_KEY.
"""
import argparse
import csv
import json
import os
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

import openai

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "collect"))
sys.path.insert(0, str(ROOT / "analysis"))
from config import DB_PATH  # noqa: E402
from sample_sentiment import OUT as SAMPLE_PATH  # noqa: E402
from sample_sentiment import QUERY  # noqa: E402
from sentiment_prompt import (OUTPUT_SCHEMA, PROMPT_VERSION, SYSTEM_PROMPT,  # noqa: E402
                              build_user_prompt, input_basis, parse_response)

MODEL = "gpt-6-luna"
EFFORT = "low"          # 3개 라벨 분류라 깊은 추론이 필요 없다. 정확도가 부족하면 medium 으로 올려 비교한다
MAX_TOKENS = 2048       # 추론(reasoning) 토큰도 여기에 포함된다
WORKERS = 8             # 동시 호출 수
SAVE_EVERY = 200        # 이 건수마다 중간 저장
OUT = ROOT / "data" / "processed" / "sentiment_llm.csv"
COLS = ["url", "label", "reason", "confidence", "input_basis", "model", "prompt_version", "labeled_at",
        "error"]
KST = timezone(timedelta(hours=9))
# 예상 비용 계산용 (1M 토큰당 USD, 입력/출력, 2026-11-16 가격표). 실제 청구액은 콘솔에서 확인한다.
PRICE = {"gpt-6.1-sol": (2.0, 10.0), "gpt-6.1-terra": (1.0, 5.0), "gpt-6-luna": (0.10, 0.50)}


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def load_api_key() -> None:
    """환경변수에 키가 없으면 .env 에서 읽어 넣는다 (값은 출력하지 않는다)."""
    if os.environ.get("OPENAI_API_KEY"):
        return
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("OPENAI_API_KEY="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val:
                    os.environ["OPENAI_API_KEY"] = val


def targets(sample_only: bool) -> list:
    con = sqlite3.connect(DB_PATH)
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


def done_urls(model: str) -> set:
    """같은 모델·프롬프트 버전으로 라벨이 이미 붙은 URL."""
    if not OUT.exists():
        return set()
    with OUT.open(encoding="utf-8-sig", newline="") as f:
        return {r["url"] for r in csv.DictReader(f)
                if r["label"] and r["prompt_version"] == PROMPT_VERSION and r["model"] == model}


def make_params(r: dict, model: str, effort: str) -> dict:
    return {
        "model": model,
        "max_completion_tokens": MAX_TOKENS,
        "reasoning_effort": effort,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(
                r["title"], r["body"], r["lang"], r["published_date"], r["press"])},
        ],
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "sentiment_label", "strict": True, "schema": OUTPUT_SCHEMA}},
    }


def estimate(rows: list, model: str) -> str:
    """대략적인 비용 추정 (글자 수 기반, 실제와 다를 수 있음)."""
    chars = sum(len(build_user_prompt(r["title"], r["body"], r["lang"], r["published_date"], r["press"]))
                for r in rows) + len(SYSTEM_PROMPT) * len(rows)
    in_tok = chars * 0.9          # 한국어는 대략 글자당 0.7~1 토큰
    out_tok = len(rows) * 400     # JSON + 낮은 effort의 추론 토큰을 넉넉히 잡은 값
    if model not in PRICE:
        return (f"입력 약 {in_tok / 1e6:.1f}M 토큰, 출력 약 {out_tok / 1e6:.2f}M 토큰 "
                f"(모델 {model} 의 단가 미등록 — 비용 미계산)")
    pin, pout = PRICE[model]
    usd = (in_tok * pin + out_tok * pout) / 1e6
    return f"입력 약 {in_tok / 1e6:.1f}M 토큰, 출력 약 {out_tok / 1e6:.2f}M 토큰 → 약 ${usd:.1f} (대략치)"


def label_one(client, r: dict, model: str, effort: str) -> dict:
    """기사 한 건을 분류한다. 실패하면 label 을 비우고 error 에 사유를 남긴다."""
    row = {"url": r["url"], "label": "", "reason": "", "confidence": "", "input_basis": input_basis(r["body"]),
           "model": model, "prompt_version": PROMPT_VERSION,
           "labeled_at": datetime.now(KST).isoformat(timespec="seconds"), "error": ""}
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
        except (ValueError, json.JSONDecodeError) as e:
            row["error"] = f"parse:{e}"[:200]
    return row


def run(client, rows: list, model: str, effort: str) -> None:
    done, n_ok, n_fail = {}, 0, 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(label_one, client, r, model, effort) for r in rows]
        for i, f in enumerate(as_completed(futs), 1):
            row = f.result()
            done[row["url"]] = row
            n_ok += bool(row["label"])
            n_fail += not row["label"]
            if i % SAVE_EVERY == 0 or i == len(futs):
                merge(done)
                done = {}
                print(f"  {datetime.now(KST):%H:%M:%S} {i}/{len(futs)}건 — 성공 {n_ok}, 실패 {n_fail}", flush=True)
    print(f"결과 저장: 성공 {n_ok}건, 실패 {n_fail}건 → {rel(OUT)}")
    if n_fail:
        print("실패한 기사는 같은 명령을 다시 실행하면 그것만 다시 처리됩니다.")


def merge(new: dict) -> None:
    """기존 결과에 합친다. 같은 URL은 새 결과로 바꾸되, 새 결과가 실패면 기존 성공 결과를 남긴다."""
    old = {}
    if OUT.exists():
        with OUT.open(encoding="utf-8-sig", newline="") as f:
            old = {r["url"]: r for r in csv.DictReader(f)}
    for url, r in new.items():
        if r["label"] or not (url in old and old[url]["label"]):
            old[url] = r
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(sorted(old.values(), key=lambda r: r["url"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--sample", action="store_true", help="검수 표본(data/eval/sentiment_sample.csv)만")
    g.add_argument("--all", action="store_true", help="처리 범위 전체")
    ap.add_argument("--dry-run", action="store_true", help="호출하지 않고 건수·예상 비용·예시 프롬프트만 출력")
    ap.add_argument("--limit", type=int, help="앞에서 N건만 (시험용)")
    ap.add_argument("--model", default=MODEL, help=f"기본 {MODEL}")
    ap.add_argument("--effort", default=EFFORT, choices=["low", "medium", "high"], help=f"기본 {EFFORT}")
    a = ap.parse_args()

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
        p = make_params(rows[0], a.model, a.effort)
        print("\n[예시 요청 — 첫 기사]\n" + p["messages"][1]["content"])
        return

    load_api_key()
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY 가 없습니다. 환경변수나 .env 에 넣어 주세요.")
    client = openai.OpenAI(max_retries=5, timeout=120)
    run(client, rows, a.model, a.effort)


if __name__ == "__main__":
    main()
