"""공통 컴포넌트 — docs/05_design/UI_SPECIFICATION.md 3-2절, 문구는 6·7절.

화면 공통 순서: ① header → ② kpis → ③ 본문 → ④ limits.
"""
from datetime import datetime

import streamlit as st

from core import filters as flt
from core.data import meta

LIMITS_COMMON = [
    "뉴스는 국내 언론 중심입니다. 해외(영어) 뉴스 797건은 지정학 이슈(생물보안법·의약품 관세·미국/유럽 현지 생산)만 보강했습니다.",
    "구글 뉴스로 모은 기사(기업명검색·CDMO검색·해외검색)는 제목만 있습니다. 본문 기반 분석은 본문이 있는 출처(제공·팀원수집) 범위입니다.",
    "분석 기업은 국내 상장 5개사입니다. 론자·우시 등 해외 CDMO는 뉴스 언급으로만 다루고, 공시 비교는 5개사로 한정합니다.",
    "산업 보고서·경쟁사 홈페이지는 수집하지 않았습니다. 뉴스·공시로 한정합니다.",
    "CDMO 키워드(카테고리) 분류는 규칙 기반이며 정확도를 검수하지 않았습니다.",
    "기사량은 중복 기사(정규화한 제목이 같고 7일 이내)를 빼고 셉니다.",
]

SENTIMENT_BADGE = {"기회": ":blue-badge[▲ 기회]", "위험": ":red-badge[▼ 위험]", "중립": ":gray-badge[● 중립]"}


def header(title: str, question: str, filters: dict, screen_scope: str | None = None) -> None:
    st.title(title)
    st.caption(f"현재 필터: {flt.status_line(filters, screen_scope)}")
    st.subheader(question)


def kpis(items: list) -> None:
    """items: [{"label", "value", "help", "delta"?, "delta_color"?}] 2~4개. 값은 형식화된 문자열 (없으면 "—").

    delta 는 증감 배지 문자열(예: "+12% 최근 3개월"). delta_color 는 normal(증가=좋음) / inverse(증가=나쁨) / off.
    """
    cols = st.columns(len(items), gap="small")
    for col, it in zip(cols, items):
        col.metric(it["label"], it.get("value") or "—", help=it.get("help"), border=True, height="stretch",
                   delta=it.get("delta"), delta_color=it.get("delta_color", "normal"))   # 증감 줄 유무와 상관없이 카드 높이 같게


def conclusion(text: str, evidence: list) -> None:
    """S0 전용. 근거 링크가 없으면 문장을 표시하지 않는다 (N6)."""
    if not evidence:
        return
    with st.container(border=True):
        st.markdown(text)
        st.caption("근거: " + " · ".join(f"[{e['label']}]({e['url']})" for e in evidence))


def pending(element: str, waiting_for: str) -> None:
    st.info(f"**{element}**  \n준비 중 — {waiting_for} 결과가 생성되면 표시됩니다.",
            icon=":material/hourglass_empty:")


def empty(kind: str, key: str) -> None:
    with st.container(border=True):
        st.markdown(f"현재 필터에 해당하는 {kind}가 없습니다")
        st.button("필터 초기화", key=f"empty_reset_{key}", on_click=flt.reset)


def no_selection(filters: dict, key: str) -> bool:
    """기업이나 카테고리를 0개 고르면 화면 전체를 빈 결과로 둔다 (4-1절 "화면은 빈 결과 상태"). True 면 그리지 않는다."""
    if filters["companies"] and filters["keywords"]:
        return False
    missing = "기업" if not filters["companies"] else "카테고리"
    with st.container(border=True):
        st.markdown(f"사이드바에서 {missing}을(를) 1개 이상 고르세요. 지금은 해당하는 기사·공시가 없습니다.")
        st.button("필터 초기화", key=f"empty_reset_{key}", on_click=flt.reset)
    return True


def data_error(path, err: Exception) -> None:
    st.error(f"데이터를 읽지 못했습니다: {path}  \nREADME의 실행 순서에 따라 데이터를 먼저 만드세요.")
    with st.expander("오류 내용"):
        st.code(f"{type(err).__name__}: {err}")


def _built_at(value: str | None) -> str:
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value


def limits(extra: list | None = None) -> None:
    st.divider()
    m = meta()
    basis = (f"데이터 기준: 기간 {m['period_start']} ~ {m['period_end']} (KST) · DB 빌드 {_built_at(m.get('built_at'))}"
             if m.get("period_start") else "데이터 기준: —")
    with st.expander("데이터 범위·한계", expanded=False):
        st.markdown("\n".join(f"- {line}" for line in LIMITS_COMMON + list(extra or [])))
        st.caption(basis)


def sentiment_badge(label: str) -> str:
    return SENTIMENT_BADGE.get(label, ":gray-badge[미분류]")


def news_line(row: dict) -> None:
    """6-5절 뉴스 형식: <제목> · <매체> · <YYYY-MM-DD> · [원문]. 영어 기사는 번역 배지, 검색어 근거면 배지."""
    title = row.get("title_clean") or row.get("title") or ""
    badges = ""
    if row.get("lang") == "en":
        if row.get("title_ko"):
            title, badges = row["title_ko"], ":gray-badge[번역] "
        else:
            badges = ":gray-badge[번역 준비 중] "
    if row.get("cdmo_kw_basis") == "query":
        badges += ":gray-badge[검색어 근거] "
    link = f"[원문]({row['url']})" if row.get("url") else "원문 없음"
    parts = [f"{badges}{title}", row.get("press") or "", row.get("published_date") or "", link]
    st.markdown(" · ".join(p for p in parts if p))
    if row.get("lang") == "en" and row.get("title_ko"):
        st.caption(f"원제목: {row.get('title')}")


def dart_url(rcept_no: str) -> str:
    return f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"


def disclosure_line(row: dict, ask_button: bool = False, key: str | None = None) -> bool:
    """6-5절 공시 형식: <공시명> · <기업> · <제출일> · [DART] (+ 정정 배지)."""
    url = row.get("url") or dart_url(row["rcept_no"])
    amended = " :gray-badge[정정]" if int(row.get("is_amended") or 0) else ""
    st.markdown(f"{row['report_nm']}{amended} · {row['corp_name']} · {row['rcept_date']} · [DART]({url})")
    return st.button("이 공시에 질문 →", key=key) if ask_button else False


def table_view(df, label: str) -> None:
    with st.expander("표로 보기"):
        st.dataframe(df, hide_index=True, width="stretch")
        st.caption(label)


ROW_CLICK_MODES = ["single-row", "single-cell"]   # 행 체크박스 + 아무 칸 클릭으로 행 선택


def selected_row(key: str) -> int | None:
    """행 선택 표(selection_mode=ROW_CLICK_MODES)의 선택 행 위치. on_select 콜백 안에서 부른다.

    칸을 누르면 그 칸의 행을 체크된 행으로 바꾸고 칸 선택은 지운다. 이미 체크된 행의 칸을 다시 누르면 해제한다.
    체크박스를 직접 눌러 끄는 것도 해제다. 표를 정렬해도 위치는 원래 표 기준이다.
    """
    sel = st.session_state[key]["selection"]
    last = st.session_state.get(f"_{key}_row")
    cells = list(sel.get("cells") or [])
    if cells:
        row = int(cells[0][0])
        row = None if row == last else row
        st.session_state[key] = {"selection": {"rows": [] if row is None else [row], "columns": [], "cells": []}}
    else:
        rows = list(sel.get("rows") or [])
        row = int(rows[0]) if rows else None
    st.session_state[f"_{key}_row"] = row
    return row
