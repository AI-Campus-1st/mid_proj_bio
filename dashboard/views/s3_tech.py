"""기술·생산 — F3 (US-09, US-10 / AC-09, AC-10). 아직 데이터 또는 구현 전이라 '준비 중' 상태만 보여 준다."""
import streamlit as st

from core import ui


def render():
    ui.header("기술·생산", "어떤 모달리티·생산기술이 성장하는가?", st.session_state["filters"])
    ui.pending("모달리티별 언급 추이와 증설 공시 목록", "화면 구현(다음 단계 — 키워드·증설 공시 데이터는 준비됨)")
    ui.pending("기업 × 모달리티 히트맵", "LLM 모달리티 태깅")
    ui.limits()
