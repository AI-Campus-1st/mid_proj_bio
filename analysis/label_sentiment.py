"""LLM 감성(영향) 분류 — Claude Message Batches API로 기회/위험/중립 라벨을 붙인다.

대상: docs/04_ai/AI_CLASSIFICATION.md 2-4절 범위 (대표 CDMO 키워드가 있고 중복이 아닌 기사, 4,727건)
방식: Message Batches API (비동기, 일반 호출의 50% 가격). 결과는 보통 1시간 안에, 최대 24시간.
      구조화 출력(output_config.format)으로 JSON 형식을 강제하고, parse_response() 로 한 번 더 검증한다.
출력: data/processed/sentiment_llm.csv (기사 URL 키). 이미 같은 프롬프트 버전으로 성공한 기사는 건너뛴다.
      제출한 배치 정보는 data/processed/sentiment_batches.json 에 남겨, 중간에 끊겨도 결과를 다시 받을 수 있다.

실행 (먼저 --dry-run 으로 건수와 예상 비용을 확인한다. 실제 제출은 API 비용이 든다)
  python analysis/label_sentiment.py --sample --dry-run   # 검수 표본 180건만, 제출하지 않고 확인
  python analysis/label_sentiment.py --sample             # 검수 표본 180건만 제출 → 완료까지 기다려 저장
  python analysis/label_sentiment.py --all                # 전체 4,727건 (이미 끝난 기사는 제외)
  python analysis/label_sentiment.py --collect <batch_id> # 끊긴 배치의 결과만 다시 받기
API 키: 환경변수 ANTHROPIC_API_KEY, 없으면 .env 의 ANTHROPIC_API_KEY, 둘 다 없으면 `ant auth login` 프로필.
"""
import argparse
import csv
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "collect"))
sys.path.insert(0, str(ROOT / "analysis"))
from config import DB_PATH  # noqa: E402
from sample_sentiment import OUT as SAMPLE_PATH  # noqa: E402
from sample_sentiment import QUERY  # noqa: E402
from sentiment_prompt import (OUTPUT_SCHEMA, PROMPT_VERSION, SYSTEM_PROMPT,  # noqa: E402
                              build_user_prompt, input_basis, parse_response)

MODEL = "claude-opus-5-5"
EFFORT = "low"          # 3개 라벨 분류라 깊은 추론이 필요 없다. 정확도가 부족하면 medium 으로 올려 비교한다
MAX_TOKENS = 2048       # 생각(thinking) 토큰도 여기에 포함된다
OUT = ROOT / "data" / "processed" / "sentiment_llm.csv"
STATE = ROOT / "data" / "processed" / "sentiment_batches.json"
COLS = ["url", "label", "reason", "confidence", "input_basis", "model", "prompt_version", "labeled_at",
        "error"]
KST = timezone(timedelta(hours=9))
POLL_SEC = 60
# 예상 비용 계산용 (1M 토큰당 USD, Batches 50% 할인 전). 실제 청구액은 콘솔에서 확인한다.
PRICE = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def load_api_key() -> None:
    """환경변수에 키가 없으면 .env 에서 읽어 넣는다 (값은 출력하지 않는다)."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("ANTHROPIC_API_KEY="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val:
                    os.environ["ANTHROPIC_API_KEY"] = val


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
        "max_tokens": MAX_TOKENS,
        "system": [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": build_user_prompt(
            r["title"], r["body"], r["lang"], r["published_date"], r["press"])}],
        "output_config": {"effort": effort, "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
    }


def estimate(rows: list, model: str) -> str:
    """대략적인 비용 추정 (글자 수 기반, 실제와 다를 수 있음)."""
    chars = sum(len(build_user_prompt(r["title"], r["body"], r["lang"], r["published_date"], r["press"]))
                for r in rows) + len(SYSTEM_PROMPT) * len(rows)
    in_tok = chars * 0.9          # 한국어는 대략 글자당 0.7~1 토큰
    out_tok = len(rows) * 400     # JSON + 낮은 effort의 생각 토큰을 넉넉히 잡은 값
    pin, pout = PRICE.get(model, PRICE[MODEL])
    usd = (in_tok * pin + out_tok * pout) / 1e6 * 0.5
    return f"입력 약 {in_tok / 1e6:.1f}M 토큰, 출력 약 {out_tok / 1e6:.2f}M 토큰 → 약 ${usd:.0f} (Batches 50% 할인 반영, 대략치)"


def save_state(entry: dict) -> None:
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else []
    state = [s for s in state if s["batch_id"] != entry["batch_id"]] + [entry]
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def submit(client, rows: list, model: str, effort: str) -> str:
    id_map = {f"n{i}": r["url"] for i, r in enumerate(rows)}  # custom_id 는 영숫자 64자 이내여야 한다
    basis = {r["url"]: input_basis(r["body"]) for r in rows}
    requests = [Request(custom_id=cid, params=MessageCreateParamsNonStreaming(**make_params(r, model, effort)))
                for (cid, _), r in zip(id_map.items(), rows)]
    batch = client.messages.batches.create(requests=requests)
    save_state({"batch_id": batch.id, "model": model, "effort": effort, "prompt_version": PROMPT_VERSION,
                "submitted_at": datetime.now(KST).isoformat(timespec="seconds"),
                "id_map": id_map, "input_basis": basis})
    print(f"배치 제출: {batch.id} ({len(requests)}건). 상태 기록: {rel(STATE)}")
    return batch.id


def wait(client, batch_id: str) -> None:
    while True:
        b = client.messages.batches.retrieve(batch_id)
        c = b.request_counts
        print(f"  {datetime.now(KST):%H:%M} {b.processing_status} — 처리 중 {c.processing}, 성공 {c.succeeded}, "
              f"오류 {c.errored}", flush=True)
        if b.processing_status == "ended":
            return
        time.sleep(POLL_SEC)


def collect(client, batch_id: str) -> None:
    state = {s["batch_id"]: s for s in json.loads(STATE.read_text(encoding="utf-8"))} if STATE.exists() else {}
    if batch_id not in state:
        raise SystemExit(f"{batch_id} 의 제출 기록이 {rel(STATE)} 에 없습니다.")
    st = state[batch_id]
    rows, n_ok, n_fail = {}, 0, 0
    now = datetime.now(KST).isoformat(timespec="seconds")
    for res in client.messages.batches.results(batch_id):
        url = st["id_map"][res.custom_id]
        row = {"url": url, "label": "", "reason": "", "confidence": "", "input_basis": st["input_basis"][url],
               "model": st["model"], "prompt_version": st["prompt_version"], "labeled_at": now, "error": ""}
        r = res.result
        if r.type == "succeeded":
            msg = r.message
            if msg.stop_reason == "refusal":
                cat = getattr(msg.stop_details, "category", None) if msg.stop_details else None
                row["error"] = f"refusal:{cat}"
            elif msg.stop_reason == "max_tokens":
                row["error"] = "max_tokens"
            else:
                text = next((b.text for b in msg.content if b.type == "text"), "")
                try:
                    row.update(parse_response(text))
                except (ValueError, json.JSONDecodeError) as e:
                    row["error"] = f"parse:{e}"[:200]
        elif r.type == "errored":
            row["error"] = f"errored:{r.error.type}"
        else:  # canceled / expired
            row["error"] = r.type
        n_ok += bool(row["label"])
        n_fail += not row["label"]
        rows[url] = row
    merge(rows)
    print(f"결과 저장: 성공 {n_ok}건, 실패 {n_fail}건 → {rel(OUT)}")
    if n_fail:
        print("실패한 기사는 같은 명령을 다시 실행하면 그것만 다시 제출됩니다.")


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
    g.add_argument("--collect", metavar="BATCH_ID", help="이미 제출한 배치의 결과만 받기")
    ap.add_argument("--dry-run", action="store_true", help="제출하지 않고 건수·예상 비용·예시 프롬프트만 출력")
    ap.add_argument("--limit", type=int, help="앞에서 N건만 (시험용)")
    ap.add_argument("--model", default=MODEL, help=f"기본 {MODEL}")
    ap.add_argument("--effort", default=EFFORT, choices=["low", "medium", "high"], help=f"기본 {EFFORT}")
    a = ap.parse_args()

    if a.collect:
        load_api_key()
        client = anthropic.Anthropic()
        wait(client, a.collect)
        collect(client, a.collect)
        return

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
        print("\n[예시 요청 — 첫 기사]\n" + p["messages"][0]["content"])
        return

    load_api_key()
    client = anthropic.Anthropic()
    batch_id = submit(client, rows, a.model, a.effort)
    print("완료까지 기다립니다. 창을 닫아도 배치는 계속 처리되며, 나중에 --collect 로 결과를 받을 수 있습니다.")
    wait(client, batch_id)
    collect(client, batch_id)


if __name__ == "__main__":
    main()
