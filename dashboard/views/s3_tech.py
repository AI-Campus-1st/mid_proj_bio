"""기술·생산 — F3 (US-09, US-10 / AC-09, AC-10). docs/05_design/UI_SPECIFICATION.md 5-4절.

모달리티별 언급 추이와 기업 × 모달리티 히트맵은 LLM 모달리티 태그(analysis/tag_modality.py,
data/processed/modality_llm.csv)로, 증설 공시 목록은 DB 공시로 그린다.
기사 범위는 사이드바 카테고리와 'CDMO 모달리티·생산능력'의 교집합이다 (4-3절, 2026-11-18 명세대로 하기로 결정).
"""
import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from core import data, theme, ui

LIMITS_S3 = [
    "모달리티 태그는 LLM(gpt-6-luna, modality-v2)이 기사마다 붙였고 사람 검수 전입니다. "
    "기사에 이름이 나온 모달리티만 붙였고, 기업의 주력 분야로 추측하지 않았습니다.",
    "제목만 있는 기사(약 74%)는 제목에 모달리티가 없으면 태그가 없어, 언급 수가 실제보다 적게 잡힙니다.",
    "히트맵 칸은 '그 기업이 언급된 기사 중 그 모달리티를 다룬 기사 수'입니다. 여러 기업이 나오는 기사(행사·업계 기사)는 "
    "다른 기업의 모달리티가 그 기업 칸에도 세어집니다.",
    "이 화면은 CDMO 모달리티·생산능력 카테고리 기사만 셉니다. 모달리티 태그가 붙은 기사의 약 18%(다른 카테고리, 예: ADC 수주 기사)는 빠집니다.",
    "'기타' 태그(저분자·오가노이드 등)는 CDMO 생산 모달리티로 보기 어려워 표시하지 않습니다.",
]
TAG_BADGE = ":gray-badge[AI 생성]"
SEQ_DARK_TEXT = {"#256ABF", "#184F95", "#0D366B"}   # 순차 8~10단계 칸은 흰 글자 (2-3절 대비 검증)


# ---------------------------------------------------------------- 집계

def _tagged(news: pd.DataFrame) -> pd.DataFrame:
    """필터된 기사 × 모달리티 (기사당 태그 수만큼 행)."""
    return data.modality_frame().merge(news[["news_id", "url", "date", "title", "title_clean", "press",
                                              "published_date", "lang", "title_ko", "cdmo_kw_basis"]], on="url")


def _monthly(tagged: pd.DataFrame, filters: dict) -> pd.DataFrame:
    s, e = (pd.Timestamp(x) for x in filters["period"])
    axis = pd.date_range(s.to_period("M").start_time, e.to_period("M").start_time, freq="MS")
    t = tagged.assign(x=tagged.date.dt.to_period("M").dt.start_time)
    table = (t.pivot_table(index="x", columns="modality", values="news_id", aggfunc="nunique", fill_value=0)
             .reindex(index=axis, columns=data.MODALITIES, fill_value=0))
    table.index.name = "월"
    return table


# 최다 증가 모달리티 기준 (2026-11-18 결정, hanju.md 기록)
GROWTH_DAYS = 91      # 3개월. 1개월은 끝 날짜를 2주만 옮겨도 상위 10개가 0~7개만 겹쳐 불안정했고, 3개월은 5~9개 유지
GROWTH_MIN = 5        # 1등 모달리티의 최근 3개월 기사가 이보다 적으면 "—". 기업을 하나만 고르는 등 숫자가 작을 때
                      # 1→3건 같은 변화로 판단하지 않게 한다 (기본 필터에서는 7개 모두 13건 이상이라 걸러지는 것 없음)


def _growth(tagged: pd.DataFrame, filters: dict) -> dict:
    """사이드바 기간 끝 날짜 기준 최근 3개월과 직전 3개월의 모달리티별 기사 수.

    순위는 증가 건수(최근 − 직전)다. 증가율(배수)로 줄 세우면 작은 숫자(1→5건 = +400%)가 위로 오고,
    발표일이 기간 경계에 걸린 큰 사건이 밀린다. 직전 0건도 계산 불가 없이 함께 정렬된다.
    돌려주는 dict: table(7개 모달리티 표, 증가 건수 내림차순), top(1등 행 또는 None), reason(top 이 없을 때 이유),
    cur/prev(각 기간의 시작·끝 Timestamp).
    """
    s, e = (pd.Timestamp(x) for x in filters["period"])
    cur = (e - pd.Timedelta(days=GROWTH_DAYS - 1), e)
    prev = (cur[0] - pd.Timedelta(days=GROWTH_DAYS), cur[0] - pd.Timedelta(days=1))
    out = {"table": None, "top": None, "reason": "", "cur": cur, "prev": prev}
    if prev[0] < s:
        # 직전 3개월이 사이드바 기간 밖이면 tagged 에 그 기사가 없어 직전 건수가 0으로 잘못 잡힌다
        out["reason"] = "사이드바 기간이 6개월 이상이어야 계산합니다"
        return out

    def count(lo, hi):
        t = tagged[(tagged.date >= lo) & (tagged.date <= hi)]
        return t.groupby("modality").news_id.nunique().reindex(data.MODALITIES, fill_value=0)

    c, p = count(*cur), count(*prev)
    table = pd.DataFrame({"모달리티": data.MODALITIES, "직전 3개월": p.values, "최근 3개월": c.values})
    table["증가 건수"] = table["최근 3개월"] - table["직전 3개월"]
    table["증가율"] = [f"{(x - y) / y * 100:+.0f}%" if y else ("신규" if x else "—")
                     for x, y in zip(table["최근 3개월"], table["직전 3개월"])]
    table = table.sort_values(["증가 건수", "최근 3개월"], ascending=False, ignore_index=True)
    out["table"] = table
    top = table.iloc[0]
    if top["증가 건수"] <= 0:
        out["reason"] = "직전 3개월보다 늘어난 모달리티가 없습니다"
    elif top["최근 3개월"] < GROWTH_MIN:
        out["reason"] = f"최근 3개월 기사가 {GROWTH_MIN}건 미만이라 판단하지 않습니다"
    else:
        out["top"] = top
    return out


def _growth_kpi(g: dict) -> dict:
    span = (f"직전 {g['prev'][0]:%Y-%m-%d}~{g['prev'][1]:%Y-%m-%d} · 최근 {g['cur'][0]:%Y-%m-%d}~{g['cur'][1]:%Y-%m-%d}")
    rule = "사이드바 기간 끝 날짜 기준 최근 3개월과 직전 3개월 비교, 증가 건수 순."
    if g["top"] is None:
        return {"label": "최다 증가 모달리티", "value": "—", "help": f"{g['reason']}. {rule}"}
    t = g["top"]
    return {"label": "최다 증가 모달리티", "value": f"{t['모달리티']} +{int(t['증가 건수']):,}건",
            "help": f"{int(t['직전 3개월']):,}건 → {int(t['최근 3개월']):,}건 ({t['증가율']}). {span}. {rule}"}


def _company_matrix(tagged: pd.DataFrame, companies: list) -> pd.DataFrame:
    nc = data.news_companies()
    m = tagged.merge(nc[nc.corp_name.isin(companies)], on="news_id")
    return (m.pivot_table(index="corp_name", columns="modality", values="news_id", aggfunc="nunique", fill_value=0)
            .reindex(index=companies, columns=data.MODALITIES, fill_value=0))


# ---------------------------------------------------------------- 차트

def _trend_chart(table: pd.DataFrame, key: str) -> None:
    """모달리티 7개 소형 다중 차트 (같은 y축). 범주 색이 5개뿐이라(2-2절) 한 그림에 7개 선을 겹치지 않고
    S1 키워드 차트와 같은 방식으로 나눈다."""
    t = theme.TOKENS[theme.current_mode()]
    mods = list(table.columns)
    rows = math.ceil(len(mods) / 4)
    fig = make_subplots(rows=rows, cols=4, shared_yaxes="all", shared_xaxes=True,
                        subplot_titles=[f"{m} ({int(table[m].sum()):,})" for m in mods], vertical_spacing=0.14)
    for i, m in enumerate(mods):
        fig.add_trace(go.Scatter(x=table.index, y=table[m], mode="lines", name=m,
                                 line=dict(width=2, color=t["series-volume"]),
                                 hovertemplate=f"{m}<br>%{{x|%Y-%m}} · %{{y:,}}건<extra></extra>"),
                      row=i // 4 + 1, col=i % 4 + 1)
    theme.style(fig, "bar", height=theme.HEIGHT["small"] * rows + 40)
    fig.update_layout(showlegend=False, hovermode="closest", margin=dict(l=8, r=8, t=28, b=8))
    fig.update_annotations(font=dict(size=12, color=t["text"]))
    fig.update_xaxes(tickformat="%Y-%m")
    theme.show(fig, key=key, alt="모달리티별 월 기사 수 (LLM 태그, 괄호는 기간 합계)")


def _seq_color(value: float, vmax: float, colors: list) -> str:
    if vmax <= 0:
        return colors[0]
    return colors[min(len(colors) - 1, int(value / vmax * (len(colors) - 1) + 0.5))]


def _heatmap(matrix: pd.DataFrame, share: bool, key: str) -> None:
    """2-2·2-6절 순차 10단계. 칸 글자색은 칸 색으로 정한다(2-3절). Plotly 7.1 은 칸마다 글자색을 줄 수 없어
    annotation 으로 쓴다(5-4절)."""
    mode = theme.current_mode()
    colors = SEQ[mode]
    counts = matrix.to_numpy()
    values = (matrix.div(matrix.sum(axis=1).replace(0, 1), axis=0) * 100).to_numpy() if share else counts
    vmax = float(values.max()) if values.size else 0.0
    scale = [[i / (len(colors) - 1), c] for i, c in enumerate(colors)]
    fig = go.Figure(go.Heatmap(
        z=values, x=list(matrix.columns), y=list(matrix.index), colorscale=scale, zmin=0, zmax=vmax or 1,
        showscale=False, xgap=2, ygap=2, customdata=counts,
        hovertemplate=("%{y} · %{x}<br>" + ("기업 기사 중 %{z:.1f}% (%{customdata:,}건)" if share else "%{z:,}건")
                       + "<extra></extra>")))
    for i, corp in enumerate(matrix.index):
        for j, mod in enumerate(matrix.columns):
            v = values[i][j]
            cell = _seq_color(v, vmax, colors)
            fig.add_annotation(x=mod, y=corp, showarrow=False, text=f"{v:.0f}%" if share else f"{int(v):,}",
                               font=dict(size=12, color="#FFFFFF" if cell in SEQ_DARK_TEXT else "#000000"))
    theme.style(fig, "heatmap", height=60 * len(matrix.index) + 60)
    fig.update_yaxes(autorange="reversed")   # IA 순서대로 위에서 아래로
    fig.update_xaxes(side="top")
    theme.show(fig, key=key, alt="기업 × 모달리티 기사 수 히트맵" + (" (기업별 비율)" if share else ""))


SEQ = {"light": ["#CDE2FB", "#9EC5F4", "#86B6EF", "#6DA7EC", "#5598E7", "#3987E5", "#2A78D6", "#256ABF", "#184F95",
                 "#0D366B"],
       "dark": ["#0D366B", "#184F95", "#256ABF", "#2A78D6", "#3987E5", "#5598E7", "#6DA7EC", "#86B6EF", "#9EC5F4",
                "#CDE2FB"]}   # .streamlit/config.toml chartSequentialColors 와 같은 값


# ---------------------------------------------------------------- 근거 기사·증설 공시

def _evidence(tagged: pd.DataFrame, matrix: pd.DataFrame) -> None:
    """칸의 근거 기사 (N6). 히트맵 클릭 대신 선택 상자로 고른다 — 칸마다 글자를 annotation 으로 얹어 클릭이 칸에 닿지 않는다."""
    with st.expander("칸의 근거 기사 보기"):
        c1, c2 = st.columns(2, gap="small")
        corp = c1.selectbox("기업", list(matrix.index), key="s3_corp")
        mod = c2.selectbox("모달리티", data.MODALITIES, key="s3_mod")
        nc = data.news_companies()
        ids = set(nc[nc.corp_name == corp].news_id)
        hit = (tagged[(tagged.modality == mod) & tagged.news_id.isin(ids)]
               .drop_duplicates("news_id").sort_values("date", ascending=False))
        st.caption(f"{corp} · {mod}: {len(hit):,}건 (최근 20건) {TAG_BADGE}")
        for r in hit.head(20).to_dict("records"):
            ui.news_line(r)
            if r["evidence"]:
                st.caption(f"근거 표현: {r['evidence']}")


def _expansion_table(filters: dict) -> pd.DataFrame:
    d = data.filter_disclosures(filters, {"증설"}).sort_values("rcept_date", ascending=False)
    return pd.DataFrame({"제출일": d.rcept_date, "기업": d.corp_name, "공시명": d.report_nm,
                         "정정": d.is_amended.map({1: "정정", 0: ""}), "DART": d.url})


# ---------------------------------------------------------------- 화면

def render():
    filters = st.session_state["filters"]
    ui.header("기술·생산", "어떤 모달리티·생산기술이 성장하는가?", filters,
              screen_scope="카테고리는 모달리티·생산능력만")
    kws = data.s3_keywords(filters)
    if not kws:
        st.info("이 화면은 CDMO 모달리티·CDMO 생산능력 기사만 다룹니다. 사이드바 카테고리에 이 중 하나 이상을 넣으세요.",
                icon=":material/filter_alt:")
        ui.empty("기사/공시", "S3-all")
        ui.limits(LIMITS_S3)
        return
    try:
        with st.spinner("데이터를 불러오는 중"):
            news = data.filter_s3_news(filters)
            tagged = _tagged(news)
            expansion = _expansion_table(filters)
    except FileNotFoundError as e:
        ui.data_error(e.args[0] if e.args else data.DB_PATH, e)
        ui.limits(LIMITS_S3)
        return
    except Exception as e:
        ui.data_error(data.MODALITY_PATH, e)
        ui.limits(LIMITS_S3)
        return

    growth = _growth(tagged, filters)
    ui.kpis([
        {"label": "모달리티 기사", "value": f"{tagged.news_id.nunique():,}건",
         "help": f"모달리티 태그(7종)가 1개 이상 붙은 기사 · 범위 {', '.join(k.removeprefix('CDMO ') for k in kws)} 기사 "
                 f"{len(news):,}건 중"},
        {"label": "증설 공시 (정정 제외)", "value": f"{int((expansion['정정'] == '').sum()):,}건",
         "help": "event_class = 증설, 정정 공시 제외"},
        _growth_kpi(growth),
    ])
    st.divider()

    fkey = abs(hash((str(filters["period"]), tuple(filters["companies"]), tuple(kws))))
    st.markdown(f"#### 모달리티별 언급 추이 {TAG_BADGE}")
    if tagged.empty:
        ui.empty("기사", "S3-C1")
    else:
        table = _monthly(tagged, filters)
        _trend_chart(table, key=f"s3_trend_{fkey}")
        out = table.copy()
        out.index = out.index.strftime("%Y-%m")
        ui.table_view(out.reset_index(), "월별 모달리티 기사 수 (한 기사에 태그가 여러 개면 각 모달리티에 셈)")
        if growth["table"] is not None:
            with st.expander("최근 3개월 증감 (최다 증가 모달리티의 근거)"):
                st.dataframe(growth["table"], hide_index=True, width="stretch", alt="모달리티별 최근 3개월과 직전 3개월 기사 수")
                st.caption(f"직전 {growth['prev'][0]:%Y-%m-%d}~{growth['prev'][1]:%Y-%m-%d} · "
                           f"최근 {growth['cur'][0]:%Y-%m-%d}~{growth['cur'][1]:%Y-%m-%d} · 증가 건수 순. "
                           "한 기사에 태그가 여러 개면 각 모달리티에 셉니다.")

    head, ctl = st.columns([3, 2], vertical_alignment="bottom")
    head.markdown(f"#### 기업 × 모달리티 {TAG_BADGE}")
    view = ctl.segmented_control("값", ["기사 수", "기업 내 비율"], key="s3_heat_value", default="기사 수",
                                 required=True)
    matrix = _company_matrix(tagged, filters["companies"])
    if matrix.to_numpy().sum() == 0:
        ui.empty("기사", "S3-C2")
    else:
        _heatmap(matrix, view == "기업 내 비율", key=f"s3_heat_{fkey}_{view}")
        st.caption("기업 내 비율: 그 기업 행의 합계 대비 비율. 삼성바이오로직스 기사가 많아 기사 수만 보면 다른 기업의 차이가 묻힙니다.")
        _evidence(tagged, matrix)

    st.markdown("#### 증설 공시")
    if expansion.empty:
        ui.empty("공시", "S3-C3")
    else:
        st.dataframe(expansion, hide_index=True, width="stretch", alt="증설 공시 목록",
                     column_config={"DART": st.column_config.LinkColumn("DART", display_text="DART")})
    ui.limits(LIMITS_S3)
