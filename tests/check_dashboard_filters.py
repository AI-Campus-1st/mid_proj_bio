"""대시보드 통합 점검 — 7개 화면 × 필터 조합 (과제 제출 전 점검 "필터가 모든 차트에 반영된다").

Streamlit AppTest 로 화면 함수를 실제로 실행해 (1) 예외·오류 상자가 없는지, (2) 필터를 바꾸면 화면의 지표·차트
데이터가 기본값과 달라지는지 본다. API 를 부르지 않는다 (Q&A 는 질문을 넣지 않으므로 호출 없음).

실행: python tests/check_dashboard_filters.py [--out 결과.md]
"""
import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
DASH = ROOT / "dashboard"
sys.path.insert(0, str(DASH))
from core.data import COMPANIES, KEYWORDS  # noqa: E402

PAGES = {"S0 요약": "s0_summary", "S1 이슈·트렌드": "s1_trend", "S2 규제·정책": "s2_policy",
         "S3 기술·생산": "s3_tech", "S4 기업 비교": "s4_compare", "S5 뉴스-공시 연계": "s5_linkage",
         "S6 공시 Q&A": "s6_qa"}
FULL = (date(2023, 10, 19), date(2026, 10, 19))
CASES = {
    "기본(전체)": dict(period=FULL, companies=COMPANIES, keywords=KEYWORDS),
    "기간 1개월(2026-09)": dict(period=(date(2026, 9, 1), date(2026, 9, 30)), companies=COMPANIES, keywords=KEYWORDS),
    "기간 1일(2025-05-22)": dict(period=(date(2025, 5, 22), date(2025, 5, 22)), companies=COMPANIES, keywords=KEYWORDS),
    **{f"기업 1개: {c}": dict(period=FULL, companies=[c], keywords=KEYWORDS) for c in COMPANIES},
    **{f"카테고리 1개: {k.removeprefix('CDMO ')}": dict(period=FULL, companies=COMPANIES, keywords=[k])
       for k in KEYWORDS},
    "기업 2개 + 카테고리 2개": dict(period=FULL, companies=["에스티팜", "바이넥스"],
                              keywords=["CDMO 수주", "CDMO 생산능력"]),
    "기업 0개": dict(period=FULL, companies=[], keywords=KEYWORDS),
    "카테고리 0개": dict(period=FULL, companies=COMPANIES, keywords=[]),
}
SCRIPT = """
import sys
sys.path.insert(0, {dash!r})
from views import {mod}
{mod}.render()
"""


def fingerprint(at: AppTest) -> dict:
    """화면 상태 요약: 지표 값, 차트 데이터 크기, 표 행 수, 안내 문구."""
    charts = []
    for el in at.get("plotly_chart"):
        try:
            spec = json.loads(el.proto.spec)
            charts.append(sum(len(t.get("x") or t.get("y") or t.get("z") or []) for t in spec.get("data", [])))
        except Exception:
            charts.append(-1)
    return {
        "metrics": [(m.label, m.value) for m in at.metric],
        "charts": charts,
        "tables": [len(el.value) if hasattr(el, "value") and el.value is not None else -1 for el in at.dataframe],
        "notes": [x.value[:60] for x in list(at.info) + list(at.warning)],
        "controls": [c.label for c in at.checkbox],     # S6 질문 범위 체크박스 문구 (기간·기업)
        "errors": [x.value[:120] for x in at.error],
        "exception": [str(x.value)[:200] for x in at.exception],
    }


def run(mod: str, filters: dict) -> dict:
    at = AppTest.from_string(SCRIPT.format(dash=str(DASH), mod=mod), default_timeout=120)
    at.session_state["filters"] = {"period": filters["period"], "companies": list(filters["companies"]),
                                   "keywords": list(filters["keywords"])}
    t0 = time.time()
    at.run()
    fp = fingerprint(at)
    fp["sec"] = round(time.time() - t0, 1)
    return fp


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, help="결과 표(마크다운)를 저장할 파일")
    args = ap.parse_args()
    rows, problems = [], []
    base = {name: run(mod, CASES["기본(전체)"]) for name, mod in PAGES.items()}
    for name, fp in base.items():
        if fp["exception"] or fp["errors"]:
            problems.append(f"{name} · 기본: {fp['exception'] or fp['errors']}")
    for case, filters in CASES.items():
        if case == "기본(전체)":
            continue
        for name, mod in PAGES.items():
            fp = run(mod, filters)
            ok = not fp["exception"] and not fp["errors"]
            changed = any(fp[k] != base[name][k] for k in ("metrics", "charts", "tables", "notes", "controls"))
            if not ok:
                problems.append(f"{name} · {case}: {fp['exception'] or fp['errors']}")
            rows.append((case, name, "오류" if not ok else ("반영" if changed else "변화 없음"),
                         "; ".join(f"{l} {v}" for l, v in fp["metrics"][:3]) or " / ".join(fp["notes"][:1])
                         or " / ".join(fp["controls"]) or "—"))
            print(f"{case:24} {name:14} {rows[-1][2]:6} {rows[-1][3][:70]}", flush=True)

    lines = ["| 필터 | 화면 | 결과 | 화면 지표(앞 3개) 또는 안내 |", "|---|---|---|---|"]
    lines += [f"| {c} | {n} | {r} | {m} |" for c, n, r, m in rows]
    summary = (f"\n화면 실행 {len(rows) + len(base)}회 · 오류 {len(problems)}건 · "
               f"변화 없음 {sum(r[2] == '변화 없음' for r in rows)}건")
    print(summary)
    for p in problems:
        print("  문제:", p)
    if args.out:
        args.out.write_text("\n".join(lines) + "\n" + summary + "\n" + "\n".join(f"- {p}" for p in problems),
                            encoding="utf-8")


if __name__ == "__main__":
    main()
