"""공시 Q&A — F5 (US-16, US-17 / AC-16, AC-17). 아직 데이터 또는 구현 전이라 '준비 중' 상태만 보여 준다."""
import streamlit as st

from core import ui


def render():
    ui.header("공시 Q&A", "공시 원문에 근거해 답합니다.", st.session_state["filters"])
    ui.pending("공시 질의응답 (근거 공시명·제출일·DART 링크, 근거 없으면 거절)", "공시 RAG(rag/qa.py)")
    ui.limits()
