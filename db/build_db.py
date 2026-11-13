"""뉴스·공시 통합 DB 구축 (data/db/bio_cdmo.sqlite).

수집된 원본만 읽어 DB를 처음부터 다시 만든다. API는 호출하지 않는다.
- 뉴스: 03_CDMO_news_3y/*묶음*.csv — 제공·팀원 수집·구글 뉴스 수집분을 합쳐 CDMO 키워드로
        재분류한 통합본 (analysis/build_cdmo_news.py 가 먼저 만들어 둔다)
- 공시 목록: data/raw/dart/list_selected/*.json
- 공시 원문: data/raw/dart/document/{rcept_no}.zip
모든 자료는 DB_START ~ DB_END (제공 뉴스 기간)로 맞춘다.
실행: python db/build_db.py
"""
import csv
import html
import json
import re
import sqlite3
import sys
import unicodedata
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "collect"))
sys.path.insert(0, str(ROOT / "analysis"))
from config import (CDMO_KEYWORDS, CDMO_OUT_DIR, CDMO_PATTERN, COMPANY_PATTERNS,  # noqa: E402
                    DB_END, DB_PATH, DB_START, KEYWORDS, PROVIDED_NEWS_DIR, RAW_DIR, SELECTED)
from disclosure_weights import classify  # noqa: E402

csv.field_size_limit(10 ** 9)
KST = timezone(timedelta(hours=9))
DART = RAW_DIR / "dart"
TYPE_NAMES = {"A": "정기공시", "B": "주요사항보고", "C": "발행공시", "D": "지분공시",
              "E": "기타공시", "F": "외부감사관련", "G": "펀드공시", "H": "자산유동화",
              "I": "거래소공시", "J": "공정위공시"}
PATS = {n: re.compile(p) for n, p in COMPANY_PATTERNS.items()}
CDMO = re.compile(CDMO_PATTERN)
DUP_DAYS = 7


def in_period(d: str) -> bool:
    return DB_START.isoformat() <= d <= DB_END.isoformat()


def norm_title(t: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", t)


# ---------------------------------------------------------------- 뉴스
def read_csv(path: Path) -> list:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_provided() -> list:
    """묶음 파일을 기준으로 읽는다. 파일명이 NFD일 수 있어 NFC로 맞춰 찾는다."""
    files = {unicodedata.normalize("NFC", p.name): p for p in PROVIDED_NEWS_DIR.glob("*.csv")}
    bundle = [p for n, p in files.items() if "묶음" in n]
    if len(bundle) != 1:
        raise SystemExit(f"묶음 CSV를 찾지 못했습니다: {list(files)}")
    rows = []
    for r in read_csv(bundle[0]):
        kws = [k.strip() for k in r["수집키워드"].split(";") if k.strip()]
        unknown = [k for k in kws if k not in KEYWORDS]
        if unknown:
            raise SystemExit(f"알 수 없는 키워드: {unknown}")
        rows.append({"origin": "provided", "title": " ".join(r["제목"].split()),
                     "body": r["본문전문"].strip() or None, "url": r["원문URL"].strip(),
                     "published_at": r["발행일"].strip(), "press": r["매체명"].strip(),
                     "keywords": kws, "query_company": set()})
    return rows


def load_google() -> list:
    """5개사 기업명 검색 뉴스. guid 기준으로 합치고 검색에 쓴 기업을 기록한다."""
    by_guid = {}
    for name in SELECTED:
        f = RAW_DIR / "news" / f"company_{name}.jsonl"
        for line in f.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if not r.get("pub_date") or not r.get("title"):
                continue
            at = datetime.fromisoformat(r["pub_date"]).astimezone(KST)
            title = r["title"]
            src = r.get("source") or ""
            while src and title.endswith(" - " + src):  # 구글 뉴스는 제목 끝에 매체명을 붙인다 (두 번 붙는 매체도 있다)
                title = title[: -len(src) - 3]
            row = by_guid.setdefault(r["guid"] or r["link"], {
                "origin": "google_rss", "title": " ".join(title.split()), "body": None,
                "url": r["link"], "published_at": at.strftime("%Y-%m-%dT%H:%M:%S"),
                "press": src, "keywords": [], "query_company": set()})
            row["query_company"].add(name)
    return list(by_guid.values())


ORIGINS = {"제공": "provided", "팀원수집": "team", "기업명검색": "google_company",
           "CDMO검색": "google_cdmo"}


def load_merged() -> list:
    """뉴스 통합본(03_CDMO_news_3y/*묶음*.csv, analysis/build_cdmo_news.py 산출물)을 읽는다."""
    files = {unicodedata.normalize("NFC", p.name): p for p in CDMO_OUT_DIR.glob("*.csv")}
    bundle = [p for n, p in files.items() if "묶음" in n]
    if len(bundle) != 1:
        raise SystemExit("뉴스 통합본이 없습니다. 먼저 python analysis/build_cdmo_news.py 를 실행하세요.")
    rows = []
    for r in read_csv(bundle[0]):
        origin = ORIGINS[r["수집출처"]]
        orig = [k.strip() for k in r["원수집키워드"].split(";") if k.strip()]
        cdmo = [k for k in r["수집키워드"].split("; ") if k in CDMO_KEYWORDS]
        rows.append({
            "origin": origin, "title": r["제목"], "body": r["본문전문"] or None,
            "url": r["원문URL"], "published_at": r["발행일"], "press": r["매체명"],
            "keywords": orig if origin == "provided" else [],
            "query_company": set(orig) & set(SELECTED) if origin != "provided" else set(),
            "search_terms": None if origin == "provided" else "; ".join(orig) or None,
            "cdmo_keywords": cdmo, "cdmo_primary": r["대표키워드"],
            "cdmo_rel_basis": r["CDMO관련근거"], "cdmo_kw_basis": r["키워드근거"]})
    return rows


def load_news(con, corp) -> None:
    rows = [r for r in load_merged() if in_period(r["published_at"][:10])]
    # 본문이 있는 출처를 먼저 넣어, 같은 제목이 겹치면 본문이 있는 쪽이 대표가 되게 한다.
    order = list(ORIGINS.values())
    rows.sort(key=lambda r: (order.index(r["origin"]), r["published_at"], r["url"]))
    canon = {}  # title_norm -> [(date, news_id)] 대표 기사
    for i, r in enumerate(rows, 1):
        d = r["published_at"][:10]
        tn = norm_title(r["title"])
        dup = None
        if len(tn) >= 8:
            for cd, cid in canon.get(tn, []):
                if abs((date.fromisoformat(d) - date.fromisoformat(cd)).days) <= DUP_DAYS:
                    dup = cid
                    break
            if dup is None:
                canon.setdefault(tn, []).append((d, i))
        text = r["title"] + " " + (r["body"] or "")
        con.execute("INSERT INTO news VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (i, r["origin"], r["title"], r["body"], r["url"], r["published_at"], d,
                     r["press"], len(r["body"] or ""), int(bool(CDMO.search(text))), tn, dup,
                     r["search_terms"], r["cdmo_rel_basis"], r["cdmo_kw_basis"]))
        for kw in r["keywords"]:
            con.execute("INSERT INTO news_keywords VALUES (?,?,?)", (i, kw, KEYWORDS[kw]))
        for kw in r["cdmo_keywords"]:
            con.execute("INSERT INTO news_cdmo_keywords VALUES (?,?,?,?)",
                        (i, kw, CDMO_KEYWORDS[kw], int(kw == r["cdmo_primary"])))
        for name, pat in PATS.items():
            if pat.search(r["title"]):
                field = "title"
            elif r["body"] and pat.search(r["body"]):
                field = "body"
            elif name in r["query_company"]:
                field = "query"
            else:
                continue
            con.execute("INSERT INTO news_companies VALUES (?,?,?)", (i, corp[name], field))


# ---------------------------------------------------------------- 공시
BLOCK_END = re.compile(
    r"</(?:p|tr|table|title|div|li|h\d|section-\d|cover-title|library)\s*>|<br\s*/?>|<pgbrk[^>]*>",
    re.I)
CELL_END = re.compile(r"</(?:td|th|te|tu)\s*>", re.I)


def to_text(raw: bytes) -> str:
    """DART 원문(XML/HTML)에서 태그를 걷어낸다. 표는 행=줄, 칸=' | ' 로 남긴다."""
    try:
        s = raw.decode("utf-8")
    except UnicodeDecodeError:
        s = raw.decode("cp949", "replace")
    s = re.sub(r"<(style|script)\b.*?</\1\s*>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<!--.*?-->", " ", s, flags=re.S)
    s = s.replace("\r", " ").replace("\n", " ")
    s = CELL_END.sub(" | ", s)
    s = BLOCK_END.sub("\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s).replace("\xa0", " ")
    lines = []
    for ln in s.split("\n"):
        ln = re.sub(r"[ \t　]+", " ", ln).strip()
        ln = re.sub(r"(?:\s*\|)+\s*$", "", ln).strip()  # 행 끝의 빈 칸 구분자 제거
        if ln and ln != "|":
            lines.append(ln)
    return "\n".join(lines)


def load_disclosures(con, corp) -> None:
    codes = set(corp.values())
    seen = set()
    for f in sorted((DART / "list_selected").glob("*_*_*.json")):
        ty = f.stem.split("_")[1]
        for r in json.loads(f.read_text(encoding="utf-8")).get("list", []):
            d = f"{r['rcept_dt'][:4]}-{r['rcept_dt'][4:6]}-{r['rcept_dt'][6:]}"
            if r["rcept_no"] in seen or r["corp_code"] not in codes or not in_period(d):
                continue
            seen.add(r["rcept_no"])
            nm = " ".join(r["report_nm"].split())
            amended = bool(re.match(r"\[(기재정정|첨부정정|첨부추가|정정명령부과)", nm))
            label, w = classify(ty, nm)
            con.execute("UPDATE companies SET corp_cls = ? WHERE corp_code = ?",
                        (r.get("corp_cls"), r["corp_code"]))
            con.execute("INSERT INTO disclosures VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0,0)",
                        (r["rcept_no"], r["corp_code"], d, nm, ty, TYPE_NAMES[ty], r.get("flr_nm"),
                         (r.get("rm") or "").strip() or None, int(amended), label,
                         0 if amended else w,
                         f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={r['rcept_no']}"))
    for no in sorted(seen):
        z = DART / "document" / f"{no}.zip"
        if not z.exists():
            continue
        total = seq = 0
        with zipfile.ZipFile(z) as zf:
            for n in sorted(zf.namelist(), key=lambda n: (Path(n).stem != no, n)):  # 본문 먼저
                text = to_text(zf.read(n))
                if not text:
                    continue
                seq += 1
                total += len(text)
                con.execute("INSERT INTO disclosure_documents VALUES (?,?,?,?,?)",
                            (no, seq, n, text, len(text)))
        con.execute("UPDATE disclosures SET has_document = ?, doc_chars = ? WHERE rcept_no = ?",
                    (int(total > 0), total, no))


# ---------------------------------------------------------------- main
def main():
    codes = json.loads((DART / "companies.json").read_text(encoding="utf-8"))
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = DB_PATH.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    con.executescript((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))
    corp = {}
    for name in SELECTED:
        corp[name] = codes[name]["corp_code"]
        con.execute("INSERT INTO companies VALUES (?,?,?,NULL,'CDMO')",
                    (corp[name], name, codes[name]["stock_code"]))
    load_news(con, corp)
    load_disclosures(con, corp)
    for k, v in {"period_start": DB_START.isoformat(), "period_end": DB_END.isoformat(),
                 "built_at": datetime.now(KST).strftime("%Y-%m-%dT%H:%M:%S"),
                 "dup_rule": f"정규화 제목 동일 & {DUP_DAYS}일 이내"}.items():
        con.execute("INSERT INTO meta VALUES (?,?)", (k, v))
    con.commit()
    con.execute("VACUUM")
    con.close()
    tmp.replace(DB_PATH)  # 끝까지 성공했을 때만 기존 DB를 교체한다

    con = sqlite3.connect(DB_PATH)
    print(f"DB: {DB_PATH}  ({DB_START} ~ {DB_END})")
    for t in ("companies", "news", "news_keywords", "news_cdmo_keywords", "news_companies", "disclosures",
              "disclosure_documents"):
        print(f"  {t}: {con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]}")
    con.close()


if __name__ == "__main__":
    main()
