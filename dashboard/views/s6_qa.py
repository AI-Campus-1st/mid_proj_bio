"""공시 Q&A — F5 (US-16, US-17 / AC-16, AC-17). docs/05_design/UI_SPECIFICATION.md 5-7절.

rag/qa.py ask() 를 질문할 때마다 부른다 (임베딩 1회 + 답변 1회, 결과는 캐시하지 않음).
명세 5-7절은 SystemExit·답변 문구로 상태를 판정하도록 적혀 있었으나(미결 Q3), qa.py 가 QAError·flags·
answer_display 를 돌려주도록 바뀌어 그 값을 쓴다 (NEWS_DISCLOSURE_MATCHING 4-8절).
"""
import sys
from pathlib import Path

import streamlit as st

from core import filters as flt
from core import ui

RAG_DIR = Path(__file__).resolve().parents[2] / "rag"
EXAMPLES = [
    "생물보안법 논의 이후 삼성바이오로직스가 공시한 수주 계약은?",
    "에스티팜의 최근 단일판매·공급계약 금액은?",
    "SK바이오사이언스의 신규 시설 투자 내용은?",
]
HISTORY_MAX = 20
SCOPE_MISMATCH = "질문의 기업이 선택한 기업 필터 밖에 있다"
LIMITS_S6 = [
    "답변은 LLM이 공시 원문 발췌로 만듭니다. 근거 공시 원문을 확인하세요.",
    "색인 범위: 원문이 있는 공시 864건.",
    "평가(질문 20개): 검색 12/14, 거절 6/6, 근거 일치 12/13.",
]
SETUP_HELP = ("`.env` 의 `OPENAI_API_KEY`, 색인 폴더 `chroma_db/` (`python rag/build_index.py` 로 생성)를 "
              "확인하세요.")


def _qa():
    if str(RAG_DIR) not in sys.path:
        sys.path.insert(0, str(RAG_DIR))
    import qa
    return qa


def _scope(filters: dict) -> dict:
    """S6-K: 질문 범위. L8 로 넘어온 범위가 있으면 그것을, 없으면 체크한 사이드바 조건을 쓴다 (U4)."""
    override = st.session_state.get("qa_scope_override")
    if override:
        return dict(override)
    s, e = filters["period"]
    return {
        "corp_names": list(filters["companies"]) if st.session_state.get("qa_use_companies", True) else None,
        "date_from": f"{s:%Y-%m-%d}" if st.session_state.get("qa_use_period", True) else None,
        "date_to": f"{e:%Y-%m-%d}" if st.session_state.get("qa_use_period", True) else None,
    }


def _clear_override() -> None:
    st.session_state.pop("qa_scope_override", None)


def _render_scope(filters: dict) -> None:
    st.caption("범위: 5개사 · 공시 원문 있는 공시")
    override = st.session_state.get("qa_scope_override")
    if override:
        corps = ", ".join(override.get("corp_names") or []) or "5개사"
        st.caption(f"공시 화면에서 넘어온 범위: {corps} · {override.get('date_from') or '—'}")
        st.button("사이드바 범위로 돌아가기", on_click=_clear_override)
        return
    s, e = filters["period"]
    c1, c2 = st.columns(2, gap="small")
    c1.checkbox(f"기간: {s:%Y-%m-%d} ~ {e:%Y-%m-%d}", key="qa_use_period", value=True)
    c2.checkbox(f"기업: {flt.company_summary(filters)}", key="qa_use_companies", value=True)


def _submit(question: str, scope: dict) -> None:
    question = (question or "").strip()
    if not question:
        return
    if scope["corp_names"] is not None and not scope["corp_names"]:
        st.warning("사이드바에서 기업을 1개 이상 고르거나, 기업 조건을 해제하세요.")
        return
    try:
        qa = _qa()
        with st.spinner("공시를 찾는 중"):
            result = qa.ask(question, **scope)
    except Exception as e:  # qa.QAError(no_api_key / no_index / api_error) 와 그 밖의 예외
        st.session_state["qa_last"] = {"question": question, "error": getattr(e, "code", type(e).__name__),
                                       "error_message": str(e)}
        return
    entry = {"question": question, "scope": scope, "result": result}
    st.session_state["qa_last"] = entry
    history = [h for h in st.session_state.get("qa_history", []) if h is not entry]
    st.session_state["qa_history"] = ([entry] + history)[:HISTORY_MAX]


def _render_citations(citations: list) -> None:
    st.markdown("#### 근거 공시")
    for c in citations:
        amended = " :gray-badge[정정]" if int(c.get("is_amended") or 0) else ""
        st.markdown(f"**[{c['n']}]** [{c['report_nm']}]({c['url']}){amended} · {c['rcept_date']} · "
                    f"{c['corp_name']} · [DART]({c['url']})")
        with st.expander("인용 구절"):
            for q in c.get("quotes") or [c.get("quote", "")]:
                st.markdown(f"> {q}")


def _render_result(entry: dict) -> None:
    st.markdown(f"#### 질문\n{entry['question']}")
    if "error" in entry:
        st.error("Q&A를 사용할 수 없습니다(설정 확인)")
        with st.expander("설정 확인"):
            st.markdown(SETUP_HELP)
            st.caption(f"{entry['error']}: {entry.get('error_message', '')}")
        return

    r = entry["result"]
    flags = r.get("flags") or {}
    if flags.get("judgment_declined"):
        st.info("판단은 하지 않고 공시 사실만 안내합니다")

    if r["refused"] or not r.get("citations"):
        if r["stage"] == "scope":
            st.warning(f"**이 대시보드는 5개사 공시만 다룹니다.**  \n{r['answer']}")
        elif r["stage"] == "search" and r.get("refusal_reason") == SCOPE_MISMATCH:
            st.warning(f"**공시에서 근거를 찾지 못했습니다.**  \n{r['answer']}  \n"
                       "질문 범위의 기업 조건을 해제하거나 질문 속 기업을 바꿔 보세요.")
        else:
            st.warning(f"**공시에서 근거를 찾지 못했습니다.**  \n{r['answer']}  \n"
                       "기업명·기간·공시 종류(예: 단일판매·공급계약, 신규시설투자)를 넣어 다시 질문해 보세요.")
            with st.expander("거절 이유"):
                st.caption(f"단계: {r['stage']} · 이유: {r.get('refusal_reason') or '—'}")
        return

    with st.container(border=True):
        st.markdown(r.get("answer_display") or r["answer"])
        st.markdown(":gray-badge[AI 생성]")
        if flags.get("causality_unconfirmed"):
            st.caption("인과는 공시로 확인되지 않음")
    _render_citations(r["citations"])


def _show_history_item(i: int) -> None:
    st.session_state["qa_last"] = st.session_state["qa_history"][i]


def _render_history() -> None:
    history = st.session_state.get("qa_history") or []
    if not history:
        return
    with st.expander("이전 질문"):
        for i, h in enumerate(history):
            r = h.get("result") or {}
            mark = "거절" if r.get("refused") else f"근거 {len(r.get('citations') or [])}건"
            st.button(f"{h['question']} ({mark})", key=f"qa_hist_{i}", on_click=_show_history_item, args=(i,))


def render():
    filters = st.session_state["filters"]
    ui.header("공시 Q&A", "공시 원문에 근거해 답합니다.", filters, screen_scope="카테고리 미적용")
    _render_scope(filters)
    scope = _scope(filters)
    st.divider()

    asked = None
    with st.container(horizontal=True):
        for i, q in enumerate(EXAMPLES):
            if st.button(q, key=f"qa_example_{i}"):
                asked = q
    with st.form("qa_form", clear_on_submit=False):
        text = st.text_area("질문", placeholder="질문을 입력하세요", max_chars=300)
        if st.form_submit_button("질문하기", type="primary"):
            asked = text
    if asked is None and st.session_state.get("qa_pending"):   # 요약(S0) 화면 검색창에서 넘어온 질문
        asked = st.session_state.pop("qa_pending")
    if asked is not None:
        _submit(asked, scope)

    if st.session_state.get("qa_last"):
        _render_result(st.session_state["qa_last"])
    _render_history()
    ui.limits(LIMITS_S6)
