"""공시 Q&A — F5 (US-16, US-17 / AC-16, AC-17). docs/05_design/UI_SPECIFICATION.md 5-7절.

rag/qa.py ask() 를 질문할 때마다 부른다 (임베딩 1회 + 답변 1회, 결과는 캐시하지 않음).
명세 5-7절은 SystemExit·답변 문구로 상태를 판정하도록 적혀 있었으나(미결 Q3), qa.py 가 QAError·flags·
answer_display 를 돌려주도록 바뀌어 그 값을 쓴다 (NEWS_DISCLOSURE_MATCHING 4-8절).
"""
import math
import re
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

from core import data
from core import filters as flt
from core import ui

RAG_DIR = Path(__file__).resolve().parents[2] / "rag"
# 예시 질문은 평가 20문항(data/eval/rag_questions.csv) 중 검색·핵심 답이 모두 맞은 질문에서 골랐다 (A04·A06·A14).
# 명세(NEWS_DISCLOSURE_MATCHING 5절)의 처음 예시 "생물보안법 논의 이후 … 수주 계약은?"은 정책과 공시를 잇는 질문이라
# 공시만으로는 답할 때와 거절할 때가 갈려(2026-11-19 화면에서 거절) 예시에서 뺐다. 이런 질문은 아래 관련 뉴스로 보완한다.
EXAMPLES = [
    "삼성바이오로직스가 2026년 10월에 자율공시한 의약품 위탁생산계약의 계약금액과 계약기간 종료일은?",
    "바이넥스의 오송공장 신규시설투자 금액과 투자기간은?",
    "SK바이오사이언스의 RSV 예방항체 기술도입 계약의 상대방과 총 계약금액은?",
]
# 거절 시 관련 뉴스: 질문 단어 중 기사 제목 찾기에 쓰지 않는 말과 조사
NEWS_STOP = {"공시", "이후", "이전", "최근", "내용", "무엇", "어떤", "어떻게", "관련", "대해", "알려", "얼마", "있나",
             "논의", "기업", "회사", "시기", "언제", "규모", "이유", "결과", "현황", "체결", "시행", "금액", "누구", "상대방",
             "목적", "방법", "얼마나"}
JOSA = re.compile(r"(했나|하나|인가|일까|는지|으로|에서|에게|까지|부터|의|은|는|가|을|를|에|와|과|도|로|한|된)$")
NEWS_MAX = 5
# 질문·제목에서 기업을 알아보는 짧은 이름 ("삼성바이오가", "SK바이오 …" 처럼 줄여 쓰는 경우)
CORP_STEMS = {"삼성바이오로직스": "삼성바이오", "SK바이오사이언스": "SK바이오", "에스티팜": "에스티팜",
              "바이넥스": "바이넥스", "프레스티지바이오로직스": "프레스티지"}
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


def _terms(question: str) -> list:
    """질문에서 기사 제목과 대조할 단어 (2글자 이상, 조사·질문 상투어 제외)."""
    out = []
    for tok in re.findall(r"[가-힣A-Za-z0-9]{2,}", question):
        tok = JOSA.sub("", tok) if len(tok) > 2 else tok
        if len(tok) >= 2 and tok not in NEWS_STOP and tok not in out:
            out.append(tok)
    return out


def related_news(question: str, scope: dict) -> pd.DataFrame:
    """공시로 답하지 못한 질문에 참고로 보여 줄 뉴스 (LLM 호출 없음).

    질문 속 5개사가 있으면 그 기업이 제목·본문에 나온 기사로 좁힌다. 질문 단어(기업 이름 제외)가 제목에 있으면 점수를
    주되, 드문 단어일수록 무게를 높인다(IDF — "생물보안법"이 "계약"보다 크다). 점수 높은 순, 같으면 최신 순.
    기업이 없는 질문은 단어가 둘 이상 맞아야 보여 준다(한 단어만 겹친 무관한 기사를 막는다). 기간은 질문 범위를 따른다.
    """
    news = data.news_frame()
    if scope.get("date_from"):
        news = news[news.published_date >= scope["date_from"]]
    if scope.get("date_to"):
        news = news[news.published_date <= scope["date_to"]]
    corps = [c for c, stem in CORP_STEMS.items() if stem.lower() in question.lower()]
    if corps:
        nc = data.news_companies()
        news = news[news.news_id.isin(nc[nc.corp_name.isin(corps)].news_id)]
    terms = [t for t in _terms(question) if not any(CORP_STEMS[c].lower() in t.lower() for c in corps)]
    if not terms or news.empty:
        return news.iloc[0:0]
    titles = (news.title_clean.fillna(news.title) + " " + news.title_ko.fillna("")).str.lower()
    hits = {t: titles.str.contains(t.lower(), regex=False) for t in terms}
    n = len(titles)
    weight = {t: math.log((n + 1) / (h.sum() + 1)) + 1 for t, h in hits.items()}
    score = sum(h.astype(float) * weight[t] for t, h in hits.items())
    n_hit = sum(h.astype(int) for h in hits.values())
    if corps:   # 질문의 기업이 제목에도 있으면 가산 (본문에만 나온 기사보다 앞에)
        in_title = sum(titles.str.contains(CORP_STEMS[c].lower(), regex=False).astype(float) for c in corps)
        score = score + 2 * (in_title > 0)
        keep = n_hit >= 1
    else:       # 기업이 없으면 단어 둘 이상 + 가장 드문 단어(질문의 핵심어일 가능성이 큼)가 맞아야 한다
        present = [t for t, h in hits.items() if h.any()]
        rare = max(present, key=lambda t: weight[t]) if present else None
        keep = (n_hit >= 2) & (hits[rare] if rare else False)
    out = news.assign(score=score, n_hit=n_hit)
    out = out[keep]
    out = out.sort_values(["score", "published_date"], ascending=False).head(NEWS_MAX)
    return out.merge(data.sentiment_frame()[["url", "label"]], on="url", how="left")


def _news_md(row: dict) -> str:
    """관련 뉴스 1줄 (강조 상자 안에 넣는 마크다운). 6-5절 뉴스 형식 + 감성 배지."""
    title = row.get("title_clean") or row.get("title") or ""
    prefix = ""
    if row.get("lang") == "en":
        if isinstance(row.get("title_ko"), str) and row["title_ko"]:
            title, prefix = row["title_ko"], ":gray-badge[번역] "
        else:
            prefix = ":gray-badge[번역 준비 중] "
    label = ui.sentiment_badge(row["label"]) + " " if isinstance(row.get("label"), str) else ""
    parts = [f"{label}{prefix}**[{title}]({row['url']})**", row.get("press") or "", row.get("published_date") or ""]
    return " · ".join(p for p in parts if p)


def _render_no_disclosure(entry: dict) -> None:
    """공시 근거 없음 — 오류가 아니라 '이 질문에 해당하는 공시가 없다'는 정상 결과다.

    경고 상자·거절 이유·다시 질문하라는 안내를 쓰지 않고, 중립적인 한 줄로 알린 뒤 관련 뉴스를 색 상자로 강조한다
    (시선이 뉴스로 바로 가게). 뉴스도 없을 때만 질문을 바꿔 보라고 안내한다.
    """
    st.markdown(":gray-badge[공시 근거 없음] 이 질문에 해당하는 공시는 찾지 못해, 공시로 답하지 않았습니다.")
    try:
        news = related_news(entry["question"], entry.get("scope") or {})
    except Exception:
        news = None
    if news is None or news.empty:
        st.info("관련 뉴스도 찾지 못했습니다. 기업명·기간·공시 종류(예: 단일판매·공급계약, 신규시설투자)를 넣어 "
                "다시 질문해 보세요.", icon=":material/search:")
        return
    lines = [f"**관련 뉴스 {len(news)}건** — 질문의 기업·단어가 제목에 들어간 기사입니다 (공시로 확인된 답은 아닙니다)", ""]
    lines += [f"- {_news_md(r.to_dict())}" for _, r in news.iterrows()]
    st.info("\n".join(lines), icon=":material/newspaper:")


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
        else:   # 근거 없음(검색·생성·검증 단계) — 오류가 아니라 정상 결과
            _render_no_disclosure(entry)
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
