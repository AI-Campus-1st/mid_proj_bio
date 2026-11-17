"""이슈 이름 묶기 — 같은 사건인데 다르게 붙은 이슈 이름을 대표 이름 하나로 합친다.

extract_issues.py 는 기사마다 따로 이슈 이름을 뽑으므로, 같은 사건이 여러 이름으로 나뉜다
("삼성바이오로직스 폴리펩타이드그룹 인수" / "삼성바이오로직스 PPG 인수"). 이 스크립트는 기사가 아니라
**이슈 이름 목록**만 LLM에 넣어, 이름마다 대표 이름(issue_group)을 정한다.

입력: data/processed/issues_llm.csv (extract_issues.py 결과)
방식: 이슈 이름을 가나다순으로 BATCH 개씩 나눠 차례로 호출한다. 호출마다 지금까지 정해진 대표 이름 중
      기사 수가 많은 CANON_TOP 개를 함께 넣어, 뒤 묶음이 앞 묶음의 대표 이름을 다시 쓰게 한다.
      (앞 결과를 이어 쓰므로 동시에 호출하지 않는다.)
      응답에서 빠진 이름이나 형식이 틀린 이름은 원래 이름을 대표 이름으로 둔다.
출력: data/processed/issue_groups.csv (issue_norm 키). 기사별 결과는 issues_llm.csv 와 issue_norm 으로 잇는다.
      이미 같은 모델·프롬프트 버전으로 묶인 이름은 건너뛴다. 처음부터 다시 묶으려면 --rebuild.

실행 (이슈 이름만 넣으므로 비용은 추출보다 훨씬 작다)
  python analysis/group_issues.py --dry-run    # 호출하지 않고 이름 수·호출 횟수만 확인
  python analysis/group_issues.py              # 새 이름만 묶는다
  python analysis/group_issues.py --rebuild    # 전부 다시 묶는다
  python analysis/group_issues.py --summary    # 묶은 결과의 이슈별 기사 수만 출력 (호출 없음)
API 키: 환경변수 OPENAI_API_KEY, 없으면 .env 의 OPENAI_API_KEY.

한계: LLM이 이름만 보고 판단하므로 다른 사건을 합치거나(과병합) 같은 사건을 못 합칠 수 있다.
      결과는 --summary 로 확인하고, 묶음 정확도는 표본으로 검수한다.
"""
import argparse
import csv
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import openai

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "collect"))
sys.path.insert(0, str(ROOT / "analysis"))
from extract_issues import OUT as ISSUES_PATH  # noqa: E402
from issue_prompt import ISSUE_MAX, normalize_issue  # noqa: E402
from label_sentiment import KST, load_api_key, rel  # noqa: E402

PROMPT_VERSION = "issue-group-v1"
MODEL = "gpt-6-luna"
EFFORT = "medium"       # 이름끼리 비교하는 일이라 추출(low)보다 한 단계 높게 둔다
MAX_TOKENS = 16000      # 추론 토큰 포함. 이름 BATCH 개의 대응표가 들어갈 만큼 넉넉히 잡는다
BATCH = 120             # 한 번에 넣는 이슈 이름 수
CANON_TOP = 250         # 함께 넣는 기존 대표 이름 수 (기사 수 많은 순)
OUT = Path(os.environ.get("ISSUE_GROUPS_OUT", ROOT / "data" / "processed" / "issue_groups.csv"))
COLS = ["issue_norm", "issue", "issue_group", "n_articles", "model", "prompt_version", "grouped_at"]

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "mapping": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "group": {"type": "string"}},
                "required": ["id", "group"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["mapping"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = f"""당신은 글로벌 바이오 CDMO(위탁개발생산) 뉴스의 이슈 이름을 정리하는 편집자입니다.
뉴스 기사마다 따로 붙인 이슈 이름 목록을 받아, **같은 사건·같은 주제를 가리키는 이름을 대표 이름 하나로 통일**합니다.

[입력]
- [기존 대표 이름]: 이미 정해진 대표 이름입니다. 같은 사건이면 이 이름을 **글자 그대로** 다시 씁니다.
- [이슈 이름]: 번호가 붙은 이름 목록입니다. 번호마다 대표 이름을 정합니다.

[합치는 경우]
- 표기만 다른 경우: 띄어쓰기, 약칭과 정식 이름(삼바 = 삼성바이오로직스, PPG = 폴리펩타이드그룹),
  영문과 한글(Lonza = 론자, BIOSECURE Act = 미국 생물보안법)
- 같은 사건의 다른 단계나 다른 표현: "생물보안법 발의", "생물보안법 상원 통과", "미국 생물보안법 재추진"
  → "미국 생물보안법"
- 같은 기업의 개별 수주 소식: "○○ 수주", "○○ 위탁생산 계약", "○○ 대규모 수주" → "○○ 수주"

[합치지 않는 경우]
- 기업이 다르면 합치지 않습니다 ("삼성바이오로직스 수주"와 "에스티팜 수주"는 다른 이슈).
- 같은 기업이라도 사건이 다르면 합치지 않습니다 ("5공장 증설"과 "5공장 파업", "인적분할"과 "유상증자").
- 정책이 다르면 합치지 않습니다 ("미국 생물보안법"과 "미국 의약품 관세").
- 확신이 없으면 합치지 않고 원래 이름을 그대로 대표 이름으로 둡니다.

[대표 이름]
- {ISSUE_MAX}자 이내의 한국어 명사구, "주체 + 사건" 형태. 날짜·금액·수식어는 넣지 않습니다.
- 기존 대표 이름이나 목록에 있는 이름 중 가장 짧고 분명한 것을 고릅니다. 새 이름을 지어내는 것은
  목록의 이름이 모두 부적절할 때만 합니다.

[출력]
- 모든 번호에 대해 {{"id": 번호, "group": "대표 이름"}} 을 빠짐없이 한 번씩 답합니다.
- JSON 한 개만 답합니다."""


def load_issues() -> dict:
    """issues_llm.csv 에서 이슈 이름별 기사 수를 센다. {issue_norm: {"issue": 대표 표기, "n": 기사 수}}"""
    if not ISSUES_PATH.exists():
        raise SystemExit(f"이슈 추출 결과가 없습니다: {rel(ISSUES_PATH)}\n"
                         "먼저 python analysis/extract_issues.py 를 실행합니다.")
    variants = {}
    with ISSUES_PATH.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["issue"]:
                variants.setdefault(r["issue_norm"], Counter())[r["issue"]] += 1
    return {k: {"issue": c.most_common(1)[0][0], "n": sum(c.values())} for k, c in variants.items()}


def read_out() -> dict:
    if not OUT.exists():
        return {}
    with OUT.open(encoding="utf-8-sig", newline="") as f:
        return {r["issue_norm"]: r for r in csv.DictReader(f)}


def write_out(rows: dict) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(sorted(rows.values(), key=lambda r: r["issue_norm"]))


def top_canon(rows: dict) -> list:
    """지금까지의 대표 이름을 기사 수 많은 순으로 CANON_TOP 개."""
    n = Counter()
    for r in rows.values():
        n[r["issue_group"]] += int(r["n_articles"])
    return [g for g, _ in n.most_common(CANON_TOP)]


def build_user_prompt(names: list, canon: list) -> str:
    head = "[기존 대표 이름]\n" + ("\n".join(f"- {c}" for c in canon) if canon else "(아직 없음)")
    body = "[이슈 이름]\n" + "\n".join(f"{i}. {n}" for i, n in enumerate(names, 1))
    return f"{head}\n\n{body}"


def parse_response(text: str, names: list) -> tuple:
    """응답을 {이름: 대표 이름} 으로 바꾼다. 빠지거나 틀린 번호는 원래 이름을 쓰고 그 수를 함께 돌려준다."""
    d = json.loads(text[text.index("{"): text.rindex("}") + 1])
    got = {}
    for m in d.get("mapping", []):
        i, g = m.get("id"), " ".join(str(m.get("group", "")).split())
        if isinstance(i, int) and 1 <= i <= len(names) and g and len(g) <= ISSUE_MAX and i not in got:
            got[i] = g
    out = {n: got.get(i, n) for i, n in enumerate(names, 1)}
    return out, len(names) - len(got)


def unify(rows: dict) -> int:
    """표기만 다른 대표 이름(공백·문장부호)을 기사 수가 가장 많은 표기로 통일한다. 바뀐 행 수를 돌려준다."""
    n = {}
    for r in rows.values():
        n.setdefault(normalize_issue(r["issue_group"]), Counter())[r["issue_group"]] += int(r["n_articles"])
    best = {k: c.most_common(1)[0][0] for k, c in n.items()}
    changed = 0
    for r in rows.values():
        b = best[normalize_issue(r["issue_group"])]
        if r["issue_group"] != b:
            r["issue_group"] = b
            changed += 1
    return changed


def group_batch(client, names: list, canon: list, model: str, effort: str) -> tuple:
    """이름 한 묶음의 대표 이름을 받는다. 호출이나 해석에 실패하면 모두 원래 이름으로 둔다."""
    try:
        res = client.chat.completions.create(
            model=model, max_completion_tokens=MAX_TOKENS, reasoning_effort=effort,
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": build_user_prompt(names, canon)}],
            response_format={"type": "json_schema", "json_schema": {
                "name": "issue_groups", "strict": True, "schema": OUTPUT_SCHEMA}})
        ch = res.choices[0]
        if getattr(ch.message, "refusal", None) or ch.finish_reason == "length":
            raise ValueError("refusal" if getattr(ch.message, "refusal", None) else "max_tokens")
        return parse_response(ch.message.content or "", names)
    except (openai.OpenAIError, ValueError, json.JSONDecodeError) as e:
        print(f"    묶음 실패({type(e).__name__}: {str(e)[:80]}) — 이 묶음은 원래 이름을 그대로 둡니다.")
        return {n: n for n in names}, len(names)


def run(client, issues: dict, rows: dict, model: str, effort: str) -> None:
    todo = sorted((k for k in issues if k not in rows), key=lambda k: issues[k]["issue"])
    n_calls = -(-len(todo) // BATCH)
    missed = 0
    for b in range(n_calls):
        keys = todo[b * BATCH:(b + 1) * BATCH]
        names = [issues[k]["issue"] for k in keys]
        mapping, miss = group_batch(client, names, top_canon(rows), model, effort)
        missed += miss
        now = datetime.now(KST).isoformat(timespec="seconds")
        for k, name in zip(keys, names):
            rows[k] = {"issue_norm": k, "issue": name, "issue_group": mapping[name],
                       "n_articles": issues[k]["n"], "model": model,
                       "prompt_version": PROMPT_VERSION, "grouped_at": now}
        unify(rows)
        write_out(rows)
        print(f"  {datetime.now(KST):%H:%M:%S} {b + 1}/{n_calls}회 — 이름 {len(rows):,}개 → "
              f"이슈 {len({r['issue_group'] for r in rows.values()}):,}개", flush=True)
    print(f"저장: {rel(OUT)}" + (f" (응답에서 빠져 원래 이름을 쓴 이름 {missed}개)" if missed else ""))


def summary(top: int = 30) -> str:
    rows = read_out()
    if not rows:
        return f"결과가 없습니다: {rel(OUT)}"
    n, members = Counter(), {}
    for r in rows.values():
        n[r["issue_group"]] += int(r["n_articles"])
        members.setdefault(r["issue_group"], []).append(r["issue"])
    total = sum(n.values())
    single = sum(1 for v in n.values() if v == 1)
    merged = {g: m for g, m in members.items() if len(m) > 1}
    lines = [f"기사 {total:,}건 · 이슈 이름 {len(rows):,}개 → 묶은 뒤 이슈 {len(n):,}개 "
             f"(기사 1건뿐인 이슈 {single:,}개)",
             f"이름이 2개 이상 합쳐진 이슈 {len(merged):,}개", "", f"[기사 수 상위 이슈 {top}개]"]
    lines += [f"  {v:>4,}  {g}" + (f"  ← 이름 {len(members[g])}개" if len(members[g]) > 1 else "")
              for g, v in n.most_common(top)]
    lines += ["", f"[합쳐진 예 — 이름 수 많은 순 {min(top, 15)}개]"]
    for g, m in sorted(merged.items(), key=lambda kv: -len(kv[1]))[:min(top, 15)]:
        shown = ", ".join(sorted(m)[:6]) + (" …" if len(m) > 6 else "")
        lines.append(f"  {g}  ←  {shown}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="호출하지 않고 이름 수·호출 횟수만 출력")
    ap.add_argument("--rebuild", action="store_true", help="기존 결과를 버리고 전부 다시 묶는다")
    ap.add_argument("--summary", action="store_true", help="묶은 결과 요약만 출력 (호출 없음)")
    ap.add_argument("--model", default=MODEL, help=f"기본 {MODEL}")
    ap.add_argument("--effort", default=EFFORT, choices=["low", "medium", "high"], help=f"기본 {EFFORT}")
    a = ap.parse_args()

    if a.summary:
        print(summary())
        return
    issues = load_issues()
    rows = {} if a.rebuild else {k: r for k, r in read_out().items()
                                 if k in issues and r["prompt_version"] == PROMPT_VERSION and r["model"] == a.model}
    for k, r in rows.items():                       # 추출을 더 돌려 기사 수가 늘었으면 갱신
        r["n_articles"] = issues[k]["n"]
    todo = [k for k in issues if k not in rows]
    n_calls = -(-len(todo) // BATCH)
    print(f"이슈 이름 {len(issues):,}개 (이미 묶인 {len(rows):,}개 제외 → {len(todo):,}개) · "
          f"호출 {n_calls}회 · 모델 {a.model} · effort {a.effort} · {PROMPT_VERSION}")
    if a.dry_run or not todo:
        if not todo and rows:
            write_out(rows)
        return

    load_api_key()
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY 가 없습니다. 환경변수나 .env 에 넣어 주세요.")
    client = openai.OpenAI(max_retries=5, timeout=300)
    run(client, issues, rows, a.model, a.effort)
    print("\n" + summary())


if __name__ == "__main__":
    main()
