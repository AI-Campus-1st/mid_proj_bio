"""DB·CSV 읽기 — docs/05_design/UI_SPECIFICATION.md 3-1절.

읽는 함수는 st.cache_data 로 감싼다. 화면별 집계 함수는 각 화면을 구현할 때 이 파일에 더한다.
"""
import re
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "db" / "bio_cdmo.sqlite"
PROCESSED = ROOT / "data" / "processed"

# IA 4-1절 순서 (미결 Q10 — 화면은 이 순서를 쓴다)
COMPANIES = ["삼성바이오로직스", "SK바이오사이언스", "프레스티지바이오로직스", "에스티팜", "바이넥스"]
KEYWORDS = ["CDMO 규제·정책", "CDMO 지정학", "CDMO 모달리티", "CDMO 생산능력", "CDMO 수주", "CDMO 경쟁 구도"]
PERIOD = ("2023-10-19", "2026-10-19")  # DB meta 를 못 읽을 때의 기본값


def connect() -> sqlite3.Connection:
    """읽기 전용 연결. 파일이 없으면 FileNotFoundError (화면은 ui.data_error 로 알린다)."""
    if not DB_PATH.exists():
        raise FileNotFoundError(DB_PATH)
    return sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)


@st.cache_data(show_spinner=False)
def meta() -> dict:
    """DB meta 표 (period_start, period_end, built_at, dup_rule). 못 읽으면 빈 dict."""
    try:
        con = connect()
        try:
            return {k: v for k, v, *_ in con.execute("SELECT * FROM meta").fetchall()}
        finally:
            con.close()
    except Exception:
        return {}


# ---------------------------------------------------------------- 뉴스 (S1·S2·S3·S5 공통)

ORIGIN_KO = {"provided": "제공", "team": "팀원수집", "google_company": "기업명검색",
             "google_cdmo": "CDMO검색", "google_global": "해외검색"}  # analysis/eda.py 와 같은 이름·순서


@st.cache_data(show_spinner=False)
def news_frame() -> pd.DataFrame:
    """중복 제외 기사 전체 (PRD 4절 R1). 필터는 filter_news() 로 건다."""
    con = connect()
    try:
        df = pd.read_sql(
            "SELECT n.news_id, n.origin, n.published_date, n.title, n.url, n.press, n.lang, n.title_ko, "
            "n.cdmo_kw_basis, c.title_clean FROM news n LEFT JOIN news_clean c USING (news_id) "
            "WHERE n.dup_of IS NULL", con)
    finally:
        con.close()
    df["date"] = pd.to_datetime(df.published_date)
    df["origin_ko"] = df.origin.map(ORIGIN_KO)
    return df


@st.cache_data(show_spinner=False)
def news_keywords() -> pd.DataFrame:
    con = connect()
    try:
        return pd.read_sql("SELECT news_id, keyword, is_primary FROM news_cdmo_keywords", con)
    finally:
        con.close()


@st.cache_data(show_spinner=False)
def news_companies() -> pd.DataFrame:
    """기업 단위 집계용 — 제목·본문에 기업명이 있는 행만 (PRD 4절 R2)."""
    con = connect()
    try:
        return pd.read_sql(
            "SELECT nc.news_id, c.corp_name FROM news_companies nc JOIN companies c USING (corp_code) "
            "WHERE nc.match_field IN ('title', 'body')", con)
    finally:
        con.close()


def filter_news(filters: dict) -> pd.DataFrame:
    """UI_SPECIFICATION 4-2절 뉴스 규칙.

    기업: 5개 전체면 거르지 않음(산업 기사 포함), 일부면 그 기업이 제목·본문에 나온 기사만 (U2).
    카테고리: 선택 키워드가 하나라도 있는 기사. 6개 전체면 키워드 없는 기사도 포함 (미결 Q1 임시 동작).
    """
    df = news_frame()
    s, e = filters["period"]
    df = df[(df.date >= pd.Timestamp(s)) & (df.date <= pd.Timestamp(e))]
    if len(filters["companies"]) < len(COMPANIES):
        nc = news_companies()
        df = df[df.news_id.isin(nc[nc.corp_name.isin(filters["companies"])].news_id)]
    if len(filters["keywords"]) < len(KEYWORDS):
        kw = news_keywords()
        df = df[df.news_id.isin(kw[kw.keyword.isin(filters["keywords"])].news_id)]
    return df


# ---------------------------------------------------------------- 급증 시점 (S1)

SPIKES_PATH = PROCESSED / "eda_spikes.csv"
# 산업 전체 급증 중 정기 행사 주간 (eda_report 4-1절)
EVENT_WEEKS = {"2025-06-16": "바이오 USA", "2026-06-22": "바이오 USA", "2025-10-27": "CPHI", "2026-10-05": "CPHI"}
_ARTICLE = re.compile(r"^(.*) \((.+?)\) (https?://\S+)$")
_DISCLOSURE = re.compile(r"^(\d{4}-\d{2}-\d{2}) \[(.+?)\] (.*?) (https?://\S+)$")


@st.cache_data(show_spinner=False)
def spikes_frame() -> pd.DataFrame:
    df = pd.read_csv(SPIKES_PATH, dtype=str).fillna("")
    for col in ("peak_count", "weeks"):
        df[col] = df[col].astype(int)
    for col in ("baseline", "z"):
        df[col] = df[col].astype(float)
    df["peak"] = pd.to_datetime(df.peak_week)
    df["spike_id"] = df.series + "|" + df.scope + "|" + df.peak_week
    df["event"] = [EVENT_WEEKS.get(w, "") if s == "산업 전체" else "" for s, w in zip(df.series, df.peak_week)]
    return df


def filter_spikes(filters: dict) -> pd.DataFrame:
    """4-2절 급증 규칙. 기업 행은 선택 기업만, 산업 전체 행은 5개 전체일 때만 (U2). 키워드 행은 선택 키워드만."""
    df = spikes_frame()
    s, e = filters["period"]
    df = df[(df.peak >= pd.Timestamp(s)) & (df.peak <= pd.Timestamp(e))]
    all_corps = len(filters["companies"]) == len(COMPANIES)
    keep = ((df.series == "기업") & df.scope.isin(filters["companies"])) \
        | ((df.series == "산업 전체") & all_corps) \
        | ((df.series == "키워드") & df.scope.isin(filters["keywords"]))
    return df[keep].sort_values("peak", ascending=False)


def spike_evidence(row: pd.Series) -> tuple:
    """급증 1건의 대표 기사(최대 3건)와 같은 시기 공시를 읽는다 (UI_SPECIFICATION 5-2절 S1-C3)."""
    news = news_frame().set_index("url")
    articles = []
    for item in [x.strip() for x in row["evidence_articles"].split(" / ") if x.strip()][:3]:
        m = _ARTICLE.match(item)
        if not m:
            continue
        title, press, url = m.groups()
        hit = news.loc[url] if url in news.index else None
        if isinstance(hit, pd.DataFrame):
            hit = hit.iloc[0]
        articles.append({"title": title, "press": press, "url": url,
                         "published_date": hit["published_date"] if hit is not None else "",
                         "lang": hit["lang"] if hit is not None else "ko",
                         "title_ko": hit["title_ko"] if hit is not None else None,
                         "cdmo_kw_basis": hit["cdmo_kw_basis"] if hit is not None else ""})
    disclosures = []
    for item in [x.strip() for x in row["disclosures"].split(" / ") if x.strip()]:
        m = _DISCLOSURE.match(item)
        if m:
            d, cls, name, url = m.groups()
            disclosures.append({"rcept_date": d, "event_class": cls, "report_nm": name, "url": url})
    return articles, disclosures
