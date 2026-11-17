"""뉴스-공시 매칭 (M1) — 기사마다 같은 기업·인접 시점·대응 주제의 공시를 연결한다.

통합 DB(data/db/bio_cdmo.sqlite)를 읽는다. API·LLM은 호출하지 않는다.
규칙의 근거와 한계는 docs/04_ai/NEWS_DISCLOSURE_MATCHING.md 3절에 있다.

연결 조건 (셋 다 만족)
  1) 같은 기업 — news_companies.match_field 가 title·body 인 기업 = 공시의 corp_code
  2) 시점 창   — day_gap = 공시 접수일 − 기사 발행일
                  direct: −DIRECT_BEFORE ~ +DIRECT_AFTER 일 (같은 사건)
                  follow: 그 뒤 ~ +FOLLOW_AFTER 일 (이후의 사업 활동. 인과가 아니라 선후 관계)
  3) 주제 대응 — 기사의 CDMO 키워드와 공시의 event_class 가 TOPIC_MAP 에서 대응
                  리스크 공시는 direct 창이면 키워드와 무관하게 연결한다

기사 기준
  - 중복 기사(dup_of 있음)는 뺀다.
  - 기업 연결이 query 뿐인 기사는 뺀다 (기업명 검색에 걸렸지만 제목·본문에 기업명이 없음).
공시 기준
  - 사건성 공시(MATCH_CLASSES)만 쓴다. 정기보고서·IR·기타·거래정지는 뺀다.
  - 정정 공시는 빼지 않고 is_amended=1 로 표시한다 (최신 계약 내용이 정정 공시에 있다).

실행: python analysis/match_news_disclosure.py
결과: data/processed/news_disclosure_links.csv (기사 × 기업 × 공시 = 1행)
"""
import os
import sqlite3
import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "collect"))
from config import DB_END, DB_PATH  # noqa: E402

OUT = Path(os.environ.get("NEWS_DISC_LINKS_OUT", ROOT / "data" / "processed" / "news_disclosure_links.csv"))

# ---------------------------------------------------------------- 설정
# 시점 창(일). 검증 전 가설이다 — 수주 공시 주변 기사 분포로 확인한 뒤 확정한다 (문서 3-2절).
DIRECT_BEFORE = 7    # 기사보다 며칠 먼저 접수된 공시까지 direct 로 볼지
DIRECT_AFTER = 7     # 기사보다 며칠 뒤에 접수된 공시까지 direct 로 볼지
FOLLOW_AFTER = 90    # 기사 뒤 며칠까지 follow 로 볼지

# event_class 별 가중치. analysis/disclosure_weights.py 의 RULES 와 같은 값이다.
# disclosures.event_weight 는 정정 공시이면 0이라 정렬에 쓰면 정정 공시가 모두 뒤로 밀린다.
# 그래서 정렬에는 행의 event_weight 가 아니라 이 분류별 값을 쓴다.
CLASS_WEIGHT = {
    "수주": 5,
    "증설": 4,
    "M&A·구조개편": 4,
    "실적": 3,
    "임상·허가·기술계약": 2,
    "자금조달": 2,
    "리스크": 0,
}
MATCH_CLASSES = list(CLASS_WEIGHT)   # 매칭에 쓰는 사건성 공시 분류
RISK_CLASS = "리스크"

# CDMO 키워드 → 창별로 연결할 event_class (문서 3-3절).
# 규제·정책과 지정학 기사는 공시와 같은 사건을 다루지 않으므로 direct 가 비어 있다.
TOPIC_MAP = {
    "CDMO 수주":      {"direct": ["수주"],
                       "follow": ["수주", "실적"]},
    "CDMO 생산능력":  {"direct": ["증설", "자금조달"],
                       "follow": ["증설", "자금조달", "수주"]},
    "CDMO 경쟁 구도": {"direct": ["M&A·구조개편", "수주"],
                       "follow": ["M&A·구조개편", "수주", "증설"]},
    "CDMO 모달리티":  {"direct": ["임상·허가·기술계약", "증설"],
                       "follow": ["임상·허가·기술계약", "증설", "수주"]},
    "CDMO 규제·정책": {"direct": [],
                       "follow": ["수주", "증설", "M&A·구조개편"]},
    "CDMO 지정학":    {"direct": [],
                       "follow": ["수주", "증설", "M&A·구조개편"]},
}

COLS = ["url", "published_date", "corp_code", "corp_name", "rcept_no", "rcept_date", "report_nm",
        "window", "day_gap", "news_keyword", "event_class", "class_weight", "is_amended",
        "kw_low_confidence", "follow_cut"]


def window_of(day_gap: int):
    """day_gap(공시 접수일 − 기사 발행일)이 어느 창인지. 창 밖이면 None."""
    if -DIRECT_BEFORE <= day_gap <= DIRECT_AFTER:
        return "direct"
    if DIRECT_AFTER < day_gap <= FOLLOW_AFTER:
        return "follow"
    return None


def topic_ok(keyword, window: str, event_class: str) -> bool:
    """키워드·창·공시 분류 조합이 연결 대상인지. keyword 는 None(키워드 없는 기사)일 수 있다."""
    if event_class == RISK_CLASS:
        return window == "direct"
    if keyword not in TOPIC_MAP:
        return False
    return event_class in TOPIC_MAP[keyword][window]


def load(con):
    """매칭 대상 기사(기사 × 기업 × 키워드)와 사건성 공시를 읽는다."""
    news = pd.read_sql(
        """
        SELECT n.url, n.published_date, n.cdmo_kw_basis, nc.corp_code, k.keyword
        FROM news n
        JOIN news_companies nc ON nc.news_id = n.news_id
        LEFT JOIN news_cdmo_keywords k ON k.news_id = n.news_id
        WHERE n.dup_of IS NULL AND nc.match_field IN ('title', 'body')
        """, con)
    marks = ",".join("?" * len(MATCH_CLASSES))
    disc = pd.read_sql(
        f"""
        SELECT d.rcept_no, d.corp_code, c.corp_name, d.rcept_date, d.report_nm,
               d.event_class, d.is_amended
        FROM disclosures d JOIN companies c ON c.corp_code = d.corp_code
        WHERE d.event_class IN ({marks})
        """, con, params=MATCH_CLASSES)
    return news, disc


def match(news: pd.DataFrame, disc: pd.DataFrame, db_end=DB_END) -> pd.DataFrame:
    """연결 조건을 적용해 기사 × 기업 × 공시 = 1행의 표를 만든다."""
    if news.empty or disc.empty:
        return pd.DataFrame(columns=COLS)

    pairs = news.merge(disc, on="corp_code")
    pub = pd.to_datetime(pairs["published_date"])
    pairs["day_gap"] = (pd.to_datetime(pairs["rcept_date"]) - pub).dt.days
    # 창 밖의 쌍을 먼저 버려 이후 계산량을 줄인다
    pairs = pairs[pairs["day_gap"].between(-DIRECT_BEFORE, FOLLOW_AFTER)].copy()
    if pairs.empty:
        return pd.DataFrame(columns=COLS)

    pairs["window"] = pairs["day_gap"].map(window_of)
    keep = [topic_ok(k if isinstance(k, str) else None, w, e)
            for k, w, e in zip(pairs["keyword"], pairs["window"], pairs["event_class"])]
    pairs = pairs[keep]
    if pairs.empty:
        return pd.DataFrame(columns=COLS)

    # 한 기사가 여러 키워드로 같은 공시에 걸리면 한 행으로 합친다.
    # 리스크 공시는 키워드와 무관하게 걸리므로 news_keyword 를 비운다.
    def join_keywords(s):
        return "; ".join(sorted({k for k in s if isinstance(k, str)}))

    key = ["url", "corp_code", "rcept_no"]
    links = (pairs.groupby(key, sort=False)
             .agg(published_date=("published_date", "first"),
                  corp_name=("corp_name", "first"),
                  rcept_date=("rcept_date", "first"),
                  report_nm=("report_nm", "first"),
                  window=("window", "first"),
                  day_gap=("day_gap", "first"),
                  news_keyword=("keyword", join_keywords),
                  event_class=("event_class", "first"),
                  is_amended=("is_amended", "first"),
                  cdmo_kw_basis=("cdmo_kw_basis", "first"))
             .reset_index())
    links.loc[links["event_class"] == RISK_CLASS, "news_keyword"] = ""
    links["class_weight"] = links["event_class"].map(CLASS_WEIGHT)
    # 키워드가 검색어만으로 붙은 기사는 주제 대응의 신뢰도가 낮다
    links["kw_low_confidence"] = (links["cdmo_kw_basis"] == "query").astype(int)
    # 수집 기간 끝에 가까운 기사는 follow 창이 잘린다 — "후속 공시 없음"이 아니라 "아직 알 수 없음"
    cut_from = pd.Timestamp(db_end) - timedelta(days=FOLLOW_AFTER)
    links["follow_cut"] = (pd.to_datetime(links["published_date"]) > cut_from).astype(int)

    # 기사별로 direct → follow, 분류 가중치 높은 순, 날짜가 가까운 순
    links["_w"] = (links["window"] != "direct").astype(int)
    links["_gap"] = links["day_gap"].abs()
    links = links.sort_values(
        ["published_date", "url", "corp_code", "_w", "class_weight", "_gap", "rcept_no"],
        ascending=[True, True, True, True, False, True, True])
    return links[COLS].reset_index(drop=True)


def summarize(news: pd.DataFrame, disc: pd.DataFrame, links: pd.DataFrame) -> str:
    """실행 결과 요약 문자열."""
    articles = news[["url", "corp_code"]].drop_duplicates()
    linked = links[["url", "corp_code"]].drop_duplicates()
    n_art, n_linked = len(articles), len(linked)
    lines = [
        f"창: direct −{DIRECT_BEFORE}~+{DIRECT_AFTER}일, follow +{DIRECT_AFTER + 1}~+{FOLLOW_AFTER}일",
        f"대상 기사(기사 × 기업): {n_art:,}건 / 사건성 공시: {len(disc):,}건",
        f"연결: {len(links):,}쌍",
    ]
    if n_art:
        lines.append(f"공시가 1건 이상 연결된 기사: {n_linked:,}건 ({n_linked / n_art:.1%}), "
                     f"연결 없음: {n_art - n_linked:,}건")
    if len(links):
        per = links.groupby(["url", "corp_code"]).size()
        lines.append(f"기사당 연결 공시 수: 중앙값 {per.median():.0f}, 최대 {per.max()}")
        lines.append("\n[창 × 공시 분류]")
        lines.append(pd.crosstab(links["event_class"], links["window"], margins=True,
                                 margins_name="계").to_string())
        lines.append("\n[기업 × 창]")
        lines.append(pd.crosstab(links["corp_name"], links["window"], margins=True,
                                 margins_name="계").to_string())
        lines.append(f"\n정정 공시 연결: {int(links['is_amended'].sum()):,}쌍 / "
                     f"키워드 신뢰도 낮음: {int(links['kw_low_confidence'].sum()):,}쌍 / "
                     f"follow 창이 잘린 기사의 연결: {int(links['follow_cut'].sum()):,}쌍")
    return "\n".join(lines)


def main():
    if not DB_PATH.exists():
        sys.exit(f"DB가 없습니다: {DB_PATH}\n"
                 "python db/build_db.py 로 만들거나 팀원에게 파일을 받아 같은 위치에 둡니다.")
    with sqlite3.connect(DB_PATH) as con:
        news, disc = load(con)
    links = match(news, disc)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    links.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(summarize(news, disc, links))
    print(f"\n저장: {OUT} ({len(links):,}행)")


if __name__ == "__main__":
    main()
