"""규제·정책 — F2, F8 (US-06, US-07, US-08 / AC-06, AC-07, AC-08). docs/05_design/UI_SPECIFICATION.md 5-3절.

대상: 중복 제외 & 카테고리 '규제 및 정책'(CDMO 규제·정책, CDMO 지정학) 기사. 사이드바 카테고리와의 교집합만 본다.
기회/위험/중립 지표, 월별 감성 누적 막대, 날짜순 기사 타임라인(판단 이유 포함), 언급 기업 막대.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import data, theme, ui

SCREEN_KEYWORDS = ["CDMO 규제·정책", "CDMO 지정학"]
LABELS = ["기회", "위험", "중립"]          # 목록·배지 순서 (6-3절)
STACK = ["기회", "중립", "위험"]           # 누적 막대 아래부터
LABEL_HELP = {
    "기회": "CDMO 시장(위탁 수요·수주·투자·생산능력)이 커지는 사건이나 흐름",
    "위험": "CDMO 시장이 줄거나 위축되는 사건이나 흐름",
    "중립": "영향을 판단할 수 없거나 단순 사실 전달",
}
ACCURACY_NOTE = "라벨 정확도: 표본 85.0% (180건) · 층 가중 84.2%"
PAGE = 20
LIMITS_S2 = [
    "기회/위험 라벨은 LLM(gpt-6-luna, sentiment-v3)이 붙였습니다. 표본 180건 검수 정확도 85.0%(층 가중 84.2%, "
    "모두 \"기회\"로 찍을 때 47.2%). 정답 22건은 이전 버전 결과를 본 뒤 고쳐 수치가 높게 나왔을 수 있습니다.",
    "라벨은 제목만 보고 붙인 기사가 3,505건, 제목+본문 1,222건입니다(전체 4,727건).",
    "해외 뉴스는 지정학 이슈만 보강되었습니다.",
]


def _reset_rows() -> None:
    st.session_state["s2_rows"] = PAGE


def _more_rows() -> None:
    st.session_state["s2_rows"] = st.session_state.get("s2_rows", PAGE) + PAGE


def _load(filters: dict) -> pd.DataFrame:
    """화면 대상 기사 + 감성 라벨. 사이드바 기간·기업 규칙은 filter_news 를 그대로 쓴다."""
    scoped = {**filters, "keywords": [k for k in SCREEN_KEYWORDS if k in filters["keywords"]]}
    news = data.filter_news(scoped)
    return news.merge(data.sentiment_frame(), on="url", how="inner")


def _monthly_chart(df: pd.DataFrame, filters: dict, key: str) -> None:
    mode = theme.current_mode()
    t = theme.TOKENS[mode]
    s, e = (pd.Timestamp(x) for x in filters["period"])
    months = pd.date_range(s.to_period("M").start_time, e.to_period("M").start_time, freq="MS")
    table = (df.assign(m=df.date.dt.to_period("M").dt.start_time)
             .pivot_table(index="m", columns="label", values="news_id", aggfunc="count", fill_value=0)
             .reindex(index=months, columns=STACK, fill_value=0))
    fig = go.Figure()
    for label in STACK:
        fig.add_trace(go.Bar(x=table.index, y=table[label], name=f"{label}",
                             marker=dict(color=theme.SENTIMENT_COLOR[mode][label], line=dict(width=1, color=t["bg"])),
                             hovertemplate="<b>%{fullData.name}</b> %{y:,}건<extra></extra>"))
    fig.update_layout(barmode="stack")
    theme.style(fig, "time", height="sub")
    fig.update_layout(showlegend=True, legend_traceorder="normal")
    fig.update_xaxes(hoverformat="%Y-%m")
    theme.show(fig, key=key, alt="월별 규제·정책 기사 수, 기회·중립·위험 누적 (중복 제외)")
    out = table.copy()
    out.index = out.index.strftime("%Y-%m")
    out["합계"] = out.sum(axis=1)
    ui.table_view(out.rename_axis("월").reset_index(), "월별 감성 라벨 건수")


def _company_chart(df: pd.DataFrame, key: str) -> None:
    mode = theme.current_mode()
    nc = data.news_companies()
    counts = nc[nc.news_id.isin(df.news_id)].groupby("corp_name").news_id.nunique() \
        .reindex(data.COMPANIES, fill_value=0)
    fig = go.Figure(go.Bar(
        x=counts.values, y=counts.index, orientation="h",
        marker=dict(color=[theme.COMPANY_COLOR[mode][c] for c in counts.index]),
        hovertemplate="%{y} · %{x:,}건<extra></extra>"))
    theme.style(fig, "bar", height="sub")
    fig.update_yaxes(autorange="reversed", showgrid=False)   # IA 순서를 위에서 아래로
    fig.update_xaxes(showgrid=True, gridcolor=theme.TOKENS[mode]["grid"])
    theme.show(fig, key=key, alt="5개사별 규제·정책 기사 언급 수 (제목·본문에 기업명이 있는 기사)")
    st.caption("기업명이 제목·본문에 나온 기사 수입니다. 한 기사에 여러 기업이 나오면 기업마다 셉니다.")


def _article_row(r: pd.Series) -> None:
    title = r.title_clean if isinstance(r.title_clean, str) and r.title_clean else r.title
    prefix = ""
    if r.lang == "en":
        if isinstance(r.title_ko, str) and r.title_ko:
            title, prefix = r.title_ko, ":gray-badge[번역] "
        else:
            prefix = ":gray-badge[번역 준비 중] "
    press = f" · {r.press}" if isinstance(r.press, str) and r.press else ""
    st.markdown(f"{r.published_date} · {ui.sentiment_badge(r.label)} · {prefix}[{title}]({r.url}){press} · "
                f"[원문]({r.url})")
    notes = ["제목+본문" if r.input_basis == "title+body" else "제목만"]
    if r.confidence == "low":
        notes.append(":gray-badge[확신도 낮음]")
    if r.cdmo_kw_basis == "query":
        notes.append(":gray-badge[검색어 근거]")
    if r.lang == "en" and isinstance(r.title_ko, str) and r.title_ko:
        notes.append(f"원제목: {r.title}")
    st.caption(" · ".join(notes))
    with st.expander("판단 이유"):
        st.markdown(f"{r.reason}  \n:gray-badge[AI 생성] `{r.model} · {r.prompt_version}`")


def _timeline(df: pd.DataFrame) -> None:
    head, c1, c2 = st.columns([3, 3, 2], gap="small", vertical_alignment="bottom")
    head.markdown("#### 정책·규제 타임라인")
    labels = c1.multiselect("라벨", LABELS, default=LABELS, key="s2_label", on_change=_reset_rows)
    lang = c2.segmented_control("언어", ["전체", "한국어", "영어"], key="s2_lang", default="전체", required=True,
                                on_change=_reset_rows)
    rows = df[df.label.isin(labels)]
    if lang == "한국어":
        rows = rows[rows.lang != "en"]
    elif lang == "영어":
        rows = rows[rows.lang == "en"]
    if rows.empty:
        ui.empty("기사", "S2-C2")
        return
    rows = rows.sort_values(["published_date", "published_at"], ascending=False)
    n = st.session_state.get("s2_rows", PAGE)
    st.caption(f"{len(rows):,}건 중 {min(n, len(rows)):,}건 표시 · 최신순")
    for _, r in rows.head(n).iterrows():
        with st.container(border=True):
            _article_row(r)
    if n < len(rows):
        st.button("더 보기", key="s2_more", on_click=_more_rows)


def render():
    filters = st.session_state["filters"]
    ui.header("규제·정책", "정책·규제 변화는 CDMO 시장에 기회인가 위험인가?", filters,
              screen_scope="규제·정책, 지정학")
    if not any(k in filters["keywords"] for k in SCREEN_KEYWORDS):
        st.info("이 화면은 규제·정책, 지정학 기사만 다룹니다. 사이드바 카테고리에 이 중 하나 이상을 넣으세요.")
        ui.limits(LIMITS_S2)
        return
    try:
        with st.spinner("데이터를 불러오는 중"):
            df = _load(filters)
    except Exception as e:
        ui.data_error(data.SENTIMENT_PATH, e)
        ui.limits(LIMITS_S2)
        return

    counts = df.label.value_counts()
    ui.kpis([{"label": f"{'▲' if lb == '기회' else '▼' if lb == '위험' else '●'} {lb}",
              "value": f"{int(counts.get(lb, 0)):,}건", "help": LABEL_HELP[lb]} for lb in LABELS])
    st.caption(ACCURACY_NOTE)
    st.divider()

    if df.empty:
        ui.empty("기사", "S2-C1")
        ui.limits(LIMITS_S2)
        return
    fkey = abs(hash((str(filters["period"]), tuple(filters["companies"]), tuple(filters["keywords"]))))
    st.markdown("#### 월별 기사 수 — 기회/위험/중립")
    _monthly_chart(df, filters, key=f"s2_month_{fkey}")

    _timeline(df)

    st.markdown("#### 언급 기업")
    left, right = st.columns([3, 2], gap="medium")
    with left:
        _company_chart(df, key=f"s2_corp_{fkey}")
    with right:
        ui.pending("해외 CDMO 언급 수", "해외 CDMO 언급 집계 기준 정의")
    ui.limits(LIMITS_S2)
