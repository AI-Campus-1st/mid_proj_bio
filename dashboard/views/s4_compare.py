"""기업 비교 — F4 (US-11, US-12, US-13 / AC-11, AC-12, AC-13). 아직 구현 전이라 '준비 중' 상태만 보여 준다."""
import streamlit as st

from core import ui


def render():
    ui.header("기업 비교", "경쟁사의 수주·증설·투자는 어떻게 변하는가?", st.session_state["filters"])
    ui.pending("기업별 주요 4분류 공시 건수와 공시 타임라인", "화면 구현(다음 단계 — 공시 DB는 준비됨)")
    ui.pending("수주 계약 금액 추이", "수주 공시 계약 금액 추출")
    ui.limits()
