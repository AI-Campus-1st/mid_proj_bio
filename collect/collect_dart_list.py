"""DART 공시 목록 수집 (후보 기업 × 공시 유형).

- corpCode.xml로 corp_code를 찾고, list.json을 공시 유형별로 호출한다.
- 응답 원본을 data/raw/dart/list/ 에 저장한다. 이미 저장된 파일은 건너뛰므로 재실행 가능.
실행: python collect/collect_dart_list.py
"""
import io
import json
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

from config import COMPANIES, RAW_DIR, load_env
from config import DB_END as END, DB_START as START  # 제공 뉴스와 같은 기간

API = "https://opendart.fss.or.kr/api"
# A 정기공시, B 주요사항보고, C 발행공시, D 지분공시, E 기타공시,
# F 외부감사, G 펀드, H 자산유동화, I 거래소공시, J 공정위공시
TYPES = "ABCDEFGHIJ"
DELAY = 0.3
OUT = RAW_DIR / "dart"


def get(url: str) -> bytes:
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read()
        except Exception as e:  # 네트워크 오류는 잠시 후 재시도
            if attempt == 3:
                raise
            print(f"  재시도({attempt + 1}): {type(e).__name__}", file=sys.stderr)
            time.sleep(3 * (attempt + 1))


def load_corp_codes(key: str) -> dict:
    """회사명 → {corp_code, stock_code} (상장사만)."""
    path = OUT / "corpCode.xml"
    if not path.exists():
        z = zipfile.ZipFile(io.BytesIO(get(f"{API}/corpCode.xml?crtfc_key={key}")))
        path.write_bytes(z.read(z.namelist()[0]))
    out = {}
    for el in ET.parse(path).getroot().iter("list"):
        stock = (el.findtext("stock_code") or "").strip()
        if stock:
            out[el.findtext("corp_name").strip()] = {
                "corp_code": el.findtext("corp_code"),
                "stock_code": stock,
            }
    return out


def main():
    key = load_env("DART_OPEN_API")
    (OUT / "list").mkdir(parents=True, exist_ok=True)
    codes = load_corp_codes(key)

    found = {}
    for name, _, _ in COMPANIES:
        if name in codes:
            found[name] = codes[name]
        else:
            near = [n for n in codes if name[:4] in n][:5]
            print(f"[미발견] {name} / 유사: {near}")
    (OUT / "companies.json").write_text(
        json.dumps(found, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    for name, info in found.items():
        for ty in TYPES:
            page = 1
            while True:
                f = OUT / "list" / f"{info['corp_code']}_{ty}_{page}.json"
                if f.exists():
                    data = json.loads(f.read_text(encoding="utf-8"))
                else:
                    q = urllib.parse.urlencode({
                        "crtfc_key": key,
                        "corp_code": info["corp_code"],
                        "bgn_de": START.strftime("%Y%m%d"),
                        "end_de": END.strftime("%Y%m%d"),
                        "pblntf_ty": ty,
                        "page_no": page,
                        "page_count": 100,
                    })
                    data = json.loads(get(f"{API}/list.json?{q}"))
                    time.sleep(DELAY)
                    # 000 정상, 013 조회 결과 없음. 그 외는 저장하지 않고 중단한다.
                    if data.get("status") not in ("000", "013"):
                        raise SystemExit(f"DART 오류 {data.get('status')}: {data.get('message')}")
                    f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                if page >= int(data.get("total_page", 1)):
                    break
                page += 1
        print(f"완료: {name} ({info['stock_code']})")


if __name__ == "__main__":
    main()
