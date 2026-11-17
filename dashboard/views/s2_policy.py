"""규제·정책 — F2, F8 (US-06, US-07, US-08 / AC-06, AC-07, AC-08). 아직 데이터 또는 구현 전이라 '준비 중' 상태만 보여 준다."""
import streamlit as st

from core import ui


def render():
    ui.header("규제·정책", "정책·규제 변화는 CDMO 시장에 기회인가 위험인가?", st.session_state["filters"])
    ui.pending("정책·규제 타임라인과 기회/위험 라벨", "화면 구현(다음 단계 — 감성 라벨 sentiment-v3 결과는 준비됨)")
    ui.pending("영어 기사 한국어 제목", "영어 기사 번역(title_ko)")
    ui.limits()
