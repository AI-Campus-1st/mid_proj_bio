"""이슈·트렌드 — F1 (US-03, US-04, US-05 / AC-03, AC-04, AC-05). 아직 구현 전이라 '준비 중' 상태만 보여 준다."""
import streamlit as st

from core import ui


def render():
    ui.header("이슈·트렌드", "지금 가장 많이 다뤄지는 이슈는?", st.session_state["filters"])
    ui.pending("기사량 추이와 급증 시점, 근거 기사·공시", "화면 구현(다음 단계 — DB·eda_spikes.csv 는 준비됨)")
    ui.limits()
