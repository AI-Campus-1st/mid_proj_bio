"""DART 주요계정(매출액 등) 수집 — 2025 사업연도 사업보고서 기준.

응답 원본을 data/raw/dart/fin/ 에 저장한다. 이미 저장된 파일은 건너뛴다.
실행: python collect/collect_dart_fin.py
"""
import json
import time
import urllib.parse
import urllib.request

from config import COMPANIES, RAW_DIR, load_env

YEAR = 2025
OUT = RAW_DIR / "dart"


def main():
    key = load_env("DART_OPEN_API")
    (OUT / "fin").mkdir(parents=True, exist_ok=True)
    codes = json.loads((OUT / "companies.json").read_text(encoding="utf-8"))
    for name, _, _ in COMPANIES:
        f = OUT / "fin" / f"{codes[name]['corp_code']}_{YEAR}.json"
        if not f.exists():
            q = urllib.parse.urlencode({"crtfc_key": key, "corp_code": codes[name]["corp_code"],
                                        "bsns_year": YEAR, "reprt_code": "11011"})
            with urllib.request.urlopen(
                    f"https://opendart.fss.or.kr/api/fnlttSinglAcnt.json?{q}", timeout=60) as r:
                data = json.loads(r.read())
            if data.get("status") not in ("000", "013"):
                raise SystemExit(f"DART 오류 {data.get('status')}: {data.get('message')}")
            f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            time.sleep(0.3)
        data = json.loads(f.read_text(encoding="utf-8"))
        rev = [(x["fs_div"], x["thstrm_amount"]) for x in data.get("list", [])
               if x["account_nm"] == "매출액"]
        print(name, rev)


if __name__ == "__main__":
    main()
