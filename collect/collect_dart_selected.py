"""분석 대상 5개사의 DART 공시 목록 + 공시 원문 수집 (제공 뉴스와 동일 기간).

1) 공시검색(list.json)        → data/raw/dart/list_selected/{corp_code}_{유형}_{page}.json
2) 공시서류원본파일(document.xml) → data/raw/dart/document/{rcept_no}.zip
   원문이 없는 공시는 data/raw/dart/document/_missing.json 에 사유를 남긴다.

응답 원본을 그대로 저장하고, 이미 받은 파일은 건너뛰므로 재실행 가능하다.
텍스트 추출과 DB 적재는 db/build_db.py 에서 한다.
실행: python collect/collect_dart_selected.py [list|doc|all]
"""
import json
import sys
import time
import urllib.parse

from collect_dart_list import API, DELAY, TYPES, get, load_corp_codes
from config import DB_END, DB_START, RAW_DIR, SELECTED, load_env

OUT = RAW_DIR / "dart"
LIST_DIR = OUT / "list_selected"
DOC_DIR = OUT / "document"
MISSING = DOC_DIR / "_missing.json"


def collect_list(key: str, codes: dict) -> list:
    """5개사 × 공시 유형별 목록. 반환: 접수번호 목록(중복 제거)."""
    LIST_DIR.mkdir(parents=True, exist_ok=True)
    meta = {"bgn_de": DB_START.strftime("%Y%m%d"), "end_de": DB_END.strftime("%Y%m%d")}
    mf = LIST_DIR / "_period.json"
    if mf.exists() and json.loads(mf.read_text(encoding="utf-8")) != meta:
        raise SystemExit(f"{LIST_DIR} 의 기존 수집 기간이 현재 설정과 다릅니다. 폴더를 비우고 다시 실행하세요.")
    mf.write_text(json.dumps(meta), encoding="utf-8")

    rcept = []
    for name in SELECTED:
        code = codes[name]["corp_code"]
        n = 0
        for ty in TYPES:
            page = 1
            while True:
                f = LIST_DIR / f"{code}_{ty}_{page}.json"
                if f.exists():
                    data = json.loads(f.read_text(encoding="utf-8"))
                else:
                    q = urllib.parse.urlencode({
                        "crtfc_key": key, "corp_code": code, **meta,
                        "pblntf_ty": ty, "page_no": page, "page_count": 100,
                    })
                    data = json.loads(get(f"{API}/list.json?{q}"))
                    time.sleep(DELAY)
                    if data.get("status") not in ("000", "013"):
                        raise SystemExit(f"DART 오류 {data.get('status')}: {data.get('message')}")
                    f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                for r in data.get("list", []):
                    rcept.append(r["rcept_no"])
                    n += 1
                if page >= int(data.get("total_page", 1)):
                    break
                page += 1
        print(f"목록 완료: {name} {n}건", flush=True)
    return list(dict.fromkeys(rcept))


def collect_docs(key: str, rcept: list):
    DOC_DIR.mkdir(parents=True, exist_ok=True)
    missing = json.loads(MISSING.read_text(encoding="utf-8")) if MISSING.exists() else {}
    got = skipped = 0
    for i, no in enumerate(rcept, 1):
        f = DOC_DIR / f"{no}.zip"
        if f.exists() or no in missing:
            skipped += 1
            continue
        raw = get(f"{API}/document.xml?crtfc_key={key}&rcept_no={no}")
        time.sleep(DELAY)
        if raw[:2] == b"PK":
            f.write_bytes(raw)
            got += 1
        else:  # 오류는 XML(<status>, <message>)로 온다
            text = raw.decode("utf-8", "replace")
            status = (text.split("<status>")[1].split("</status>")[0]
                      if "<status>" in text else "?")
            if status == "020":  # 요청 제한 초과: 기록하지 않고 중단 → 나중에 이어서 실행
                raise SystemExit("DART 요청 제한 초과(020). 잠시 후 다시 실행하세요.")
            missing[no] = {"status": status, "body": text[:200]}
            MISSING.write_text(json.dumps(missing, ensure_ascii=False, indent=1), encoding="utf-8")
        if i % 50 == 0:
            print(f"  원문 {i}/{len(rcept)}", flush=True)
    print(f"원문 완료: 신규 {got}건, 기존 {skipped}건, 원문 없음 {len(missing)}건")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    key = load_env("DART_OPEN_API")
    codes = load_corp_codes(key)
    rcept = collect_list(key, codes)
    print(f"공시 {len(rcept)}건 ({DB_START} ~ {DB_END})")
    if mode in ("doc", "all"):
        collect_docs(key, rcept)


if __name__ == "__main__":
    main()
