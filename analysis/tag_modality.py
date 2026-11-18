"""LLM 모달리티 태깅 (T3) — 기사마다 다루는 모달리티(의약품 종류) 태그를 붙인다.

대상: 감성 분류·이슈 추출과 같은 범위 (대표 CDMO 키워드가 있고 중복이 아닌 기사, 4,727건).
      sample_sentiment.QUERY 를 그대로 쓴다. 같은 기사 집합이라 화면에서 감성·이슈와 URL 로 붙일 수 있다.
      모달리티 키워드(995건)만 하지 않는 이유: 규칙(build_cdmo_news.py)에 없는 표현을 쓴 기사도 잡기 위해서다.
방식: analysis/extract_issues.py 와 같다. Chat Completions API 를 기사마다 한 번씩 동시에 호출하고,
      구조화 출력으로 JSON 형식을 강제한 뒤 modality_prompt.parse_response() 로 한 번 더 검증한다.
출력: data/processed/modality_llm.csv (기사 URL 키).
      modalities 는 '; ' 로 이은 태그 목록이고, 빈 값이면 특정 모달리티를 다루지 않는 기사다.
      같은 모델·프롬프트 버전으로 성공한 기사는 건너뛴다. SAVE_EVERY 건마다 중간 저장하므로
      끊겨도 같은 명령을 다시 실행하면 남은 기사만 처리한다.

실행 (먼저 --dry-run 으로 건수와 예상 비용을 확인한다. 실제 호출은 API 비용이 든다)
  python analysis/tag_modality.py --all --dry-run          # 전체, 호출하지 않고 확인
  python analysis/tag_modality.py --all --limit 50         # 앞 50건만 (시험)
  python analysis/tag_modality.py --all                    # 전체 (이미 끝난 기사는 제외 — 실패한 기사도 다시 처리)
  python analysis/tag_modality.py --failed                 # 실패한 기사만 다시 처리 (아직 시도 안 한 기사는 제외)
  python analysis/tag_modality.py --summary                # 저장된 결과 요약만 (호출 없음)
API 키: 환경변수 OPENAI_API_KEY, 없으면 .env 의 OPENAI_API_KEY.

한계: 제목만 있는 기사(약 74%)는 제목에 모달리티가 없으면 빈 태그가 된다. 즉 태그 수는 실제 언급보다 적게 잡힌다.
      정확도는 표본 검수로 확인해야 한다 (AI_EVALUATION).
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
from modality_prompt import (MODALITIES, OUTPUT_SCHEMA, PROMPT_VERSION, SYSTEM_PROMPT,  # noqa: E402
                             build_user_prompt, input_basis, parse_response)
from sample_sentiment import QUERY  # noqa: E402

MODEL = "gpt-6-luna"    # 감성 분류·이슈 추출과 같은 모델 — 목록에서 고르는 단순 분류라 작은 모델로 충분하다
EFFORT = "low"          # 이슈 추출과 같은 값. 태그 목록이 정해져 있어 깊은 추론이 필요 없다
MAX_TOKENS = 2048       # 추론(reasoning) 토큰도 여기에 포함된다
WORKERS = 8             # 동시 호출 수 (이슈 추출과 같음 — 이 값으로 속도 제한에 걸리지 않았다)
SAVE_EVERY = 200        # 이 건수마다 중간 저장
OUT = Path(os.environ.get("MODALITY_LLM_OUT", ROOT / "data" / "processed" / "modality_llm.csv"))
COLS = ["url", "modalities", "evidence", "confidence", "input_basis",
        "model", "prompt_version", "tagged_at", "error"]
# 요약의 기업 × 모달리티 표. 기업 단위 분석은 제목·본문에 기업명이 있는 기사만 쓴다 (PRD 4절).
COMPANY_QUERY = """
SELECT n.url, c.corp_name
FROM news_companies nc
JOIN news n ON n.news_id = nc.news_id
JOIN companies c ON c.corp_code = nc.corp_code
WHERE nc.match_field IN ('title', 'body')
"""


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


def ok(r: dict) -> bool:
    """성공한 결과인가. 빈 태그도 성공이므로 error 칸으로 판단한다."""
    return not r["error"]


def done_urls(model: str) -> set:
    """같은 모델·프롬프트 버전으로 이미 태깅에 성공한 URL."""
    return {u for u, r in read_out().items()
            if ok(r) and r["prompt_version"] == PROMPT_VERSION and r["model"] == model}


def user_prompt(r: dict) -> str:
    return build_user_prompt(r["title"], r["body"], r["lang"], r["published_date"], r["press"])


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
            "name": "modality_tagging", "strict": True, "schema": OUTPUT_SCHEMA}},
    }


def estimate(rows: list, model: str) -> str:
    """대략적인 비용 추정 (글자 수 기반, 실제와 다를 수 있음). 계수는 extract_issues.py 와 같다."""
    chars = sum(len(user_prompt(r)) for r in rows) + len(SYSTEM_PROMPT) * len(rows)
    in_tok = chars * 0.9          # 한국어는 대략 글자당 0.7~1 토큰
    out_tok = len(rows) * 400     # JSON + 낮은 effort의 추론 토큰을 넉넉히 잡은 값
    if model not in PRICE:
        return (f"입력 약 {in_tok / 1e6:.1f}M 토큰, 출력 약 {out_tok / 1e6:.2f}M 토큰 "
                f"(모델 {model} 의 단가 미등록 — 비용 미계산)")
    pin, pout = PRICE[model]
    usd = (in_tok * pin + out_tok * pout) / 1e6
    return f"입력 약 {in_tok / 1e6:.1f}M 토큰, 출력 약 {out_tok / 1e6:.2f}M 토큰 → 약 ${usd:.1f} (대략치)"


def tag_one(client, r: dict, model: str, effort: str) -> dict:
    """기사 한 건에 태그를 붙인다. 실패하면 error 에 사유를 남긴다."""
    row = {"url": r["url"], "modalities": "", "evidence": "", "confidence": "",
           "input_basis": input_basis(r["body"]), "model": model, "prompt_version": PROMPT_VERSION,
           "tagged_at": datetime.now(KST).isoformat(timespec="seconds"), "error": ""}
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


def merge(new: dict) -> None:
    """기존 결과에 합친다. 같은 URL은 새 결과로 바꾸되, 새 결과가 실패면 기존 성공 결과를 남긴다."""
    old = read_out()
    for url, r in new.items():
        if ok(r) or not (url in old and ok(old[url])):
            old[url] = r
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(sorted(old.values(), key=lambda r: r["url"]))


def run(client, rows: list, model: str, effort: str) -> None:
    done, n_ok, n_fail = {}, 0, 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(tag_one, client, r, model, effort) for r in rows]
        for i, f in enumerate(as_completed(futs), 1):
            row = f.result()
            done[row["url"]] = row
            n_ok += ok(row)
            n_fail += not ok(row)
            if i % SAVE_EVERY == 0 or i == len(futs):
                merge(done)
                done = {}
                print(f"  {datetime.now(KST):%H:%M:%S} {i}/{len(futs)}건 — 성공 {n_ok}, 실패 {n_fail}", flush=True)
    print(f"결과 저장: 성공 {n_ok}건, 실패 {n_fail}건 → {rel(OUT)}")
    if n_fail:
        print("실패한 기사는 같은 명령을 다시 실행하면 그것만 다시 처리됩니다.")


def summary(db_path=None) -> str:
    """저장된 결과의 모달리티별 기사 수, 입력 근거별 태그 비율, 기업 × 모달리티 표."""
    rows = [r for r in read_out().values() if ok(r)]
    if not rows:
        return f"결과가 없습니다: {rel(OUT)}"
    fails = sum(1 for r in read_out().values() if not ok(r))
    tags = {r["url"]: [t for t in r["modalities"].split("; ") if t] for r in rows}
    tagged = sum(1 for t in tags.values() if t)
    by_mod = Counter(t for ts in tags.values() for t in ts)
    multi = sum(1 for t in tags.values() if len(t) > 1)
    lines = [f"기사 {len(rows):,}건 (실패 {fails}건) · 태그 있음 {tagged:,}건 ({tagged / len(rows):.1%}) · "
             f"여러 태그 {multi:,}건", "", "[모달리티별 기사 수]"]
    lines += [f"  {m}: {by_mod.get(m, 0):,}" for m in MODALITIES]
    lines += ["", "[입력 근거별 태그 비율 — 제목만인 기사는 낮게 나오는 것이 정상]"]
    for basis in ("body", "title"):
        sub = [r for r in rows if r["input_basis"] == basis]
        if sub:
            n = sum(1 for r in sub if r["modalities"])
            lines.append(f"  {basis}: {n:,}/{len(sub):,} ({n / len(sub):.1%})")
    lines += ["", "[확신도]"]
    lines += [f"  {k}: {v:,}" for k, v in Counter(r["confidence"] for r in rows).most_common()]
    path = Path(db_path or DB_PATH)
    if path.exists():
        con = sqlite3.connect(path)
        corp = {}
        for url, name in con.execute(COMPANY_QUERY):
            corp.setdefault(url, set()).add(name)
        con.close()
        names = sorted({n for s in corp.values() for n in s})
        mods = [m for m in MODALITIES if m != "기타"]
        lines += ["", "[기업 × 모달리티 기사 수 — 제목·본문에 기업명이 있는 기사]",
                  "  " + " | ".join(["기업"] + mods)]
        for name in names:
            cnt = Counter(t for u, ts in tags.items() if name in corp.get(u, ()) for t in ts)
            lines.append("  " + " | ".join([name] + [str(cnt.get(m, 0)) for m in mods]))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true", help="처리 범위 전체")
    g.add_argument("--failed", action="store_true",
                   help="결과 파일에서 실패(error 칸이 있는)한 기사만 다시 처리. 아직 시도하지 않은 기사는 제외")
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
    rows = targets()
    skip = done_urls(a.model)
    rows = [r for r in rows if r["url"] not in skip]
    if a.failed:
        failed = {u for u, r in read_out().items() if not ok(r)}
        reasons = Counter(r["error"].split(":")[0] for r in read_out().values() if not ok(r))
        print(f"결과 파일의 실패 {len(failed)}건 — 사유: " + (", ".join(f"{k} {v}" for k, v in reasons.items()) or "없음"))
        rows = [r for r in rows if r["url"] in failed]
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
