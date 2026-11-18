"""CDMO 이슈 대시보드 — 실행: 저장소 루트에서 `streamlit run dashboard/app.py`.

구성은 docs/05_design/UI_SPECIFICATION.md 3-1절: 페이지 설정 → 사이드바 필터 → 메뉴 → 화면 실행.
"""
import streamlit as st

from core import filters
from views import s0_summary, s1_trend, s2_policy, s3_tech, s4_compare, s5_linkage, s6_qa

st.set_page_config(page_title="CDMO 이슈 대시보드", layout="wide", initial_sidebar_state="expanded")

with st.sidebar:
    st.markdown("### CDMO 이슈 대시보드")
    filters.render_sidebar()

# 화면 함수 이름이 모두 render 라 url_path 를 직접 준다
pages = {
    "": [st.Page(s0_summary.render, title="요약", url_path="summary", default=True)],
    "산업 흐름": [st.Page(s1_trend.render, title="이슈·트렌드", url_path="trend"),
              st.Page(s2_policy.render, title="규제·정책", url_path="policy"),
              st.Page(s3_tech.render, title="기술·생산", url_path="tech")],
    "경쟁": [st.Page(s4_compare.render, title="기업 비교", url_path="compare")],
    "근거 확인": [st.Page(s5_linkage.render, title="뉴스-공시 연계", url_path="linkage"),
              st.Page(s6_qa.render, title="공시 Q&A", url_path="qa")],
}
st.navigation(pages, position="sidebar").run()
