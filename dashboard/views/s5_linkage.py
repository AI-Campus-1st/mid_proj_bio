"""뉴스-공시 연계 — F5 (US-14, US-15 / AC-14, AC-15). 아직 데이터 또는 구현 전이라 '준비 중' 상태만 보여 준다."""
import streamlit as st

from core import ui


def render():
    ui.header("뉴스-공시 연계", "뉴스의 변화가 공시로 확인되는가?", st.session_state["filters"])
    ui.pending("기업별 기사량과 공시 시점 비교", "화면 구현(다음 단계 — v_company_daily 는 준비됨)")
    ui.pending("이슈 ↔ 관련 공시 목록", "뉴스-공시 매칭(news_disclosure_links.csv)")
    ui.limits()
