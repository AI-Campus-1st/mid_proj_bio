"""공시 유형별 가중치 정의와 기업별 가중 점수 산출.

가중치는 'CDMO 사업과의 직접성'으로 정한다 (0~5).
- 공시 1건마다 (분류, 가중치)를 붙여 data/processed/dart_disclosures_weighted.csv 로 저장
- 기업별 합계를 data/processed/company_weighted_score.csv 로 저장
실행: python analysis/disclosure_weights.py
"""
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "collect"))
from config import COMPANIES, RAW_DIR, ROOT  # noqa: E402

DART = RAW_DIR / "dart"

# (분류, 가중치, 적용 공시유형, 보고서명 패턴, 근거) — 위에서부터 처음 맞는 규칙을 적용한다.
RULES = [
    ("제외(거래정지)", 0, "I", r"매매거래정지",
     "다른 공시에 따른 절차 안내로, 원 공시와 중복된다"),
    ("수주", 5, "I", r"단일판매|공급계약|위탁생산|위탁제조",
     "CDMO 매출의 직접 원천. 거래소 규정상 매출액 대비 일정 비율 이상 계약만 공시 의무"),
    ("증설", 4, "I", r"신규시설투자|유형자산취득",
     "생산능력이 수주 상한을 정한다. 자기자본 대비 일정 비율 이상 투자만 공시 의무"),
    ("M&A·구조개편", 4, "BI", r"타법인주식및출자증권|회사분할|회사합병|영업양수|영업양도",
     "생산거점 인수·분할 등 사업 구조 변화 ('바이오 M&A' 키워드와 대응)"),
    ("실적", 3, "I", r"영업\(잠정\)실적|매출액또는손익구조|영업실적등에대한전망",
     "수주가 매출·이익으로 전환되는지 확인하는 결과 지표"),
    ("임상·허가·기술계약", 2, "I", r"투자판단관련주요경영사항",
     "산업 이슈이나 자체 파이프라인 사안으로, CDMO 본업과는 간접 관계"),
    ("자금조달", 2, "BI", r"유상증자결정|사채권발행결정",
     "증설 재원 ('바이오 투자 유치' 키워드와 대응). 사업 성과 자체는 아니다"),
    ("리스크", 0, "I", r"횡령|배임|불성실공시|회계처리기준위반|소송|조회공시|풍문",
     "선정 점수에는 넣지 않고 건수만 별도 표기한다"),
    ("정기보고서", 1, "A", r"사업보고서|반기보고서|분기보고서",
     "모든 상장사 공통이라 변별력은 낮으나 사업 내용의 기본 출처"),
    ("IR", 0, "I", r"기업설명회",
     "설명회 일정 안내일 뿐 사건이 아니며, 개최 횟수가 점수를 왜곡한다"),
]
DEFAULT = ("기타(지분·주총·행정)", 0, "지분 변동, 주주총회, 발행 절차 서류 등 사업 이슈와 무관하거나 중복")


def classify(ty: str, report_nm: str):
    for label, w, types, pat, _ in RULES:
        if ty in types and re.search(pat, report_nm):
            return label, w
    return DEFAULT[0], DEFAULT[1]


def revenue(corp_code: str):
    """2025 사업연도 매출액(억원). 연결이 있으면 연결, 없으면 별도."""
    f = DART / "fin" / f"{corp_code}_2025.json"
    if not f.exists():
        return ""
    amt = {x["fs_div"]: x["thstrm_amount"] for x in json.loads(f.read_text(encoding="utf-8")).get("list", [])
           if x["account_nm"] == "매출액"}
    v = amt.get("CFS") or amt.get("OFS")
    return round(int(v.replace(",", "")) / 1e8) if v else ""


def main():
    codes = json.loads((DART / "companies.json").read_text(encoding="utf-8"))
    rows, seen = [], set()
    for name, _, status in COMPANIES:
        for f in sorted(DART.glob(f"list/{codes[name]['corp_code']}_*.json")):
            ty = f.stem.split("_")[1]
            for r in json.loads(f.read_text(encoding="utf-8")).get("list", []):
                if r["rcept_no"] in seen:
                    continue
                seen.add(r["rcept_no"])
                nm = " ".join(r["report_nm"].split())
                # 정정 공시는 같은 사건의 반복이므로 점수에서 제외한다.
                amended = bool(re.match(r"\[(기재정정|첨부정정|첨부추가|정정명령부과)", nm))
                label, w = classify(ty, nm)
                rows.append({
                    "기업": name, "구분": status, "접수번호": r["rcept_no"],
                    "접수일": r["rcept_dt"], "공시유형": ty, "보고서명": nm,
                    "분류": label, "정정": int(amended), "가중치": 0 if amended else w,
                })

    out = ROOT / "data" / "processed"
    out.mkdir(parents=True, exist_ok=True)
    with (out / "dart_disclosures_weighted.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    labels = [r[0] for r in RULES if r[1] > 0] + ["리스크"]
    cnt = defaultdict(Counter)
    score = Counter()
    annual, unfaithful = Counter(), Counter()
    for r in rows:
        if r["정정"]:
            continue
        cnt[r["기업"]][r["분류"]] += 1
        score[r["기업"]] += r["가중치"]
        if r["공시유형"] == "A" and r["보고서명"].startswith("사업보고서"):
            annual[r["기업"]] += 1
        if re.match(r"불성실공시법인지정(?!예고)", r["보고서명"]):
            unfaithful[r["기업"]] += 1

    summary = []
    for name, _, status in COMPANIES:
        core = 5 * cnt[name]["수주"] + 4 * cnt[name]["증설"]
        # 자격 요건: 3년치 사업보고서 / 불성실공시법인 지정 없음 / 수주 공시 3건 이상
        fails = []
        if annual[name] < 3:
            fails.append(f"사업보고서 {annual[name]}건")
        if unfaithful[name]:
            fails.append(f"불성실공시법인 지정 {unfaithful[name]}회")
        if cnt[name]["수주"] < 3:
            fails.append(f"수주 공시 {cnt[name]['수주']}건")
        summary.append({"기업": name, "구분": status, "가중점수": score[name], "본업점수": core,
                        **{l: cnt[name][l] for l in labels},
                        "매출액_억": revenue(codes[name]["corp_code"]),
                        "자격": "통과" if not fails else "미달: " + ", ".join(fails)})
    summary.sort(key=lambda x: (x["자격"] != "통과", -x["가중점수"]))
    for i, s in enumerate(summary, 1):
        s["순위"] = i
    with (out / "company_weighted_score.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0]))
        w.writeheader()
        w.writerows(summary)

    print(" | ".join(summary[0]))
    for s in summary:
        print(" | ".join(str(v) for v in s.values()))


if __name__ == "__main__":
    main()
