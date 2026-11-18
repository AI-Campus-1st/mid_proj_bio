"""이슈·트렌드 — F1 (US-03, US-04, US-05 / AC-03, AC-04, AC-05). docs/05_design/UI_SPECIFICATION.md 5-2절.

기사량 추이(출처별 누적 막대 / 키워드별 소형 다중 차트)와 급증 시점, 선택한 급증의 대표 기사·같은 시기 공시.
부상 이슈(S1-C4)는 LLM 이슈(issues_llm.csv + issue_groups.csv)로 최근 3개월과 직전 3개월을 비교한다
(기준과 근거: AI_CLASSIFICATION 3-8절).
"""
import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from core import data, theme, ui

LIMITS_S1 = [
    "출처별 기사량은 따로 해석하세요. 팀원수집·CDMO검색 기사는 2026년에 몰려 있습니다.",
    "급증은 기사 건수 기준이며 기사 내용의 중요도가 아닙니다. 판정 기준(주별 z ≥ 3, 직전 26주 중앙값)은 민감도를 검증하지 않았습니다.",
    "2024-01 중순 이전은 급증을 판정하지 않습니다.",
    "급증 판정에서 팀원수집 1,306건은 제외했습니다.",
    "이슈 이름(LLM 추출)은 표본 30건 검수에서 98.7%(층 가중)가 정확했습니다.",
    "부상 이슈는 필터 기간 끝에서 최근 3개월과 직전 3개월을 비교하며, 최근 3개월 기사 5건 이상인 이슈만 증가 건수 순으로 보입니다. 팀원수집 제외 토글을 따릅니다.",
]
EVENT_NOTE = "정기 행사 주간의 급증입니다 (바이오 USA 6월, CPHI 10월)"


# ---------------------------------------------------------------- 집계

def _bucket(dates: pd.Series, unit: str) -> pd.Series:
    """월 = 그 달 1일, 주 = 월요일 시작 주 (eda.py 와 같은 기준)."""
    return dates.dt.to_period("M" if unit == "월" else "W-SUN").dt.start_time


def _axis(filters: dict, unit: str) -> pd.DatetimeIndex:
    s, e = (pd.Timestamp(x) for x in filters["period"])
    if unit == "월":
        return pd.date_range(s.to_period("M").start_time, e.to_period("M").start_time, freq="MS")
    return pd.date_range(s.to_period("W-SUN").start_time, e.to_period("W-SUN").start_time, freq="W-MON")


def _by_origin(news: pd.DataFrame, filters: dict, unit: str, excl_team: bool) -> pd.DataFrame:
    origins = [o for o in data.ORIGIN_KO.values() if not (excl_team and o == "팀원수집")]
    df = news[news.origin_ko.isin(origins)]
    table = (df.assign(x=_bucket(df.date, unit)).pivot_table(index="x", columns="origin_ko", values="news_id",
                                                              aggfunc="count", fill_value=0)
             .reindex(index=_axis(filters, unit), columns=origins, fill_value=0))
    table.index.name = "기간"
    return table


def _by_keyword(news: pd.DataFrame, filters: dict, unit: str, excl_team: bool) -> pd.DataFrame:
    """대표 키워드(is_primary=1), 검색어만 근거인 기사 제외 — eda_keyword_monthly.csv 와 같은 기준."""
    kw = data.news_keywords()
    df = news[news.cdmo_kw_basis != "query"]
    if excl_team:
        df = df[df.origin != "team"]
    k = kw[(kw.is_primary == 1) & kw.keyword.isin(filters["keywords"])].merge(df, on="news_id")
    table = (k.assign(x=_bucket(k.date, unit)).pivot_table(index="x", columns="keyword", values="news_id",
                                                            aggfunc="count", fill_value=0)
             .reindex(index=_axis(filters, unit), columns=filters["keywords"], fill_value=0))
    table.index.name = "기간"
    return table


# ---------------------------------------------------------------- 선택 상태 (s1_spike, L3)

def _select_from_table() -> None:
    rows = st.session_state["s1_spike_tbl"]["selection"]["rows"]
    ids = st.session_state.get("_s1_tbl_ids", [])
    st.session_state["s1_spike"] = ids[rows[0]] if rows and rows[0] < len(ids) else None


def _select_from_chart(key: str) -> None:
    """● 클릭 → s1_spike. 시계열 차트는 'x unified' 호버라 클릭이 같은 기간의 막대로 잡힐 수 있어,
    customdata 가 없으면 클릭한 점의 기간(x)에 찍힌 급증을 쓴다."""
    points = st.session_state[key]["selection"]["points"]
    marks = st.session_state.get("_s1_marks", {})
    for p in points:
        cd = p.get("customdata")
        sid = cd[0] if isinstance(cd, (list, tuple)) and cd else cd
        if isinstance(sid, str) and sid.count("|") == 2:
            st.session_state["s1_spike"] = sid
            return
    for p in points:
        sid = marks.get(str(p.get("x", ""))[:10])
        if sid:
            st.session_state["s1_spike"] = sid
            return


# ---------------------------------------------------------------- 차트

def _spike_marks(fig, spikes: pd.DataFrame, unit: str, y_top: float, color: str, row=None, col=None) -> None:
    """급증 시점: 세로 점선 + 위쪽 ● (x 위치에만, 막대 높이에 얹지 않음). 행사 주간은 '행사' 주석."""
    if spikes.empty:
        return
    sp = spikes.assign(x=_bucket(spikes.peak, unit))
    for x in sp.x.unique():
        fig.add_vline(x=x, line_dash="dot", line_width=1, line_color=color, row=row, col=col)
    grouped = sp.sort_values("z", ascending=False).groupby("x", sort=False)
    xs, ids, texts, labels = [], [], [], []
    for x, g in grouped:
        xs.append(x)
        ids.append(g.spike_id.iloc[0])
        texts.append("<br>".join(f"{r.peak_week} 주 · {r.scope} · {r.peak_count:,}건 (z {r.z:.1f})"
                                 + (f" · {r.event}" if r.event else "") for r in g.itertuples()))
        labels.append("행사" if (g.event != "").any() else "")
    st.session_state.setdefault("_s1_marks", {}).update(
        {pd.Timestamp(x).strftime("%Y-%m-%d"): sid for x, sid in zip(xs, ids)})
    fig.add_trace(go.Scatter(x=xs, y=[y_top] * len(xs), mode="markers+text", name="급증 시점",
                             marker=dict(symbol="circle", size=10, color=color), text=labels,
                             textposition="middle right", textfont=dict(size=12, color=color),
                             customdata=[[i] for i in ids], hovertemplate="%{hovertext}<extra>급증</extra>",
                             hovertext=texts, showlegend=False), row=row, col=col)


def _origin_chart(table: pd.DataFrame, spikes: pd.DataFrame, unit: str, key: str) -> None:
    mode = theme.current_mode()
    t = theme.TOKENS[mode]
    fig = go.Figure()
    fmt = "%Y-%m" if unit == "월" else "%Y-%m-%d"
    for origin in table.columns:
        fig.add_trace(go.Bar(x=table.index, y=table[origin], name=origin,
                             marker=dict(color=theme.ORIGIN_COLOR[mode][origin], line=dict(width=1, color=t["bg"])),
                             unselected=dict(marker=dict(opacity=1)),  # ● 선택 때 막대가 흐려지지 않게
                             hovertemplate=f"<b>%{{fullData.name}}</b> %{{y:,}}건<extra></extra>"))
    total = table.sum(axis=1)
    y_top = float(total.max() or 1) * 1.08
    _spike_marks(fig, spikes, unit, y_top, t["text"])
    fig.update_layout(barmode="stack")
    theme.style(fig, "time")
    fig.update_xaxes(tickformat=fmt, hoverformat=fmt)
    fig.update_layout(showlegend=True, legend_traceorder="normal")
    theme.show(fig, key=key, alt=f"{unit}별 기사 수, 출처별 누적, 중복 제외. 점선과 ●은 급증 시점",
               on_select=lambda: _select_from_chart(key), selection_mode="points")


def _keyword_chart(table: pd.DataFrame, spikes: pd.DataFrame, unit: str, key: str) -> None:
    mode = theme.current_mode()
    t = theme.TOKENS[mode]
    kws = list(table.columns)
    rows = math.ceil(len(kws) / 3)
    fig = make_subplots(rows=rows, cols=3, shared_yaxes="all", shared_xaxes=True,
                        subplot_titles=[k.removeprefix("CDMO ") for k in kws], vertical_spacing=0.12)
    y_top = float(table.values.max() or 1) * 1.1
    for i, kw in enumerate(kws):
        r, c = i // 3 + 1, i % 3 + 1
        fig.add_trace(go.Scatter(x=table.index, y=table[kw], mode="lines", name=kw,
                                 line=dict(width=2, color=t["series-volume"]),
                                 unselected=dict(marker=dict(opacity=1)),
                                 hovertemplate=f"{kw}<br>%{{x|%Y-%m-%d}} · %{{y:,}}건<extra></extra>"),
                      row=r, col=c)
        _spike_marks(fig, spikes[(spikes.series == "키워드") & (spikes.scope == kw)], unit, y_top, t["text"], r, c)
    theme.style(fig, "bar", height=theme.HEIGHT["small"] * rows + 40)
    fig.update_layout(showlegend=False, hovermode="closest", margin=dict(l=8, r=8, t=28, b=8))
    fig.update_annotations(font=dict(size=12, color=t["text"]))
    fig.update_xaxes(tickformat="%Y-%m")
    theme.show(fig, key=key, alt=f"키워드별 {unit} 기사 수 (대표 키워드, 검색어 근거 제외). ●은 그 키워드의 급증 시점",
               on_select=lambda: _select_from_chart(key), selection_mode="points")


# ---------------------------------------------------------------- 급증 목록·근거

def _spike_table(spikes: pd.DataFrame) -> None:
    st.markdown("#### 급증 시점 목록")
    if spikes.empty:
        ui.empty("기사", "S1-C2")
        return
    st.session_state["_s1_tbl_ids"] = spikes.spike_id.tolist()
    view = pd.DataFrame({
        "주간": spikes.peak_week, "구분": spikes.series, "대상": spikes.scope.str.removeprefix("CDMO "),
        "기사 수": spikes.peak_count, "평소": spikes.baseline.round(1), "z": spikes.z.round(1),
        "상위어": spikes.top_terms.map(lambda s: ", ".join(s.split(", ")[:5])),
    })
    st.dataframe(view, hide_index=True, width="stretch", height=360, key="s1_spike_tbl",
                 on_select=_select_from_table, selection_mode="single-row",
                 column_config={"상위어": st.column_config.TextColumn(width="large"),
                                "평소": st.column_config.NumberColumn(format="%.1f"),
                                "z": st.column_config.NumberColumn(format="%.1f")})
    st.caption("행을 고르거나 차트의 ●을 누르면 오른쪽에 대표 기사가 보입니다.")


def _spike_detail(spikes: pd.DataFrame) -> None:
    st.markdown("#### 선택한 급증 시점의 대표 기사")
    sid = st.session_state.get("s1_spike")
    hit = spikes[spikes.spike_id == sid] if sid else spikes.iloc[0:0]
    if hit.empty:
        st.caption("급증 시점을 고르면 대표 기사가 보입니다")
        return
    row = hit.iloc[0]
    articles, disclosures = data.spike_evidence(row)
    with st.container(border=True):
        st.markdown(f"**{row.peak_week} 주 · {row.scope}** — {row.peak_count:,}건 (평소 {row.baseline:.1f}, z {row.z:.1f})")
        if row.event:
            st.caption(EVENT_NOTE)
        for a in articles:
            ui.news_line(a)
        st.markdown("**같은 시기 공시**")
        if not disclosures:
            st.caption("같은 시기 공시 없음")
        for d in disclosures:
            amended = " :gray-badge[정정]" if d["report_nm"].startswith("[기재정정]") else ""
            st.markdown(f":gray-badge[{d['event_class']}] {d['report_nm']}{amended} · {d['rcept_date']} · "
                        f"[DART]({d['url']})")


# ---------------------------------------------------------------- 부상 이슈 (S1-C4)

EMERGE_DAYS = 91   # 비교 구간 길이 (최근·직전 각각)
EMERGE_MIN = 5     # 최근 구간 최소 기사 수


def _emerging(news: pd.DataFrame, filters: dict) -> dict:
    """필터된 기사(news)로 이슈별 최근·직전 기사 수를 세고 증가 건수(최근 − 직전) 순으로 정렬한다.
    직전 0건은 증가율 대신 "신규"로 표시한다."""
    s, e = (pd.Timestamp(x) for x in filters["period"])
    cur = (e - pd.Timedelta(days=EMERGE_DAYS - 1), e)
    prev = (cur[0] - pd.Timedelta(days=EMERGE_DAYS), cur[0] - pd.Timedelta(days=1))
    out = {"table": None, "cur": cur, "prev": prev, "reason": "", "articles": None}
    if prev[0] < s:
        out["reason"] = "필터 기간이 6개월 이상이어야 계산합니다"
        return out
    art = news.merge(data.issues_frame(), on="url")
    art = art[(art.date >= prev[0]) & (art.date <= cur[1])]
    art = art.assign(window=(art.date >= cur[0]).map({True: "cur", False: "prev"}))
    cnt = art.pivot_table(index="issue_group", columns="window", values="news_id", aggfunc="nunique", fill_value=0)
    cnt = cnt.reindex(columns=["prev", "cur"], fill_value=0)
    cnt = cnt[(cnt.cur >= EMERGE_MIN) & (cnt.cur > cnt.prev)].copy()
    if cnt.empty:
        out["reason"] = f"최근 3개월 기사 {EMERGE_MIN}건 이상이면서 늘어난 이슈가 없습니다"
        return out
    cnt["diff"] = cnt.cur - cnt.prev
    cnt = cnt.sort_values(["diff", "cur"], ascending=False)
    rate = [f"{(c - p) / p * 100:+,.0f}%" if p else "신규" for c, p in zip(cnt.cur, cnt.prev)]
    out["table"] = pd.DataFrame({
        "이슈명": cnt.index, "증가율": rate, "증가 건수": cnt["diff"].values,
        "기간": f"{cur[0]:%Y-%m-%d} ~ {cur[1]:%Y-%m-%d}", "기사 수": cnt.cur.values, "직전 3개월": cnt.prev.values})
    out["articles"] = art
    return out


def _select_issue() -> None:
    rows = st.session_state["s1_issue_tbl"]["selection"]["rows"]
    ids = st.session_state.get("_s1_issue_ids", [])
    st.session_state["s1_issue"] = ids[rows[0]] if rows and rows[0] < len(ids) else None


def _go_linkage(companies: list, period: tuple) -> None:
    """L4 — 선택 이슈의 최근 기사에 나온 기업과 최근 구간을 사이드바 필터에 넣는다 (콜백, UI 명세 4-4절)."""
    f = dict(st.session_state["filters"])
    if companies:
        f["companies"] = [c for c in data.COMPANIES if c in companies]
        st.session_state["flt_companies"] = f["companies"]
    f["period"] = period
    st.session_state["flt_period"] = period
    st.session_state["filters"] = f


def _linkage_page():
    from views import s5_linkage
    return st.Page(s5_linkage.render, title="뉴스-공시 연계", url_path="linkage")


def _emerging_section(news: pd.DataFrame, filters: dict) -> None:
    st.markdown("#### 부상 이슈 (직전 3개월 대비) :gray-badge[AI 생성]")
    g = _emerging(news, filters)
    if g["table"] is None:
        st.caption(g["reason"])
        return
    table = g["table"]
    st.caption(f"최근 3개월 {g['cur'][0]:%Y-%m-%d}~{g['cur'][1]:%Y-%m-%d} vs 직전 {g['prev'][0]:%Y-%m-%d}~"
               f"{g['prev'][1]:%Y-%m-%d} · 최근 기사 {EMERGE_MIN}건 이상, 증가 건수 순 · 이슈 이름은 LLM 추출 결과입니다 "
               "(표본 사람 검수 이름 98.7%)")
    st.session_state["_s1_issue_ids"] = table["이슈명"].tolist()
    st.dataframe(table, hide_index=True, width="stretch", height=min(36 * (len(table) + 1) + 4, 400),
                 key="s1_issue_tbl", on_select=_select_issue, selection_mode="single-row",
                 alt="부상 이슈 — 최근 3개월 기사 수가 직전 3개월보다 많이 늘어난 순",
                 column_config={"이슈명": st.column_config.TextColumn(width="large")})
    sel = st.session_state.get("s1_issue")
    sel = sel if sel in set(table["이슈명"]) else None
    art = g["articles"]
    recent = art[(art.issue_group == sel) & (art.window == "cur")].drop_duplicates("news_id") if sel else art.iloc[0:0]
    nc = data.news_companies()
    companies = sorted(set(nc[nc.news_id.isin(recent.news_id)].corp_name)) if sel else []
    c1, c2 = st.columns(2, gap="small")
    show = c1.button("대표 기사", key="s1_issue_articles", disabled=sel is None, width="stretch")
    if c2.button("관련 공시 →", key="s1_issue_link", disabled=sel is None, width="stretch",
                 on_click=_go_linkage, args=(companies, (g["cur"][0].date(), g["cur"][1].date())),
                 help="선택한 이슈의 최근 기사에 나온 기업과 최근 3개월로 필터를 바꾸고 뉴스-공시 연계 화면으로 갑니다. "
                      "이슈 자체는 넘어가지 않습니다 (S5는 키워드 × 기업 × 월로 묶음)"):
        st.switch_page(_linkage_page())
    if sel is None:
        st.caption("행을 고르면 대표 기사와 관련 공시로 갈 수 있습니다")
    elif show or st.session_state.get("_s1_issue_open") == sel:
        st.session_state["_s1_issue_open"] = sel
        with st.container(border=True):
            st.markdown(f"**{sel}** — 최근 3개월 {len(recent):,}건 (최근순 10건)")
            for r in recent.sort_values("date", ascending=False).head(10).to_dict("records"):
                ui.news_line(r)
            if companies:
                st.caption("기사에 나온 기업: " + ", ".join(companies))
    ui.table_view(table, "부상 이슈 (최근 3개월 기사 5건 이상, 증가 건수 순)")


# ---------------------------------------------------------------- 화면

def render():
    filters = st.session_state["filters"]
    ui.header("이슈·트렌드", "지금 가장 많이 다뤄지는 이슈는?", filters)
    if ui.no_selection(filters, "S1"):
        ui.limits(LIMITS_S1)
        return
    try:
        with st.spinner("데이터를 불러오는 중"):
            news = data.filter_news(filters)
            spikes = data.filter_spikes(filters)
    except FileNotFoundError as e:
        ui.data_error(e.args[0] if e.args else data.DB_PATH, e)
        ui.limits(LIMITS_S1)
        return
    except Exception as e:
        ui.data_error(data.SPIKES_PATH, e)
        ui.limits(LIMITS_S1)
        return

    excl_team = st.session_state.get("s1_excl_team", True)
    counted = news[news.origin != "team"] if excl_team else news
    ui.kpis([
        {"label": "기사 (중복 제외)", "value": f"{len(counted):,}건",
         "help": "중복(dup_of) 제외" + (", 팀원수집 제외" if excl_team else ", 팀원수집 포함")},
        {"label": "급증 시점", "value": f"{len(spikes):,}회", "help": "급증 판정: 주별 z ≥ 3, eda_report 4절"},
        {"label": "최근 급증", "value": spikes.peak_week.max() if len(spikes) else "—",
         "help": "선택 범위의 급증 중 가장 최근 주(월요일)"},
    ])
    st.divider()

    head, c1, c2, c3 = st.columns([3, 2, 2, 2], gap="small", vertical_alignment="bottom")
    head.markdown("#### 기사량 추이")
    unit = c1.segmented_control("단위", ["월", "주"], key="s1_unit", default="월", required=True)
    series = c2.segmented_control("계열", ["출처별", "키워드별"], key="s1_series", default="출처별", required=True)
    c3.toggle("팀원수집 제외", key="s1_excl_team", value=True)

    if counted.empty:
        ui.empty("기사", "S1-C1")
    else:
        st.session_state["_s1_marks"] = {}  # 이번 차트에 찍은 ● (기간 → 급증), 클릭 판정용
        fkey = abs(hash((str(filters["period"]), tuple(filters["companies"]), tuple(filters["keywords"]),
                         unit, series, excl_team)))
        if series == "출처별":
            table = _by_origin(news, filters, unit, excl_team)
            # 전체 기사량 차트에는 그 계열에서 판정한 급증만 찍는다: 5개사 전체면 산업 전체, 일부면 그 기업들.
            # (키워드·기업 급증까지 모두 찍으면 거의 매달 ●이 붙어 읽히지 않는다. 목록 표에는 전부 남긴다)
            all_corps = len(filters["companies"]) == len(data.COMPANIES)
            marks = spikes[spikes.series == ("산업 전체" if all_corps else "기업")]
            _origin_chart(table, marks, unit, key=f"s1_chart_{fkey}")
        elif not filters["keywords"]:
            ui.empty("기사", "S1-C1-kw")
            table = None
        else:
            table = _by_keyword(news, filters, unit, excl_team)
            _keyword_chart(table, spikes, unit, key=f"s1_chart_{fkey}")
        if spikes.empty:
            st.caption("선택한 범위에 급증 시점이 없습니다")
        if table is not None:
            out = table.copy()
            out.index = out.index.strftime("%Y-%m" if unit == "월" else "%Y-%m-%d")
            ui.table_view(out.reset_index(), f"{unit}별 기사 수 ({series}, 중복 제외"
                          + (", 팀원수집 제외)" if excl_team else ")"))

    left, right = st.columns(2, gap="medium")
    with left:
        _spike_table(spikes)
    with right:
        _spike_detail(spikes)

    _emerging_section(counted, filters)
    ui.limits(LIMITS_S1)
