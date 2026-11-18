"""수주 공시 계약 금액 추출 — S4 기업 비교의 "수주 금액 추이"(PRD F4, UI 명세 5-5절 S4-C3)에 쓴다.

대상: DB `disclosures` 중 event_class='수주' 인 공시(원공시·정정 모두)와 그 본문(disclosure_documents seq=1).
방식: 정규식. 단일판매ㆍ공급계약 공시는 금액이 정형 칸("계약금액 총액(원) | 91,332,435,000")으로 있어
      LLM 없이 뽑을 수 있다 (API 비용 없음, 결과를 사람이 전부 확인할 수 있는 규모 — 98건).
출력: data/processed/contract_amounts.csv (rcept_no 키). 대시보드는 이 파일만 읽는다 (PRD N1·N2).

금액 규칙과 근거
  1. "계약금액 총액(원) | N" 이 있으면 그 값 (마지막 것). 조건부 계약이 있으면 "확정 계약금액"·"조건부 계약금액"
     칸이 따로 있고 총액이 둘의 합이라, 총액이 계약 규모를 가장 잘 나타낸다.
  2. 없으면 "계약금액(원) | N" 의 마지막 값. 정정 공시는 앞쪽 정정표에 "계약금액 | 정정전 | 정정후" 가 있고,
     뒤에 정정 후 서식 전체가 다시 실린다. 그래서 마지막 값이 최신 금액이다. 정정표 행만 있으면 정정후 값을 쓴다.
  3. 금액이 없으면(투자판단 관련 주요경영사항 — 계약 금액 비공개, 계약 해지 공시) 빈칸으로 두고 note 에 이유를 쓴다.
정정 공시는 정정 대상 원공시의 제출일(original_date)도 뽑는다. 화면은 원공시에 최신 정정본 금액을 붙인다
(eda_report 5절: "금액 추이는 최신 정정본 기준").

실행
  python analysis/extract_contract_amounts.py           # 추출해 저장하고 요약 출력
  python analysis/extract_contract_amounts.py --check   # 저장하지 않고 요약만
"""
import argparse
import csv
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "collect"))
from config import DB_PATH  # noqa: E402

OUT = ROOT / "data" / "processed" / "contract_amounts.csv"
COLS = ["rcept_no", "corp_name", "rcept_date", "report_nm", "is_amended", "amount_krw", "amount_basis",
        "original_date", "counterparty", "note"]

QUERY = """
SELECT d.rcept_no, c.corp_name, d.rcept_date, d.report_nm, d.is_amended, COALESCE(x.text, '') AS text
FROM disclosures d
JOIN companies c ON c.corp_code = d.corp_code
LEFT JOIN disclosure_documents x ON x.rcept_no = d.rcept_no AND x.seq = 1
WHERE d.event_class = '수주'
ORDER BY d.rcept_date, d.rcept_no
"""

NUM = r"([\d,]{2,})"
TOTAL = re.compile(r"계약금액\s*총액\s*\(원\)\s*\|\s*" + NUM)
# "계약금액(원) | N" 또는 정정표 "계약금액 (원) | 정정전 | 정정후" (단위 표기가 없는 행도 있다)
AMOUNT = re.compile(r"계약금액\s*(?:\(원\))?\s*\|\s*" + NUM + r"(?:\s*\|\s*" + NUM + r")?")
# 원공시 제출일. 표기가 공시마다 다르다: "2019-11-28", "2022.03.17", "2022 년 3 월 17 일"
ORIGINAL = re.compile(r"(?:정정관련\s*공시서류\s*제출일|최초\s*제출일)\s*:?\s*\|?\s*"
                      r"(\d{4})\s*[년.-]\s*(\d{1,2})\s*[월.-]\s*(\d{1,2})")
COUNTERPARTY = re.compile(r"계약상대방?\s*\|\s*([^|\n]{2,40}?)\s*(?:\||\n|- 최근|-최근|$)")


def to_int(s: str) -> int:
    return int(s.replace(",", ""))


def extract(row: dict) -> dict:
    text = row["text"]
    out = {k: row[k] for k in ("rcept_no", "corp_name", "rcept_date", "report_nm", "is_amended")}
    out.update(amount_krw="", amount_basis="", original_date="", counterparty="", note="")
    if not text.strip():
        out["note"] = "원문 없음"
        return out
    totals = TOTAL.findall(text)
    amounts = AMOUNT.findall(text)
    if totals:
        out["amount_krw"], out["amount_basis"] = to_int(totals[-1]), "계약금액 총액"
    elif amounts:
        before, after = amounts[-1]
        out["amount_krw"] = to_int(after or before)
        out["amount_basis"] = "정정후" if after else "계약금액"
    elif "해지" in row["report_nm"]:
        out["note"] = "계약 해지 공시 (계약 금액 아님)"
    else:
        out["note"] = "금액 칸 없음 (계약 금액 비공개 공시)"
    if out["amount_krw"] == 0:
        out["amount_krw"], out["note"] = "", "금액 0 (추출 확인 필요)"
    if int(row["is_amended"]):
        m = ORIGINAL.search(text)
        if m:
            out["original_date"] = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = COUNTERPARTY.search(text)
    if m:
        out["counterparty"] = m.group(1).strip()
    return out


def run(db_path=None) -> list:
    con = sqlite3.connect(db_path or DB_PATH)
    con.row_factory = sqlite3.Row
    rows = [extract(dict(r)) for r in con.execute(QUERY)]
    con.close()
    return rows


def summary(rows: list) -> str:
    got = [r for r in rows if r["amount_krw"] != ""]
    lines = [f"수주 공시 {len(rows)}건 — 금액 추출 {len(got)}건, 미추출 {len(rows) - len(got)}건"]
    lines += [f"  근거: {k} {v}" for k, v in Counter(r["amount_basis"] for r in got).most_common()]
    amended = [r for r in rows if int(r["is_amended"])]
    lines.append(f"  정정 공시 {len(amended)}건 중 원공시 제출일을 찾은 것 {sum(1 for r in amended if r['original_date'])}건")
    lines.append("미추출:")
    lines += [f"  {r['rcept_date']} {r['corp_name']} {r['report_nm']} — {r['note']}" for r in rows if r["amount_krw"] == ""]
    big = sorted(got, key=lambda r: -r["amount_krw"])[:5]
    lines.append("금액 상위 5건 (억 원):")
    lines += [f"  {r['rcept_date']} {r['corp_name']} {r['amount_krw'] / 1e8:,.0f} ({r['report_nm']})" for r in big]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="저장하지 않고 요약만 출력")
    a = ap.parse_args()
    if not DB_PATH.exists():
        raise SystemExit(f"DB가 없습니다: {DB_PATH} — python db/build_db.py 로 먼저 만듭니다.")
    rows = run()
    print(summary(rows))
    if a.check:
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    print(f"저장: {OUT.relative_to(ROOT)} ({len(rows)}행)")


if __name__ == "__main__":
    main()
