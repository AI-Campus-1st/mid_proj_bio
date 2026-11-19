"""CDMO 이슈 대시보드 — 실행: 저장소 루트에서 `streamlit run dashboard/app.py`.

구성은 docs/05_design/UI_SPECIFICATION.md 3-1절: 페이지 설정 → 사이드바 필터 → 메뉴 → 화면 실행.
"""
import streamlit as st

from core import filters, style, ui
from views import s0_summary, s1_trend, s2_policy, s3_tech, s4_compare, s5_linkage, s6_qa

APP_TITLE = "CDMO 이슈 대시보드"

st.set_page_config(page_title=APP_TITLE, layout="wide", initial_sidebar_state="expanded")
ui.reset_cards()
style.inject()   # DESIGN.md — 테마로 안 되는 카드·버튼·제목·결론 띠 (core/style.py)

# 메뉴(st.navigation)는 사이드바 내용보다 위에 그려지므로, 제목은 CSS로 메뉴 위에 붙인다(명세 3-1절 "사이드바 맨 위 문구")
# 제목은 사이드바 폭에 맞춰 한 줄로: 글자 크기를 메뉴 폭(cqi)에 비례시킨다 (18px 에서 글자 폭 ≈ 161px → 폭의 약 11%)
st.html(f"""<style>
[data-testid="stSidebarNav"] {{ container-type: inline-size; }}
[data-testid="stSidebarNav"]::before {{
  content: "{APP_TITLE}";
  display: block;
  padding: 0 0 0.75rem;
  white-space: nowrap;
  font-size: clamp(0.875rem, 10.8cqi, 1.5rem);
  font-weight: 600;
  line-height: 1.2;
  color: var(--st-text-color, inherit);
}}
/* 기간 달력 머리: Streamlit 기본은 [월][연도] — 순서를 [연도][월]로 */
[data-testid="stDateInputCalendar"] header > div {{
  flex-direction: row-reverse;
}}
/* 달력 아래 영어 'Date range' 빠른 선택은 숨긴다 — 오늘부터 세서 데이터 기간과 안 맞음. 한국어 빠른 선택은 filters.py */
[data-testid="stDateInputQuickSelect"] {{
  display: none;
}}
</style>""")

with st.sidebar:
    st.markdown("### 필터")
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
