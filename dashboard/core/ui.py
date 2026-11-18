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
    """items: [{"label", "value", "help"}] 2~4개. 값은 형식화된 문자열 (없으면 "—")."""
    cols = st.columns(len(items), gap="small")
    for col, it in zip(cols, items):
        col.metric(it["label"], it.get("value") or "—", help=it.get("help"), border=True)


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
