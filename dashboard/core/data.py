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
            "SELECT n.news_id, n.origin, n.published_date, n.published_at, n.title, n.url, n.press, n.lang, "
            "n.title_ko, "
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


# ---------------------------------------------------------------- 감성 라벨 (S2)

SENTIMENT_PATH = PROCESSED / "sentiment_llm.csv"


@st.cache_data(show_spinner=False)
def sentiment_frame() -> pd.DataFrame:
    """LLM 감성 라벨 (sentiment-v3). url 로 news 와 잇는다. 실패 행(label 없음)은 뺀다."""
    df = pd.read_csv(SENTIMENT_PATH, dtype=str)
    df = df[df.label.isin(["기회", "위험", "중립"])]
    return df[["url", "label", "reason", "confidence", "input_basis", "model", "prompt_version"]] \
        .drop_duplicates("url")


# ---------------------------------------------------------------- 모달리티 태그 (S3)

MODALITY_PATH = PROCESSED / "modality_llm.csv"
# 히트맵·추이에 쓰는 7개. "기타"(저분자·오가노이드 등)는 CDMO 생산 모달리티로 보기 어려워 화면에서 뺀다
# (AI_CLASSIFICATION 4-1절).
MODALITIES = ["항체", "ADC", "mRNA", "세포·유전자치료제", "올리고", "펩타이드", "백신"]
S3_KEYWORDS = ["CDMO 모달리티", "CDMO 생산능력"]   # UI_SPECIFICATION 4-3절 S3 교집합


@st.cache_data(show_spinner=False)
def modality_frame() -> pd.DataFrame:
    """기사 × 모달리티 1행 (태그가 여러 개면 여러 행). 성공한 태깅만, '기타' 제외."""
    df = pd.read_csv(MODALITY_PATH, dtype=str).fillna("")
    df = df[(df.error == "") & (df.modalities != "")]
    df = df.assign(modality=df.modalities.str.split("; ")).explode("modality")
    return df[df.modality.isin(MODALITIES)][["url", "modality", "evidence", "confidence", "input_basis"]]


def s3_keywords(filters: dict) -> list:
    return [k for k in S3_KEYWORDS if k in filters["keywords"]]


def filter_s3_news(filters: dict) -> pd.DataFrame:
    """S3 기사: 사이드바 필터 + 카테고리는 모달리티·생산능력과의 교집합만 (4-3절). 교집합이 없으면 빈 표."""
    kws = s3_keywords(filters)
    if not kws:
        return news_frame().iloc[0:0]
    df = filter_news({**filters, "keywords": list(KEYWORDS)})   # 기간·기업만
    kw = news_keywords()
    return df[df.news_id.isin(kw[kw.keyword.isin(kws)].news_id)]


# ---------------------------------------------------------------- 공시 (S3·S4)

# NEWS_DISCLOSURE_MATCHING 3-3절 대응표의 직접·후속 열을 합친 집합 (UI_SPECIFICATION 4-3절 S4, 미결 Q8)
KEYWORD_EVENTS = {
    "CDMO 수주": {"수주", "실적"},
    "CDMO 생산능력": {"증설", "자금조달", "수주"},
    "CDMO 경쟁 구도": {"M&A·구조개편", "수주", "증설"},
    "CDMO 모달리티": {"임상·허가·기술계약", "증설", "수주"},
    "CDMO 규제·정책": {"수주", "증설", "M&A·구조개편"},
    "CDMO 지정학": {"수주", "증설", "M&A·구조개편"},
}
MAIN_EVENTS = ["수주", "증설", "M&A·구조개편", "자금조달"]   # S4 주요 4분류 (UI_SPECIFICATION 5-5절)


@st.cache_data(show_spinner=False)
def disclosures_frame() -> pd.DataFrame:
    con = connect()
    try:
        df = pd.read_sql(
            "SELECT d.rcept_no, d.rcept_date, c.corp_name, d.report_nm, d.event_class, d.is_amended, d.url "
            "FROM disclosures d JOIN companies c USING (corp_code)", con)
    finally:
        con.close()
    df["date"] = pd.to_datetime(df.rcept_date)
    return df


def filter_disclosures(filters: dict, event_classes=None) -> pd.DataFrame:
    """4-2절 공시 규칙: 제출일이 기간 안, 선택 기업. event_classes 가 있으면 그 분류만."""
    df = disclosures_frame()
    s, e = filters["period"]
    df = df[(df.date >= pd.Timestamp(s)) & (df.date <= pd.Timestamp(e)) & df.corp_name.isin(filters["companies"])]
    if event_classes is not None:
        df = df[df.event_class.isin(event_classes)]
    return df


def keyword_events(filters: dict) -> set:
    return set().union(*(KEYWORD_EVENTS[k] for k in filters["keywords"])) if filters["keywords"] else set()


# ---------------------------------------------------------------- 수주 계약 금액 (S4)

AMOUNTS_PATH = PROCESSED / "contract_amounts.csv"


@st.cache_data(show_spinner=False)
def contract_amounts() -> tuple:
    """(원공시 표, 정정 공시 표). 원공시 1행에 최신 정정본 금액을 붙인다 (eda_report 5절).

    정정 공시는 original_date(정정 대상 공시의 제출일)로 같은 기업의 원공시를 찾는다. 정정의 정정이면
    대상이 정정 공시이므로 그 정정의 원공시까지 따라간다. 같은 원공시의 정정이 여러 건이면 가장 늦은 것.
    원공시가 DB 기간 밖(2017~2023년 계약)인 정정은 matched=False 로 남긴다.
    """
    df = pd.read_csv(AMOUNTS_PATH, dtype=str).fillna("")
    df["is_amended"] = df.is_amended.astype(int)
    df["amount"] = pd.to_numeric(df.amount_krw, errors="coerce")
    orig = df[df.is_amended == 0].copy()
    amended = df[df.is_amended == 1].copy()
    # (기업, 제출일) → 원공시 rcept_no. 같은 날 원공시가 2건 이상이면 어느 것의 정정인지 알 수 없어 연결하지 않는다
    # 해지 공시는 정정 대상(계약 체결)이 아니다. 프레스티지 2026-04-30 정정은 원공시 제출일을 해지 공시와 같은 날로
    # 적어 두어, 해지를 빼지 않으면 해지 공시에 금액이 붙는다.
    key = orig[~orig.report_nm.str.contains("해지")].groupby(["corp_name", "rcept_date"]).rcept_no.agg(list)
    origin_of = {k: v[0] for k, v in key.items() if len(v) == 1}
    amend_target = {(r.corp_name, r.rcept_date): r.original_date for r in amended.itertuples()}

    def resolve(corp: str, date: str):
        for _ in range(5):                       # 정정의 정정 (실제는 2단계 이내)
            if (corp, date) in origin_of:
                return origin_of[(corp, date)]
            if (corp, date) not in amend_target:
                return None
            date = amend_target[(corp, date)]
        return None

    amended["target"] = [resolve(c, d) for c, d in zip(amended.corp_name, amended.original_date)]
    latest = (amended[amended.target.notna() & amended.amount.notna()]
              .sort_values(["rcept_date", "rcept_no"]).groupby("target").last())
    n_amend = amended[amended.target.notna()].groupby("target").size()
    orig["first_amount"] = orig.amount
    orig["n_amended"] = orig.rcept_no.map(n_amend).fillna(0).astype(int)
    orig["amount"] = orig.rcept_no.map(latest.amount).fillna(orig.amount)
    orig["latest_amend_date"] = orig.rcept_no.map(latest.rcept_date).fillna("")
    orig["date"] = pd.to_datetime(orig.rcept_date)
    amended["matched"] = amended.target.notna()
    amended["date"] = pd.to_datetime(amended.rcept_date)
    return orig, amended


# ---------------------------------------------------------------- 뉴스-공시 연결 (S5)

LINKS_PATH = PROCESSED / "news_disclosure_links.csv"


@st.cache_data(show_spinner=False)
def links_frame() -> pd.DataFrame:
    """M1 매칭 결과 (기사 url × 공시 rcept_no). news_keyword 는 '; ' 로 이어진 대표 키워드 목록."""
    df = pd.read_csv(LINKS_PATH, dtype=str).fillna("")
    for col in ("day_gap", "class_weight", "is_amended", "kw_low_confidence", "follow_cut"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    df["date"] = pd.to_datetime(df.published_date)
    df["keywords"] = df.news_keyword.map(lambda s: [k for k in s.split("; ") if k])
    return df


def filter_links(filters: dict) -> pd.DataFrame:
    """4-2절 연결 규칙: 기사 발행일이 기간 안, 선택 기업, 선택 키워드가 하나라도 있는 행.
    키워드가 빈 행(리스크 공시 107행)은 카테고리 6개 전체일 때만 넣는다 (미결 Q8)."""
    df = links_frame()
    s, e = filters["period"]
    df = df[(df.date >= pd.Timestamp(s)) & (df.date <= pd.Timestamp(e)) & df.corp_name.isin(filters["companies"])]
    sel = set(filters["keywords"])
    all_kw = len(sel) == len(KEYWORDS)
    keep = df.keywords.map(lambda ks: bool(sel & set(ks)) if ks else all_kw)
    return df[keep]
