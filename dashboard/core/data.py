"""DB·CSV 읽기 — docs/05_design/UI_SPECIFICATION.md 3-1절.

읽는 함수는 st.cache_data 로 감싼다. 화면별 집계 함수는 각 화면을 구현할 때 이 파일에 더한다.
"""
import sqlite3
from pathlib import Path

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
