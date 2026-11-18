"""사이드바 필터 (F7) — docs/05_design/UI_SPECIFICATION.md 4-1·4-5절.

위젯 값(flt_*)은 on_change 콜백에서 st.session_state["filters"] 로 옮긴다. 화면 코드는 filters 만 읽는다.
"""
from datetime import date

import streamlit as st

from core.data import COMPANIES, KEYWORDS, PERIOD, meta


def _period_bounds() -> tuple:
    m = meta()
    start = date.fromisoformat(m.get("period_start", PERIOD[0]))
    end = date.fromisoformat(m.get("period_end", PERIOD[1]))
    return start, end


def defaults() -> dict:
    return {"period": _period_bounds(), "companies": list(COMPANIES), "keywords": list(KEYWORDS)}


def init() -> None:
    """첫 실행에 위젯 key 와 filters 를 기본값으로 채운다."""
    if "filters" not in st.session_state:
        d = defaults()
        st.session_state["filters"] = d
        st.session_state["flt_period"] = d["period"]
        st.session_state["flt_companies"] = d["companies"]
        st.session_state["flt_keywords"] = d["keywords"]


def _sync() -> None:
    """위젯 값 → filters. 기간이 시작일만 고른 상태면 기간은 바꾸지 않는다."""
    f = dict(st.session_state["filters"])
    p = st.session_state.get("flt_period")
    if isinstance(p, (tuple, list)) and len(p) == 2:
        f["period"] = (p[0], p[1])
    f["companies"] = [c for c in COMPANIES if c in st.session_state.get("flt_companies", [])]
    f["keywords"] = [k for k in KEYWORDS if k in st.session_state.get("flt_keywords", [])]
    st.session_state["filters"] = f


def reset() -> None:
    """세 위젯과 filters 를 기본값으로. 화면별 상태 key 는 지우지 않는다."""
    d = defaults()
    st.session_state["filters"] = d
    st.session_state["flt_period"] = d["period"]
    st.session_state["flt_companies"] = d["companies"]
    st.session_state["flt_keywords"] = d["keywords"]


def render_sidebar() -> None:
    init()
    start, end = _period_bounds()
    st.date_input("기간", key="flt_period", min_value=start, max_value=end, format="YYYY-MM-DD", on_change=_sync)
    p = st.session_state.get("flt_period")
    if not (isinstance(p, (tuple, list)) and len(p) == 2):
        st.caption("종료일을 고르면 적용됩니다")
    st.multiselect("기업", COMPANIES, key="flt_companies", on_change=_sync)
    if not st.session_state["filters"]["companies"]:
        st.warning("기업을 1개 이상 고르세요")
    st.multiselect("카테고리", KEYWORDS, key="flt_keywords", on_change=_sync)
    if not st.session_state["filters"]["keywords"]:
        st.warning("카테고리를 1개 이상 고르세요")
    st.button("필터 초기화", key="flt_reset", on_click=reset, width="stretch")
    st.caption("필터는 모든 차트에 적용됩니다. 화면별 적용 범위는 각 화면 상단을 보세요.")


def _summary(selected: list, all_items: list, all_text: str, none_text: str, short=lambda x: x) -> str:
    if len(selected) == len(all_items):
        return all_text
    if not selected:
        return none_text
    first = short(selected[0])
    return first if len(selected) == 1 else f"{first} 외 {len(selected) - 1}"


def company_summary(filters: dict) -> str:
    return _summary(filters["companies"], COMPANIES, "5개사 전체", "기업 없음")


def status_line(filters: dict, screen_scope: str | None = None) -> str:
    """4-5절 형식: <시작일> ~ <종료일> · <기업 요약> · <카테고리 요약> [· 이 화면: …]"""
    s, e = filters["period"]
    kw = _summary(filters["keywords"], KEYWORDS, f"카테고리 {len(KEYWORDS)}개 전체", "카테고리 없음",
                  short=lambda k: k.removeprefix("CDMO "))
    line = f"{s:%Y-%m-%d} ~ {e:%Y-%m-%d} · {company_summary(filters)} · {kw}"
    return f"{line} · 이 화면: {screen_scope}" if screen_scope else line
