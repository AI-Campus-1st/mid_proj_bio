"""Day 3 EDA — 기사량·공시 건수 추이와 이슈 급증 시점.

통합 DB(data/db/bio_cdmo.sqlite)만 읽는다. 재실행하면 같은 결과가 나온다.
산출물
- data/processed/eda_*.csv   집계표 (월별 기사량, 기업별, 키워드별, 공시, 급증 시점과 근거)
- docs/figures/eda/*.png     차트
해석은 docs/eda_report.md 에 있다.
실행: python db/build_db.py → python analysis/eda.py
"""
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "collect"))
from config import DB_END, DB_PATH, DB_START, SELECTED  # noqa: E402

OUT = ROOT / "data" / "processed"
FIG = ROOT / "docs" / "figures" / "eda"
_fonts = {f.name for f in matplotlib.font_manager.fontManager.ttflist}   # 설치된 한글 글꼴 중 하나를 쓴다
plt.rcParams["font.family"] = next(
    (f for f in ("Malgun Gothic", "AppleGothic", "NanumGothic") if f in _fonts), "DejaVu Sans")
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["axes.spines.top"] = plt.rcParams["axes.spines.right"] = False

ORIGIN_KO = {"provided": "제공", "team": "팀원수집", "google_company": "기업명검색",
             "google_cdmo": "CDMO검색", "google_global": "해외검색"}
COMPANIES = list(SELECTED)

# 급증 판정 (주 단위). 직전 BASE_WEEKS 주의 중앙값과 비교한다.
BASE_WEEKS = 26     # 기준 구간 (약 6개월)
MIN_BASE = 12       # 기준 구간이 이보다 짧으면 판정하지 않는다
Z_MIN = 3.0         # (건수 - 중앙값) / 산포 가 이 값 이상
STOP = set("바이오 제약 기업 글로벌 국내 올해 시장 산업 대표 한국 위해 통해 관련 대한 이번 지난 최대 "
           "종합 단독 속보 the and for with from that its has are new".split())


def load():
    con = sqlite3.connect(DB_PATH)
    news = pd.read_sql(
        "SELECT n.news_id, n.origin, n.published_date AS d, n.press, n.url, n.dup_of, n.lang, "
        "n.cdmo_rel_basis AS rel, n.cdmo_kw_basis AS kwb, c.title_clean AS title "
        "FROM news n JOIN news_clean c USING (news_id)", con, parse_dates=["d"])
    kw = pd.read_sql("SELECT news_id, keyword, category, is_primary FROM news_cdmo_keywords", con)
    nc = pd.read_sql("SELECT nc.news_id, c.corp_name, nc.match_field FROM news_companies nc "
                     "JOIN companies c USING (corp_code)", con)
    disc = pd.read_sql("SELECT d.rcept_no, c.corp_name, d.rcept_date AS d, d.report_nm, d.pblntf_ty_nm, "
                       "d.is_amended, d.event_class, d.event_weight, d.url FROM disclosures d "
                       "JOIN companies c USING (corp_code)", con, parse_dates=["d"])
    built = con.execute("SELECT value FROM meta WHERE key = 'built_at'").fetchone()[0]
    con.close()
    news["ym"] = news.d.dt.to_period("M").astype(str)
    news["week"] = news.d.dt.to_period("W-SUN").dt.start_time      # 월요일 시작 주
    disc["ym"] = disc.d.dt.to_period("M").astype(str)
    disc["q"] = disc.d.dt.to_period("Q").astype(str)
    return news, kw, nc, disc, built


# ---------------------------------------------------------------- 급증 판정
def weekly(dates: pd.Series) -> pd.Series:
    """주별 건수. 기간 양 끝의 덜 찬 주는 뺀다."""
    idx = pd.date_range(pd.Timestamp(DB_START).to_period("W-SUN").start_time,
                        pd.Timestamp(DB_END).to_period("W-SUN").start_time, freq="W-MON")
    s = dates.dt.to_period("W-SUN").dt.start_time.value_counts().reindex(idx, fill_value=0).sort_index()
    return s.iloc[1:-1]


def detect(s: pd.Series, min_count: int) -> pd.DataFrame:
    """직전 26주 중앙값 대비 급증한 주. 산포는 MAD(×1.4826)이고, 건수가 적은 구간에서
    과민해지지 않도록 sqrt(중앙값)과 1 중 큰 값을 하한으로 둔다."""
    rows = []
    for i in range(MIN_BASE, len(s)):
        base = s.iloc[max(0, i - BASE_WEEKS):i]
        med = float(base.median())
        mad = float((base - med).abs().median()) * 1.4826
        scale = max(mad, np.sqrt(med), 1.0)
        z = (s.iloc[i] - med) / scale
        if z >= Z_MIN and s.iloc[i] >= min_count:
            rows.append({"week": s.index[i], "count": int(s.iloc[i]), "baseline": med, "z": round(z, 1)})
    df = pd.DataFrame(rows, columns=["week", "count", "baseline", "z"])
    if df.empty:
        return df.assign(episode=[])
    df["episode"] = (df.week.diff() != pd.Timedelta(weeks=1)).cumsum()   # 이어진 주는 한 사건으로 묶는다
    return df


def top_terms(titles, exclude=()) -> str:
    cnt = Counter()
    for t in titles:
        toks = {w.lower() for w in re.findall(r"[가-힣]{2,}|[A-Za-z][A-Za-z&\-]{2,}", t)}
        cnt.update(w for w in toks if w not in STOP and not any(e in w for e in exclude))
    top = sorted(cnt.items(), key=lambda x: (-x[1], x[0]))[:8]      # 동률은 가나다순 (재실행해도 같은 결과)
    return ", ".join(f"{w}({c})" for w, c in top)


def describe(spikes: pd.DataFrame, items: pd.DataFrame, series: str, scope: str,
             disc: pd.DataFrame | None = None, exclude=()) -> list:
    """급증 사건마다 정점 주·정점 일, 대표 기사, 제목 빈출어, 같은 시기 공시를 붙인다."""
    out = []
    for _, ep in spikes.groupby("episode"):
        peak = ep.loc[ep["z"].idxmax()]
        in_ep = items[items.week.isin(ep.week)]
        day_cnt = in_ep.groupby("d").size()
        peak_day = day_cnt.idxmax()
        day_items = in_ep[in_ep.d == peak_day]
        # 대표 기사: 정점 일의 기사 중 매체가 겹치지 않게 3건 (제목에 근거가 있는 기사 먼저)
        day_items = day_items.sort_values(["rank", "news_id"]).drop_duplicates("press")
        ev = " / ".join(f"{r.title} ({r.press}) {r.url}" for r in day_items.head(3).itertuples())
        row = {"series": series, "scope": scope,
               "start_week": ep.week.min().date(), "end_week": (ep.week.max() + pd.Timedelta(days=6)).date(),
               "weeks": len(ep), "peak_week": peak.week.date(), "peak_count": int(peak["count"]),
               "baseline": peak.baseline, "z": peak.z, "total_in_episode": len(in_ep),
               "peak_day": peak_day.date(), "peak_day_count": int(day_cnt.max()),
               "top_terms": top_terms(in_ep.title, exclude), "evidence_articles": ev, "disclosures": ""}
        if disc is not None:
            lo, hi = ep.week.min() - pd.Timedelta(days=7), ep.week.max() + pd.Timedelta(days=13)
            dd = disc[(disc.corp_name == scope) & disc.d.between(lo, hi) & (disc.event_weight > 0)]
            dd = dd.sort_values(["event_weight", "d"], ascending=[False, True]).head(4)
            row["disclosures"] = " / ".join(
                f"{r.d.date()} [{r.event_class}] {r.report_nm} {r.url}" for r in dd.itertuples())
        out.append(row)
    return out


# ---------------------------------------------------------------- 차트
def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIG / name, dpi=130)
    plt.close(fig)


def month_axis(ax, idx):
    ticks = [i for i, m in enumerate(idx) if m.endswith(("-01", "-07"))]
    ax.set_xticks(ticks, [idx[i] for i in ticks])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    news, kw, nc, disc, built = load()
    months = [str(p) for p in pd.period_range(DB_START, DB_END, freq="M")]
    uniq = news[news.dup_of.isna()]
    print(f"DB 빌드: {built} / 뉴스 {len(news)}건 (중복 제외 {len(uniq)}건) / 공시 {len(disc)}건")

    # 1) 월별 기사량 × 수집출처 (중복 제외)
    m_origin = (uniq.assign(origin=uniq.origin.map(ORIGIN_KO)).pivot_table(
        index="ym", columns="origin", values="news_id", aggfunc="count", fill_value=0)
        .reindex(months, fill_value=0)[list(ORIGIN_KO.values())])
    m_origin["전체"] = m_origin.sum(axis=1)
    m_origin["팀원수집 제외"] = m_origin["전체"] - m_origin["팀원수집"]
    m_origin.to_csv(OUT / "eda_news_monthly.csv", encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(11, 4.2))
    bottom = np.zeros(len(months))
    for col in ORIGIN_KO.values():
        ax.bar(range(len(months)), m_origin[col], bottom=bottom, label=col, width=0.85)
        bottom += m_origin[col].to_numpy()
    month_axis(ax, months)
    ax.set_title("월별 기사량 — 수집출처별 (중복 제외)")
    ax.set_ylabel("기사 수")
    ax.legend(ncol=5, frameon=False, loc="upper left")
    save(fig, "01_news_monthly_by_origin.png")

    # 2) 분석 범위 판단: 출처별 CDMO 관련 비중 (가이드 2-3 "무관한 기사 비중 확인")
    rel = uniq.assign(
        origin=uniq.origin.map(ORIGIN_KO),
        grp=np.select([uniq.rel == "none", (uniq.rel == "query") & (uniq.kwb == "query"),
                       uniq.kwb == "none", uniq.kwb == "query"],
                      ["CDMO 무관", "검색어만 근거(제외 권장)", "CDMO 관련·6개 이슈 밖", "키워드만 검색어 근거"],
                      default="제목·본문 근거"))
    scope = pd.crosstab(rel.origin, rel.grp, margins=True, margins_name="전체")
    scope = scope.reindex(list(ORIGIN_KO.values()) + ["전체"])[
        ["제목·본문 근거", "키워드만 검색어 근거", "CDMO 관련·6개 이슈 밖", "검색어만 근거(제외 권장)", "CDMO 무관", "전체"]]
    scope.to_csv(OUT / "eda_news_scope.csv", encoding="utf-8-sig")

    # 3) CDMO 키워드별 월별 기사량 (대표 키워드, 검색어 근거 제외, 중복 제외)
    k = kw[kw.is_primary == 1].merge(uniq, on="news_id")
    k = k[k.kwb != "query"]
    m_kw = k.pivot_table(index="ym", columns="keyword", values="news_id", aggfunc="count",
                         fill_value=0).reindex(months, fill_value=0)
    m_kw_ex = k[k.origin != "team"].pivot_table(index="ym", columns="keyword", values="news_id",
                                                aggfunc="count", fill_value=0).reindex(months, fill_value=0)
    m_kw.join(m_kw_ex.add_suffix(" (팀원수집 제외)")).to_csv(OUT / "eda_keyword_monthly.csv",
                                                       encoding="utf-8-sig")
    fig, axes = plt.subplots(2, 3, figsize=(13, 6), sharex=True)
    for ax, col in zip(axes.ravel(), m_kw.columns):
        ax.bar(range(len(months)), m_kw[col], color="#c9d3e0", width=0.85, label="전체")
        ax.plot(range(len(months)), m_kw_ex[col], color="#1f4e79", lw=1.6, label="팀원수집 제외")
        ax.set_title(col, fontsize=11)
        month_axis(ax, months)
        ax.tick_params(axis="x", labelsize=8, rotation=45)
    axes[0, 0].legend(frameon=False, fontsize=9)
    fig.suptitle("CDMO 키워드별 월별 기사량 (대표 키워드, 검색어 근거·중복 제외)")
    save(fig, "02_keyword_monthly.png")

    # 4) 기업별 월별 기사량 (제목·본문에 기업명, 중복 제외) + 공시
    cn = nc[nc.match_field != "query"].merge(uniq, on="news_id")
    cn["rank"] = (cn.match_field != "title").astype(int)
    m_corp_all = cn.pivot_table(index="ym", columns="corp_name", values="news_id", aggfunc="count",
                                fill_value=0).reindex(months, fill_value=0)[COMPANIES]
    m_corp = cn[cn.origin != "team"].pivot_table(      # 차트·급증 판정은 팀원수집 제외 기준
        index="ym", columns="corp_name", values="news_id", aggfunc="count",
        fill_value=0).reindex(months, fill_value=0)[COMPANIES]
    m_disc = disc.pivot_table(index="ym", columns="corp_name", values="rcept_no", aggfunc="count",
                              fill_value=0).reindex(months, fill_value=0)[COMPANIES]
    m_corp.add_prefix("뉴스_").join(m_corp_all.add_prefix("뉴스(팀원수집 포함)_")).join(m_disc.add_prefix("공시_")).to_csv(
        OUT / "eda_company_monthly.csv", encoding="utf-8-sig")
    fig, axes = plt.subplots(len(COMPANIES), 1, figsize=(11, 10), sharex=True)
    for ax, name in zip(axes, COMPANIES):
        ax.bar(range(len(months)), m_corp[name], color="#1f4e79", width=0.85)
        ax2 = ax.twinx()
        ax2.plot(range(len(months)), m_disc[name], color="#d9822b", lw=1.4, marker="o", ms=2.5)
        ax2.spines["right"].set_visible(True)
        ax2.set_ylim(0, max(m_disc[name].max() * 1.15, 5))
        ax.set_title(f"{name} — 뉴스(막대, 좌, 팀원수집 제외) · 공시(선, 우)", fontsize=10, loc="left")
        month_axis(ax, months)
    save(fig, "03_company_news_disclosure_monthly.png")

    # 5) 공시: 분기 × 기업, 분기 × 유형
    q_corp = pd.crosstab(disc.q, disc.corp_name)[COMPANIES]
    q_corp["전체"] = q_corp.sum(axis=1)
    q_corp.to_csv(OUT / "eda_disclosure_quarterly.csv", encoding="utf-8-sig")
    ev = pd.crosstab(disc.event_class, disc.corp_name, margins=True, margins_name="전체")
    ev["정정 공시"] = disc[disc.is_amended == 1].groupby("event_class").size().reindex(ev.index).fillna(0).astype(int)
    ev.loc["전체", "정정 공시"] = int(disc.is_amended.sum())
    ev.sort_values("전체", ascending=False).to_csv(OUT / "eda_disclosure_class.csv", encoding="utf-8-sig")
    core = disc[(disc.event_weight >= 3) & (disc.is_amended == 0)]
    q_core = pd.crosstab(core.q, core.event_class).reindex(q_corp.index, fill_value=0)
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.2))
    q_corp[COMPANIES].plot.bar(stacked=True, ax=axes[0], width=0.85)
    axes[0].set_title("분기별 공시 건수 — 기업별")
    q_core.plot.bar(stacked=True, ax=axes[1], width=0.85, colormap="tab10")
    axes[1].set_title("분기별 핵심 공시 (가중치 3 이상, 정정 제외) — 유형별")
    for ax in axes:
        ax.set_xlabel("")
        ax.legend(frameon=False, fontsize=8)
        ax.tick_params(axis="x", rotation=45)
    save(fig, "04_disclosure_quarterly.png")

    # 6) 급증 시점
    spikes = []
    # 6-1) 산업 전체: CDMO 관련 기사 (검색어만 근거인 기사 제외). 팀원수집은 2026년에 몰려 있어 뺀다
    ind = uniq[(uniq.rel != "none") & ~((uniq.rel == "query") & (uniq.kwb == "query")) & (uniq.origin != "team")]
    ind = ind.assign(rank=(ind.rel != "title").astype(int))
    s_ind = weekly(ind.d)
    sp_ind = detect(s_ind, min_count=20)
    spikes += describe(sp_ind, ind, "산업 전체", "CDMO 관련 기사")
    # 6-2) 키워드별
    kk = k[k.origin != "team"].assign(rank=(k.kwb != "title").astype(int))
    for name, g in kk.groupby("keyword"):
        spikes += describe(detect(weekly(g.d), min_count=8), g, "키워드", name)
    # 6-3) 기업별 (공시와 대조). 기업명이 제목·본문에 있는 기사, 팀원수집 제외
    cc = cn[cn.origin != "team"]
    corp_series = {}
    for name in COMPANIES:
        g = cc[cc.corp_name == name]
        corp_series[name] = (weekly(g.d), detect(weekly(g.d), min_count=6))
        spikes += describe(corp_series[name][1], g, "기업", name, disc, exclude=(name,))
    sp = pd.DataFrame(spikes)
    sp.to_csv(OUT / "eda_spikes.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame({"산업 전체(팀원수집 제외)": s_ind,
                  **{n: s for n, (s, _) in corp_series.items()}}).rename_axis("week").to_csv(
        OUT / "eda_weekly.csv", encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(12, 4.2))
    ax.plot(s_ind.index, s_ind.values, color="#1f4e79", lw=1.2)
    ax.plot(s_ind.index, s_ind.rolling(BASE_WEEKS, min_periods=MIN_BASE).median().shift(1),
            color="#888", lw=1, ls="--", label=f"직전 {BASE_WEEKS}주 중앙값")
    ax.scatter(sp_ind.week, sp_ind["count"], color="#c0392b", zorder=3, label=f"급증 주 (z ≥ {Z_MIN:g})")
    for _, ep in sp_ind.groupby("episode"):
        p = ep.loc[ep["count"].idxmax()]
        ax.annotate(p.week.strftime("%y-%m-%d"), (p.week, p["count"]), textcoords="offset points",
                    xytext=(0, 6), ha="center", fontsize=8)
    ax.set_title("주별 CDMO 관련 기사량과 급증 시점 (팀원수집·검색어만 근거 기사 제외, 중복 제외)")
    ax.legend(frameon=False)
    save(fig, "05_weekly_spikes_industry.png")

    fig, axes = plt.subplots(len(COMPANIES), 1, figsize=(12, 11), sharex=True)
    for ax, name in zip(axes, COMPANIES):
        s, d = corp_series[name]
        ax.plot(s.index, s.values, color="#1f4e79", lw=1.1)
        ax.scatter(d.week, d["count"], color="#c0392b", zorder=3, s=22)
        dd = disc[(disc.corp_name == name) & (disc.event_weight >= 3) & (disc.is_amended == 0)]
        ax.vlines(dd.d, 0, s.max() * 0.12 + 0.5, color="#d9822b", lw=0.9)
        ax.set_title(f"{name} — 주별 기사량 · 급증 주(빨강) · 핵심 공시일(주황 눈금)", fontsize=10, loc="left")
    save(fig, "06_weekly_spikes_company.png")

    # 요약 출력
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 30)
    pd.set_option("display.max_colwidth", 70)
    yearly = m_origin.groupby(m_origin.index.str[:4]).sum()
    print("\n[연도별 기사량 × 출처]\n", yearly)
    print("\n[분석 범위]\n", scope)
    print("\n[급증 사건 수]\n", sp.groupby("series").size())
    print("\n[급증 시점]\n", sp[["series", "scope", "start_week", "end_week", "peak_count", "baseline", "z",
                              "peak_day", "peak_day_count"]].to_string(index=False))


if __name__ == "__main__":
    main()
