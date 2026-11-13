"""CDMO 키워드 재분류 + 뉴스 통합본 생성 (03_CDMO_news_3y/).

대상 (모두 제공 뉴스 기간 DB_START~DB_END)
  1) 제공 뉴스 전체            02_BIO_news_3y/*묶음*.csv
  2) 5개사 기업명 검색 뉴스     data/raw/news/company_*.jsonl      (기존 수집)
  3) CDMO 키워드 검색 뉴스      data/raw/news_cdmo/*.jsonl         (추가 수집, 제목만)
  4) 팀원 수집 뉴스             data/raw/cdmo_*.csv                (규제·투자유치, 본문 있음)
겹치는 기사(같은 링크, 또는 정규화 제목이 같은 기사)는 한 건만 남긴다.
우선순위는 제공 > 팀원 수집 > 기업명 검색 > CDMO 검색이다. 본문이 있는 쪽을 남기기 위해서다.

재분류는 규칙 기반이다 (LLM 호출 없음, 재실행하면 같은 결과).
  - CDMO 관련성: CDMO 표현·CDMO 기업명이 제목에 있거나 본문에 3회 이상 → 관련
  - 키워드: 제목에 키워드 표현이 있으면 그 키워드(+본문 5회 이상 언급된 키워드),
            제목에 없으면 본문 3회 이상 언급된 키워드 중 상위 2개 (복수 가능)
  - CDMO 검색으로 수집했는데 제목만으로 판정이 안 되면 검색에 쓴 키워드를 따른다 (근거 'query')
실행: python analysis/build_cdmo_news.py
"""
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "collect"))
sys.path.insert(0, str(ROOT / "db"))
from build_db import KST, in_period, load_google, load_provided, norm_title  # noqa: E402
from config import (CDMO_KEYWORDS, CDMO_NEWS_DIR, CDMO_OUT_DIR, DB_END, DB_START,  # noqa: E402
                    RAW_DIR)

# CDMO 관련 기사인지 가르는 표현: 업종 용어 + CDMO가 주력인 국내외 기업
GATE = re.compile(
    r"CDMO|(?<![A-Za-z])CMO(?![A-Za-z])|(?<![A-Za-z])CDO(?![A-Za-z])"
    r"|위탁개발생산|위탁생산|위탁개발|위탁제조|수탁생산"
    r"|삼성바이오로직스|삼성바이오(?!에피스)|삼바(?![가-힣])|롯데바이오로직스|셀트리온바이오솔루션스"
    r"|SK팜테코|에스티팜|바이넥스|프레스티지바이오로직스|에스티젠바이오|마티카"
    r"|론자|우시|후지필름|캐털런트")

# 키워드별 정규식 (조에서 정한 '주요 이슈'를 기사 표현으로 옮긴 것)
RULES = {
    "CDMO 규제·정책": r"특별법|바이오위원회|GMP|실사|품질관리|규제|식약처|식품의약품안전처|법안|입법|국회"
                    r"|지원법|육성법|경고서한|워닝레터|인허가",
    "CDMO 지정학": r"생물보안법|바이오보안법|관세|현지\s?생산|미국\s?공장|미국 내 생산|트럼프|미중|탈중국"
                  r"|리쇼어링|온쇼어링|공급망|지정학",
    "CDMO 모달리티": r"ADC|항체.?약물.?접합체|세포.?유전자|CGT|mRNA|올리고|이중항체|AAV|벡터|CAR-?T"
                   r"|펩타이드|모달리티|항체의약품|오가노이드|플라스미드|줄기세포",
    "CDMO 생산능력": r"증설|착공|준공|신공장|\d공장|공장\s?(?:건설|건립|인수|매입)|생산능력|캐파|CAPA"
                   r"|만\s?ℓ|만\s?리터|플랜트|캠퍼스|정책금융|시설투자|설비투자|부지|생산시설|생산거점",
    "CDMO 수주": r"수주|공급계약|위탁생산\s?계약|계약\s?체결|계약을 체결|빅파마|고객사|실적|매출|영업이익"
                r"|흑자|적자|어닝",
    "CDMO 경쟁 구도": r"인수|M&A|합병|진출|출사표|론자|우시|후지필름|캐털런트|써모피셔|경쟁|점유율"
                    r"|신규 진입|출범|뛰어들|도전장|분할",
}
RULES = {k: re.compile(v) for k, v in RULES.items()}
assert list(RULES) == list(CDMO_KEYWORDS)
NONE = "해당 없음"
BODY_GATE_MIN, BODY_RULE_MIN, BODY_STRONG, BODY_TOP = 3, 3, 5, 2


def load_cdmo_raw() -> list:
    """추가 수집 원본을 기사 단위(guid)로 합친다."""
    by_guid = {}
    for f in sorted(CDMO_NEWS_DIR.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if not r.get("pub_date") or not r.get("title"):
                continue
            at = datetime.fromisoformat(r["pub_date"]).astimezone(KST)
            title, src = r["title"], r.get("source") or ""
            while src and title.endswith(" - " + src):  # 매체명이 두 번 붙는 매체도 있다
                title = title[: -len(src) - 3]
            row = by_guid.setdefault(r["guid"] or r["link"], {
                "origin": "CDMO검색", "title": " ".join(title.split()), "body": None,
                "url": r["link"], "published_at": at.strftime("%Y-%m-%dT%H:%M:%S"),
                "press": src, "keywords": [], "query_kw": []})
            if r["name"] not in row["query_kw"]:
                row["query_kw"].append(r["name"])
    return [r for r in by_guid.values() if in_period(r["published_at"][:10])]


def load_team() -> list:
    """팀원이 올린 CSV(제공 뉴스와 같은 컬럼). 같은 링크는 합치고 수집 검색어를 모은다."""
    by_url = {}
    for f in sorted(RAW_DIR.glob("cdmo_*.csv")):
        with f.open(encoding="utf-8-sig", newline="") as fp:
            for x in csv.DictReader(fp):
                at = x["발행일"].strip().replace(" ", "T")
                row = by_url.setdefault(x["원문URL"].strip(), {
                    "origin": "팀원수집", "title": " ".join(x["제목"].split()),
                    "body": chr(10).join(x["본문전문"].splitlines()).strip() or None,
                    "url": x["원문URL"].strip(), "published_at": at,
                    "press": x["매체명"].strip(), "keywords": []})
                for k in x["수집키워드"].split(","):
                    if k.strip() and k.strip() not in row["keywords"]:
                        row["keywords"].append(k.strip())
    return [r for r in by_url.values() if in_period(r["published_at"][:10])]


def classify(r: dict):
    """반환: (키워드 목록, 대표 키워드, CDMO 관련 근거, 키워드 근거)"""
    title, body = r["title"], r["body"] or ""
    by_query = bool(r.get("query_kw"))
    if GATE.search(title):
        rel = "title"
    elif len(GATE.findall(body)) >= BODY_GATE_MIN:
        rel = "body"
    elif by_query:
        rel = "query"
    else:
        return [], NONE, "none", "none"
    hit_t = {kw: len(pat.findall(title)) for kw, pat in RULES.items()}
    hit_b = {kw: len(pat.findall(body)) for kw, pat in RULES.items()}
    if any(hit_t.values()):
        # 제목에 나온 키워드를 따르고, 본문에서 반복해 다룬 키워드만 더한다
        score = {kw: 100 * hit_t[kw] + hit_b[kw] for kw in RULES
                 if hit_t[kw] or hit_b[kw] >= BODY_STRONG}
    else:
        # 본문만 일치하면 많이 언급된 상위 2개까지만 붙인다 (긴 기사의 과다 분류 방지)
        top = sorted((kw for kw in RULES if hit_b[kw] >= BODY_RULE_MIN),
                     key=lambda k: -hit_b[k])[:BODY_TOP]
        score = {kw: hit_b[kw] for kw in top}
    if not score:
        if by_query:  # 제목만으로는 판정 불가 → 검색에 쓴 키워드
            return r["query_kw"], r["query_kw"][0], rel, "query"
        return [], NONE, rel, "none"  # CDMO 언급은 있으나 6개 이슈에 해당하지 않음
    kws = [k for k in RULES if k in score]
    return kws, max(kws, key=lambda k: score[k]), rel, "title" if any(hit_t.values()) else "body"


def main():
    dropped = Counter()
    kept, by_title, urls = [], {}, set()

    def add(r, label):
        """우선순위 순서로 넣는다. 먼저 들어온 기사와 겹치면 버리고 사유를 센다."""
        tn = norm_title(r["title"])
        prev = by_title.get(tn) if len(tn) >= 8 else None
        if r["url"] in urls or prev is not None:
            if prev is not None and prev["origin"] == "팀원수집":
                # 본문이 있는 팀원 기사가 남는다. 검색 정보만 넘겨 분류에 쓴다
                for k in ("query_kw", "query_company"):
                    if r.get(k):
                        prev[k] = list(dict.fromkeys(list(prev.get(k, [])) + list(r[k])))
            dropped[f"{label}: {prev['origin'] if prev else r['origin']}와 중복"] += 1
            return
        urls.add(r["url"])
        if len(tn) >= 8:
            by_title[tn] = r
        kept.append(r)

    for r in load_provided():  # 제공 뉴스는 겹쳐도 전부 유지한다
        r = {**r, "origin": "제공"}
        urls.add(r["url"])
        by_title.setdefault(norm_title(r["title"]), r)
        kept.append(r)
    team = sorted(load_team(), key=lambda r: (r["published_at"], r["url"]))
    for r in team:
        add(r, "팀원수집")
    for r in sorted(load_google(), key=lambda r: (r["published_at"], r["url"])):
        if in_period(r["published_at"][:10]):
            add({**r, "origin": "기업명검색"}, "기업명검색")
    raw = load_cdmo_raw()
    for r in sorted(raw, key=lambda r: (r["published_at"], r["url"])):
        add(r, "CDMO검색")

    cols = ["제목", "본문전문", "원문URL", "발행일", "매체명", "문서종류", "수집키워드",
            "대표키워드", "카테고리", "CDMO관련근거", "키워드근거", "원수집키워드", "수집출처"]
    out = []
    for r in kept:
        kws, main_kw, rel, basis = classify(r)
        out.append({
            "제목": r["title"], "본문전문": r["body"] or "", "원문URL": r["url"],
            "발행일": r["published_at"], "매체명": r["press"], "문서종류": "news",
            "수집키워드": "; ".join(kws) or NONE, "대표키워드": main_kw,
            "카테고리": CDMO_KEYWORDS.get(main_kw, ""), "CDMO관련근거": rel, "키워드근거": basis,
            "원수집키워드": "; ".join(r.get("keywords") or r.get("query_kw", [])
                                 or sorted(r.get("query_company", []))),
            "수집출처": r["origin"]})
    out.sort(key=lambda x: (x["발행일"], x["원문URL"]))

    CDMO_OUT_DIR.mkdir(exist_ok=True)
    for f in CDMO_OUT_DIR.glob("03_CDMO_*.csv"):  # 건수가 파일명에 들어가므로 이전 산출물을 지운다
        f.unlink()
    period = f"{DB_START}~{DB_END}"

    def write(name, rows):
        with (CDMO_OUT_DIR / name).open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)

    write(f"03_CDMO_묶음_CDMO_{len(out)}건_{period}.csv", out)
    for kw in CDMO_KEYWORDS:
        rows = [x for x in out if kw in x["수집키워드"].split("; ")]
        short = kw.replace("CDMO ", "CDMO").replace(" ", "").replace("·", "")
        write(f"03_CDMO_키워드_{short}_{len(rows)}건_{period}.csv", rows)

    print(f"기간 내 원본: 팀원수집 {len(team)}건, CDMO검색 {len(raw)}건")
    print("제외:", dict(dropped))
    print(f"통합본 {len(out)}건:", dict(Counter(x['수집출처'] for x in out)))
    print("키워드(복수 포함) | 전체 | 제공 | 팀원수집 | 기업명검색 | CDMO검색")
    for kw in list(CDMO_KEYWORDS) + [NONE]:
        c = Counter(x["수집출처"] for x in out if kw in x["수집키워드"].split("; "))
        print(f"  {kw} | {sum(c.values())} | {c['제공']} | {c['팀원수집']} | {c['기업명검색']} | {c['CDMO검색']}")
    print("CDMO관련근거 × 키워드근거:")
    for k, v in sorted(Counter((x["수집출처"], x["CDMO관련근거"], x["키워드근거"]) for x in out).items()):
        print("  ", *k, v)


if __name__ == "__main__":
    main()
