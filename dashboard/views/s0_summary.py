"""요약 — F6 (US-01, US-02 / AC-01, AC-02). 아직 데이터 또는 구현 전이라 '준비 중' 상태만 보여 준다."""
import streamlit as st

from core import ui


def render():
    ui.header("요약", "지금 주목할 기회와 위험 요인은 무엇인가?", st.session_state["filters"])
    ui.pending("기회·위험 결론 문장과 카드 (근거 뉴스·공시 링크 포함)", "F1~F5 산출물을 요약한 사전 생성 카드")
    ui.limits()
