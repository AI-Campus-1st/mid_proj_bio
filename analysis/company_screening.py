"""기업 선정 정량 기준 집계 (Q1 공시 가용성, Q3 이벤트 공시 밀도, Q4 뉴스 노출량).

수집된 원본(data/raw)을 읽어 data/processed/company_screening.csv 로 저장한다.
실행: python analysis/company_screening.py
"""
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "collect"))
from config import COMPANIES, NEWS_ALIASES, RAW_DIR, ROOT  # noqa: E402

DART = RAW_DIR / "dart"
NEWS = RAW_DIR / "news"


def dart_stats(corp_code: str) -> dict:
    by_type, seen, dates = Counter(), set(), []
    annual = supply = invest = 0
    for f in DART.glob(f"list/{corp_code}_*.json"):
        ty = f.stem.split("_")[1]
        for r in json.loads(f.read_text(encoding="utf-8")).get("list", []):
            if r["rcept_no"] in seen:
                continue
            seen.add(r["rcept_no"])
            by_type[ty] += 1
            dates.append(r["rcept_dt"])
            nm = r["report_nm"]
            if ty == "A" and "사업보고서" in nm and "정정" not in nm:
                annual += 1
            if "단일판매" in nm:
                supply += 1
            if "투자판단" in nm:
                invest += 1
    return {
        "공시_전체": len(seen),
        "정기(A)": by_type["A"],
        "주요사항(B)": by_type["B"],
        "거래소(I)": by_type["I"],
        "사업보고서": annual,
        "공급계약": supply,
        "투자판단": invest,
        "첫_공시일": min(dates) if dates else "",
    }


def load_news():
    """링크 기준으로 중복을 제거한 (kind, name, title, month) 목록."""
    rows, seen = [], set()
    for f in NEWS.glob("*.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            key = (r["kind"], r["name"], r["guid"] or r["link"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(r)
    return rows


def main():
    codes = json.loads((DART / "companies.json").read_text(encoding="utf-8"))
    news = load_news()
    kw_titles = {r["guid"]: r["title"] or "" for r in news if r["kind"] == "keyword"}
    comp = defaultdict(dict)  # name -> guid -> month
    for r in news:
        if r["kind"] == "company":
            comp[r["name"]][r["guid"]] = (r["pub_date"] or "")[:7]

    out = []
    for name, field, status in COMPANIES:
        row = {"기업": name, "분야": field, "구분": status,
               "종목코드": codes[name]["stock_code"]}
        row.update(dart_stats(codes[name]["corp_code"]))
        months = Counter(comp[name].values())
        row["기업뉴스"] = len(comp[name])
        row["월평균"] = round(len(comp[name]) / 36, 1)
        row["월_최소"] = min(months.values()) if len(months) >= 36 else 0
        pat = re.compile("|".join(map(re.escape, NEWS_ALIASES.get(name, [name]))))
        row["키워드뉴스_언급"] = sum(1 for t in kw_titles.values() if pat.search(t))
        out.append(row)

    dst = ROOT / "data" / "processed" / "company_screening.csv"
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)

    print(f"키워드 뉴스 {len(kw_titles)}건 (중복 제거)")
    print(" | ".join(out[0]))
    for r in out:
        print(" | ".join(str(v) for v in r.values()))


if __name__ == "__main__":
    main()
