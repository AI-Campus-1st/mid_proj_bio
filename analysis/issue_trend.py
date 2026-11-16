"""기업별 기사량·공시 건수 추이와 이슈 급증 시점 분석.

통합 DB(data/db/bio_cdmo.sqlite)를 읽어 다음을 만든다. API는 호출하지 않는다.
  1) 기업 × 주별 기사량·공시 건수        → weekly_counts.csv, weekly_trend.png
  2) 기업 × 일별 기사량·공시 건수        → daily_counts.csv
  3) 기업별 이슈 급증 구간(일 단위)       → spikes.csv, spikes.png
     급증 구간마다 대표 기사 제목과 앞뒤 공시를 붙인다.

기사 기준
  - 중복 기사(dup_of 있음)는 뺀다.
  - 기업 연결(news_companies)은 title·body·query 를 모두 쓴다 (v_company_daily 와 같은 기준).
  - 팀원 수집분(origin='team')은 2026년 4월 이후에 몰려 있어 추이를 부풀린다.
    그래서 기본값은 제외하고, EXCLUDE_ORIGINS 를 비우면 포함한다.

급증(spike) 판정 — 기업별 일 기사량 x 에 대해
  기준선 = 직전 28일(당일 제외)의 평균 m, 표준편차 s (s 는 최소 1로 둔다)
  x >= MIN_COUNT 이고 x >= m + Z * s 이면 급증일.
  급증일이 GAP_DAYS 이내로 이어지면 하나의 급증 구간으로 묶는다.

실행: python analysis/issue_trend.py
결과: data/processed/issue_trend/
"""
import os
import sqlite3
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib import font_manager  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "collect"))
from config import DB_END, DB_PATH, DB_START  # noqa: E402

OUT = Path(os.environ.get("ISSUE_TREND_OUT", ROOT / "data" / "processed" / "issue_trend"))

# ---------------------------------------------------------------- 설정
EXCLUDE_ORIGINS = ["team"]   # 추이 왜곡을 막기 위해 뺄 수집 출처. 빈 리스트면 전부 포함
WINDOW = 28                  # 기준선 기간(일)
Z = 3.0                      # 기준선 대비 몇 표준편차 이상이면 급증인지
MIN_COUNT = 5                # 급증으로 볼 최소 일 기사량
GAP_DAYS = 2                 # 이 일수 이내로 이어진 급증일은 한 구간으로 묶는다
DISC_WINDOW = 3              # 급증 구간 앞뒤 며칠의 공시를 붙일지
TOP_TITLES = 3               # 급증 구간마다 붙일 대표 기사 제목 수


def set_korean_font():
    # 윈도우 맑은고딕, 맥 애플고딕, 리눅스 노토/나눔 순으로 찾는다
    for f in font_manager.findSystemFonts():
        low = f.lower()
        if any(k in low for k in ("malgun", "applegothic", "notosanscjk", "nanumgothic")):
            try:
                font_manager.fontManager.addfont(f)
            except Exception:
                pass
    have = {f.name for f in font_manager.fontManager.ttflist}
    for name in ("Malgun Gothic", "AppleGothic", "NanumGothic", "Noto Sans CJK KR", "Noto Sans CJK JP"):
        if name in have:
            plt.rcParams["font.family"] = name
            break
    plt.rcParams["axes.unicode_minus"] = False


# ---------------------------------------------------------------- 집계
def load(con):
    companies = pd.read_sql("SELECT corp_code, corp_name FROM companies ORDER BY corp_name", con)
    excl = ",".join(f"'{o}'" for o in EXCLUDE_ORIGINS) or "''"
    news = pd.read_sql(f"""
        SELECT nc.corp_code, n.news_id, n.published_date AS date, n.title, n.press,
               n.url, n.origin, nc.match_field
        FROM news n JOIN news_companies nc ON nc.news_id = n.news_id
        WHERE n.dup_of IS NULL AND n.origin NOT IN ({excl})""", con)
    disc = pd.read_sql("""
        SELECT corp_code, rcept_date AS date, report_nm, event_class, event_weight,
               is_amended, url
        FROM disclosures""", con)
    return companies, news, disc


def daily_table(companies, news, disc):
    days = pd.date_range(DB_START, DB_END, freq="D")
    rows = []
    for c in companies.itertuples():
        n = news[news.corp_code == c.corp_code].groupby("date").size()
        d = disc[disc.corp_code == c.corp_code].groupby("date").size()
        df = pd.DataFrame({"date": days})
        key = df["date"].dt.strftime("%Y-%m-%d")
        df["corp_name"] = c.corp_name
        df["news_cnt"] = key.map(n).fillna(0).astype(int)
        df["disclosure_cnt"] = key.map(d).fillna(0).astype(int)
        rows.append(df)
    return pd.concat(rows, ignore_index=True)


def weekly_table(daily):
    w = (daily.set_index("date").groupby("corp_name")[["news_cnt", "disclosure_cnt"]]
         .resample("W-MON", label="left", closed="left").sum().reset_index()
         .rename(columns={"date": "week_start"}))
    return w


def find_spikes(daily, news, disc):
    out = []
    for name, g in daily.groupby("corp_name"):
        g = g.sort_values("date").reset_index(drop=True)
        base = g["news_cnt"].shift(1).rolling(WINDOW, min_periods=WINDOW)
        g["base_mean"] = base.mean()
        g["base_std"] = base.std().clip(lower=1)
        g["z"] = (g["news_cnt"] - g["base_mean"]) / g["base_std"]
        hit = g[(g["news_cnt"] >= MIN_COUNT) & (g["z"] >= Z)]
        if hit.empty:
            continue
        # 가까운 급증일 묶기
        grp = (hit["date"].diff().dt.days.fillna(GAP_DAYS + 1) > GAP_DAYS).cumsum()
        for _, h in hit.groupby(grp):
            peak = h.loc[h["news_cnt"].idxmax()]
            start, end = h["date"].min(), h["date"].max()
            code = _CODES[name]
            corp = news[news.corp_code == code]
            span = corp[(corp.date >= start.strftime("%Y-%m-%d")) & (corp.date <= end.strftime("%Y-%m-%d"))]
            # 제목에 기업명이 있는 기사를 앞에 둔다
            span = span.sort_values(["match_field", "date"], key=lambda s: s.map(
                {"title": 0, "body": 1, "query": 2}) if s.name == "match_field" else s)
            titles = " | ".join(span["title"].drop_duplicates().head(TOP_TITLES))
            lo = (start - pd.Timedelta(days=DISC_WINDOW)).strftime("%Y-%m-%d")
            hi = (end + pd.Timedelta(days=DISC_WINDOW)).strftime("%Y-%m-%d")
            dd = disc[(disc.corp_code == code) & (disc.date >= lo) & (disc.date <= hi)]
            dd = dd.sort_values(["event_weight", "date"], ascending=[False, True])
            out.append({
                "corp_name": name,
                "start": start.date(), "end": end.date(), "peak_date": peak["date"].date(),
                "peak_news": int(peak["news_cnt"]),
                "baseline_mean": round(float(peak["base_mean"]), 2),
                "z": round(float(peak["z"]), 1),
                "span_news": int(h["news_cnt"].sum()),
                "disclosures_near": len(dd),
                "top_disclosure": dd.iloc[0]["report_nm"] if len(dd) else "",
                "top_disclosure_class": dd.iloc[0]["event_class"] if len(dd) else "",
                "sample_titles": titles,
            })
    return pd.DataFrame(out).sort_values(["corp_name", "start"]) if out else pd.DataFrame()


_CODES = {}   # 기업명 → corp_code (main 에서 채운다)


# ---------------------------------------------------------------- 그림
def plot_weekly(weekly, spikes, path):
    names = sorted(weekly.corp_name.unique())
    fig, axes = plt.subplots(len(names), 1, figsize=(13, 2.6 * len(names)), sharex=True)
    for ax, name in zip(axes, names):
        w = weekly[weekly.corp_name == name]
        ax.plot(w.week_start, w.news_cnt, color="#2f6db5", lw=1.4, label="기사량(주)")
        ax.set_ylabel("기사", color="#2f6db5")
        ax2 = ax.twinx()
        ax2.bar(w.week_start, w.disclosure_cnt, width=5, color="#e08a2e", alpha=0.45, label="공시(주)")
        ax2.set_ylabel("공시", color="#e08a2e")
        if not spikes.empty:
            for s in spikes[spikes.corp_name == name].itertuples():
                ax.axvline(pd.Timestamp(s.peak_date), color="#c0392b", lw=0.8, ls="--", alpha=0.7)
        ax.set_title(name, loc="left", fontsize=11, fontweight="bold")
        ax.grid(axis="y", alpha=0.3)
    axes[0].legend(handles=[axes[0].lines[0],
                            plt.Rectangle((0, 0), 1, 1, color="#e08a2e", alpha=0.45),
                            plt.Line2D([], [], color="#c0392b", ls="--")],
                   labels=["기사량(주)", "공시 건수(주)", "이슈 급증일"], loc="upper left", fontsize=9)
    fig.suptitle(f"CDMO 5개사 주별 기사량·공시 건수 ({DB_START} ~ {DB_END})", fontsize=13)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_spikes(daily, spikes, path):
    names = sorted(daily.corp_name.unique())
    fig, axes = plt.subplots(len(names), 1, figsize=(13, 2.4 * len(names)), sharex=True)
    for ax, name in zip(axes, names):
        g = daily[daily.corp_name == name]
        ax.bar(g.date, g.news_cnt, width=1, color="#9fb7d6")
        if not spikes.empty:
            s = spikes[spikes.corp_name == name]
            ax.scatter(pd.to_datetime(s.peak_date), s.peak_news, color="#c0392b", s=18, zorder=3)
            for r in s.nlargest(3, "peak_news").itertuples():
                ax.annotate(str(r.peak_date), (pd.Timestamp(r.peak_date), r.peak_news),
                            xytext=(4, 2), textcoords="offset points", fontsize=8, color="#c0392b")
        ax.set_title(name, loc="left", fontsize=11, fontweight="bold")
        ax.set_ylabel("일 기사")
        ax.grid(axis="y", alpha=0.3)
    fig.suptitle("일별 기사량과 이슈 급증일(빨간 점, 상위 3개 날짜 표기)", fontsize=13)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------- main
def main():
    if not DB_PATH.exists():
        raise SystemExit("DB가 없습니다. 먼저 python db/build_db.py 를 실행하세요.")
    set_korean_font()
    OUT.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    companies, news, disc = load(con)
    con.close()
    _CODES.update(dict(zip(companies.corp_name, companies.corp_code)))

    daily = daily_table(companies, news, disc)
    weekly = weekly_table(daily)
    spikes = find_spikes(daily, news, disc)

    daily.assign(date=daily.date.dt.strftime("%Y-%m-%d")).to_csv(
        OUT / "daily_counts.csv", index=False, encoding="utf-8-sig")
    weekly.assign(week_start=weekly.week_start.dt.strftime("%Y-%m-%d")).to_csv(
        OUT / "weekly_counts.csv", index=False, encoding="utf-8-sig")
    spikes.to_csv(OUT / "spikes.csv", index=False, encoding="utf-8-sig")
    plot_weekly(weekly, spikes, OUT / "weekly_trend.png")
    plot_spikes(daily, spikes, OUT / "spikes.png")

    excl = ", ".join(EXCLUDE_ORIGINS) or "없음"
    print(f"결과: {OUT}  (제외한 수집 출처: {excl})")
    summary = daily.groupby("corp_name")[["news_cnt", "disclosure_cnt"]].sum()
    summary["spikes"] = spikes.groupby("corp_name").size() if not spikes.empty else 0
    print(summary.fillna(0).astype(int).to_string())


if __name__ == "__main__":
    main()
