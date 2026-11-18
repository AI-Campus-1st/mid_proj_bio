"""LLM 영어 기사 제목 번역 (T4, PRD F8) — 영어 기사 제목을 한국어로 옮겨 news.title_ko 에 넣는다.

대상: DB news 중 lang='en' (797건, 모두 제목만).
방식: analysis/extract_issues.py 와 같다. Chat Completions API 를 기사마다 한 번씩 동시에 호출하고,
      구조화 출력으로 JSON 형식을 강제한 뒤 translate_prompt.parse_response() 로 한 번 더 검증한다.
출력: data/processed/title_ko.csv (URL 키). 같은 모델·프롬프트 버전으로 성공한 기사는 건너뛴다.
      실행이 끝나면 성공한 번역을 DB news.title_ko 에 바로 넣는다 (대시보드는 DB 를 읽는다 — 재시작 필요).
      DB 를 다시 빌드하면 build_db.py 가 이 파일을 읽어 title_ko 를 다시 채운다. 그래서 번역을 다시 돌릴 필요가 없다.

실행 (먼저 --dry-run 으로 건수와 예상 비용을 확인한다. 실제 호출은 API 비용이 든다)
  python analysis/translate_titles.py --all --dry-run     # 호출하지 않고 확인
  python analysis/translate_titles.py --all --limit 20    # 앞 20건만 (시험)
  python analysis/translate_titles.py --all               # 전체 (이미 끝난 기사는 제외)
  python analysis/translate_titles.py --failed            # 실패한 기사만 다시
  python analysis/translate_titles.py --apply             # 파일의 번역을 DB 에 다시 넣기만 (호출 없음)
API 키: 환경변수 OPENAI_API_KEY, 없으면 .env 의 OPENAI_API_KEY.
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
from label_sentiment import KST, PRICE, load_api_key, rel  # noqa: E402
from translate_prompt import OUTPUT_SCHEMA, PROMPT_VERSION, SYSTEM_PROMPT, build_user_prompt, parse_response  # noqa: E402

MODEL = "gpt-6-luna"    # 감성·이슈·모달리티와 같은 모델 — 제목 한 줄 번역이라 작은 모델로 충분하다
EFFORT = "low"
MAX_TOKENS = 1024       # 제목 한 줄 + 낮은 effort 추론 토큰
WORKERS = 8             # 다른 LLM 단계와 같은 동시 호출 수
SAVE_EVERY = 100
OUT = Path(os.environ.get("TITLE_KO_OUT", ROOT / "data" / "processed" / "title_ko.csv"))
COLS = ["url", "title", "title_ko", "model", "prompt_version", "translated_at", "error"]
QUERY = "SELECT url, title FROM news WHERE lang = 'en' ORDER BY url"


def targets(db_path=None) -> list:
    con = sqlite3.connect(db_path or DB_PATH)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(QUERY)]
    con.close()
    return rows


def read_out() -> dict:
    if not OUT.exists():
        return {}
    with OUT.open(encoding="utf-8-sig", newline="") as f:
        return {r["url"]: r for r in csv.DictReader(f)}


def done_urls(model: str) -> set:
    return {u for u, r in read_out().items()
            if r["title_ko"] and r["prompt_version"] == PROMPT_VERSION and r["model"] == model}


def make_params(r: dict, model: str, effort: str) -> dict:
    return {
        "model": model,
        "max_completion_tokens": MAX_TOKENS,
        "reasoning_effort": effort,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                     {"role": "user", "content": build_user_prompt(r["title"])}],
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "title_translation", "strict": True, "schema": OUTPUT_SCHEMA}},
    }


def estimate(rows: list, model: str) -> str:
    """대략적인 비용 (글자 수 기반). 영어는 대략 글자당 0.3 토큰, 시스템 프롬프트(한국어)는 글자당 1 토큰으로 넉넉히 잡는다."""
    in_tok = sum(len(r["title"]) * 0.3 + len(SYSTEM_PROMPT) for r in rows)
    out_tok = len(rows) * 300     # 번역 JSON + 낮은 effort 추론 토큰을 넉넉히 잡은 값
    if model not in PRICE:
        return f"입력 약 {in_tok / 1e6:.2f}M 토큰, 출력 약 {out_tok / 1e6:.2f}M 토큰 (단가 미등록 — 비용 미계산)"
    pin, pout = PRICE[model]
    return (f"입력 약 {in_tok / 1e6:.2f}M 토큰, 출력 약 {out_tok / 1e6:.2f}M 토큰 → "
            f"약 ${(in_tok * pin + out_tok * pout) / 1e6:.2f} (대략치)")


def translate_one(client, r: dict, model: str, effort: str) -> dict:
    row = {"url": r["url"], "title": r["title"], "title_ko": "", "model": model, "prompt_version": PROMPT_VERSION,
           "translated_at": datetime.now(KST).isoformat(timespec="seconds"), "error": ""}
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
            row["title_ko"] = parse_response(ch.message.content or "", r["title"])
        except (ValueError, json.JSONDecodeError) as e:
            row["error"] = f"parse:{e}"[:200]
    return row


def merge(new: dict) -> None:
    """같은 URL은 새 결과로 바꾸되, 새 결과가 실패면 기존 성공 결과를 남긴다."""
    old = read_out()
    for url, r in new.items():
        if r["title_ko"] or not (url in old and old[url]["title_ko"]):
            old[url] = r
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(sorted(old.values(), key=lambda r: r["url"]))


def apply_to_db(db_path=None) -> int:
    """파일의 성공한 번역을 news.title_ko 에 넣는다. 넣은 행 수를 돌려준다."""
    rows = [(r["title_ko"], u) for u, r in read_out().items() if r["title_ko"]]
    con = sqlite3.connect(db_path or DB_PATH)
    n = 0
    for t, u in rows:
        n += con.execute("UPDATE news SET title_ko = ? WHERE url = ? AND lang = 'en'", (t, u)).rowcount
    con.commit()
    con.close()
    return n


def run(client, rows: list, model: str, effort: str) -> None:
    done, n_ok, n_fail = {}, 0, 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(translate_one, client, r, model, effort) for r in rows]
        for i, f in enumerate(as_completed(futs), 1):
            row = f.result()
            done[row["url"]] = row
            n_ok += bool(row["title_ko"])
            n_fail += not row["title_ko"]
            if i % SAVE_EVERY == 0 or i == len(futs):
                merge(done)
                done = {}
                print(f"  {datetime.now(KST):%H:%M:%S} {i}/{len(futs)}건 — 성공 {n_ok}, 실패 {n_fail}", flush=True)
    print(f"결과 저장: 성공 {n_ok}건, 실패 {n_fail}건 → {rel(OUT)}")
    if n_fail:
        print("실패한 기사는 --failed 로 다시 처리합니다.")


def summary() -> str:
    rows = list(read_out().values())
    ok = [r for r in rows if r["title_ko"]]
    lines = [f"번역 {len(ok):,}/{len(rows):,}건 성공"]
    errs = Counter(r["error"].split(":")[0] for r in rows if not r["title_ko"])
    if errs:
        lines.append("실패 사유: " + ", ".join(f"{k} {v}" for k, v in errs.items()))
    lines.append("예시 5건:")
    lines += [f"  {r['title']}\n  → {r['title_ko']}" for r in ok[:5]]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true", help="영어 기사 전체 (이미 끝난 기사 제외)")
    g.add_argument("--failed", action="store_true", help="결과 파일에서 실패한 기사만")
    g.add_argument("--apply", action="store_true", help="결과 파일의 번역을 DB 에 넣기만 (호출 없음)")
    g.add_argument("--summary", action="store_true", help="결과 요약만 (호출 없음)")
    ap.add_argument("--dry-run", action="store_true", help="호출하지 않고 건수·예상 비용·예시 프롬프트만")
    ap.add_argument("--limit", type=int, help="앞에서 N건만 (시험용)")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--effort", default=EFFORT, choices=["low", "medium", "high"])
    a = ap.parse_args()

    if a.summary:
        print(summary())
        return
    if not DB_PATH.exists():
        raise SystemExit(f"DB가 없습니다: {DB_PATH} — python db/build_db.py 로 먼저 만듭니다.")
    if a.apply:
        print(f"DB news.title_ko 에 {apply_to_db():,}건 넣음")
        return
    rows = targets()
    skip = done_urls(a.model)
    rows = [r for r in rows if r["url"] not in skip]
    if a.failed:
        failed = {u for u, r in read_out().items() if not r["title_ko"]}
        rows = [r for r in rows if r["url"] in failed]
    if a.limit:
        rows = rows[:a.limit]
    print(f"대상 {len(rows)}건 (이미 완료 {len(skip)}건 제외) · 모델 {a.model} · effort {a.effort} · {PROMPT_VERSION}")
    if not rows:
        return
    print(estimate(rows, a.model))
    if a.dry_run:
        print("\n[예시 요청 — 첫 기사]\n" + build_user_prompt(rows[0]["title"]))
        return
    load_api_key()
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY 가 없습니다. 환경변수나 .env 에 넣어 주세요.")
    client = openai.OpenAI(max_retries=5, timeout=120)
    run(client, rows, a.model, a.effort)
    print(f"DB news.title_ko 에 {apply_to_db():,}건 넣음 (대시보드는 다시 켜야 보입니다)")
    print("\n" + summary())


if __name__ == "__main__":
    main()
