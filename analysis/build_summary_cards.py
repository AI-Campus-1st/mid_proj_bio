"""S0 요약 화면의 결론 문장과 기회·위험 카드를 만든다 (UI_SPECIFICATION 5-1절, 미결 Q5).

카드의 주제·문구는 사람이 정하고(2026-11-18 팀 확인), 근거 기사·기간·태그·건수는 데이터에서 뽑는다.
LLM을 호출하지 않는다. 데이터가 바뀌면 다시 실행해 숫자와 근거 링크를 갱신한다.

입력: data/processed/sentiment_llm.csv (감성 라벨), issues_llm.csv + issue_groups.csv (이슈 이름 묶음),
      data/db/bio_cdmo.sqlite (news, news_cdmo_keywords, news_companies, disclosures)
출력: data/processed/summary_cards.json
실행: python analysis/build_summary_cards.py
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
DB = ROOT / "data" / "db" / "bio_cdmo.sqlite"
OUT = PROCESSED / "summary_cards.json"
DART = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={}"
N_EVIDENCE = 3            # 카드마다 붙이는 대표 기사 수
BASIS = "AI 초안 · 팀 검토"  # 결론·카드 문구는 Claude 초안을 팀이 확인한 것

# 카드 정의: 주제(이슈 묶음 이름)와 라벨로 기사를 고르고, 근거 공시는 접수번호로 직접 지정한다.
# prefer 는 대표 기사를 고를 때 제목에 있으면 앞세우는 주제어 (정규식).
CARDS = [
    {"id": "O1", "prefer": "인수|폴리펩타이드", "type": "기회", "screen": "compare",
     "title": "삼성바이오, 2.7조 폴리펩타이드 인수로 펩타이드(비만약) CDMO 진출",
     "desc": "스위스 펩타이드 CDMO 인수를 결정하고 3조 원 유상증자로 자금을 마련했다.",
     "groups": ["삼성바이오 폴리펩타이드 인수", "삼성바이오로직스 유상증자"],
     "disclosures": ["20260720000001", "20260828000001"]},
    {"id": "O2", "prefer": "수주", "type": "기회", "screen": "compare",
     "title": "삼성바이오로직스, 대형 수주 지속 — 누적 수주 220억 달러 돌파",
     "desc": "2026년 9~10월 공급계약 공시가 이어지고 누적 수주액이 220억 달러를 넘었다.",
     "groups": ["삼성바이오로직스 수주"],
     "disclosures": ["20260910800388", "20261002800830"]},
    {"id": "O3", "prefer": "올리고|수주", "type": "기회", "screen": "compare",
     "title": "에스티팜, 올리고 수주 확대 — 913억 원 역대 최대 계약",
     "desc": "올리고 원료 공급계약이 잇따르고 제2올리고동을 앞세워 글로벌 수주에 나섰다.",
     "groups": ["에스티팜 수주"],
     "disclosures": ["20260918900224", "20260316901006", "20260123900243"]},
    {"id": "O4", "prefer": "특별법", "type": "기회", "screen": "policy",
     "title": "CDMO 특별법 하위법령 입법 예고, 2026년 12월 시행",
     "desc": "수출 CDMO 맞춤 규제 지원을 담은 특별법 하위규정이 예고됐다. 정책이라 공시는 없다.",
     "groups": ["CDMO 특별법", "식약처 CDMO 규제지원", "식약처 CDMO 특별법 하위규정"],
     "disclosures": []},
    {"id": "O5", "prefer": "공장|증설", "type": "기회", "screen": "tech",
     "title": "생산능력 증설 — 삼성 5·6공장, 바이넥스 오송, 롯데 송도",
     "desc": "국내 CDMO들이 공장 가동·착공·증설로 생산능력을 늘리고 있다.",
     "groups": ["롯데 송도 바이오의약품 공장 건설", "바이넥스 생산능력 증설", "삼성바이오로직스 6공장 건설",
                "삼성바이오로직스 5공장 가동"],
     "disclosures": ["20250922900023"]},
    {"id": "R1", "prefer": "관세", "type": "위험", "screen": "policy",
     "title": "미국 의약품 관세 발효",
     "desc": "최대 100% 관세 발표(2026-04) 후 발효. 한국산은 15%, ADC·CGT는 0%로 정해졌다.",
     "groups": ["미국 의약품 관세"], "disclosures": []},
    {"id": "R2", "prefer": "노조|파업|노사", "type": "위험", "screen": "trend",
     "title": "삼성바이오로직스 노사 갈등이 3조 유상증자·신공장 일정에 부담",
     "desc": "파업과 노조의 유상증자 보류 요구가 이어지며 증권가가 눈높이를 낮췄다.",
     "groups": ["삼성바이오로직스 노사 갈등", "삼성바이오로직스 유상증자"],
     "disclosures": ["20261001000449"]},
    {"id": "R3", "prefer": "제조정지|FDA|실사", "type": "위험", "screen": "policy",
     "title": "품질·규제 처분 — 바이넥스 제조정지, 노보 노디스크 FDA 제재",
     "desc": "시험 결과지 위반에 따른 제조정지 등 품질 문제가 수주 신뢰에 위험 요인이다.",
     "groups": ["바이넥스 제조정지", "삼성바이오로직스 FDA 실사", "노보 노디스크 생산시설 FDA 제재",
                "진원생명과학 CDMO 사업 영업정지 논란"],
     "disclosures": []},
]
CONCLUSION = ("{start} ~ {end} CDMO 뉴스는 기회가 위험보다 {ratio}배 많습니다(기회 {opp:,}건 · 위험 {risk:,}건). "
              "기회는 삼성바이오로직스의 폴리펩타이드 인수와 대형 수주, 에스티팜 올리고 수주, CDMO 특별법에 몰려 있고, "
              "위험은 미국 의약품 관세와 삼성바이오로직스 노사 갈등에 집중됩니다.")
# 이 출처의 기사는 제목만 있거나(구글 뉴스) 해외 기사라, 대표 기사로는 본문이 있는 국내 기사를 먼저 쓴다
ORIGIN_RANK = {"provided": 0, "team": 0, "google_company": 1, "google_cdmo": 1, "google_global": 2}


def load():
    issues = pd.read_csv(PROCESSED / "issues_llm.csv", dtype=str)
    groups = pd.read_csv(PROCESSED / "issue_groups.csv", dtype=str)
    sent = pd.read_csv(PROCESSED / "sentiment_llm.csv", dtype=str)
    con = sqlite3.connect(DB)
    try:
        news = pd.read_sql("SELECT news_id, url, published_date, published_at, title, press, origin "
                           "FROM news WHERE dup_of IS NULL", con)
        kw = pd.read_sql("SELECT news_id, keyword FROM news_cdmo_keywords WHERE is_primary = 1", con)
        corp = pd.read_sql("SELECT nc.news_id, c.corp_name FROM news_companies nc JOIN companies c USING (corp_code) "
                           "WHERE nc.match_field IN ('title', 'body')", con)
        disc = pd.read_sql("SELECT d.rcept_no, d.rcept_date, c.corp_name, d.report_nm FROM disclosures d "
                           "JOIN companies c USING (corp_code)", con)
    finally:
        con.close()
    m = (issues.merge(groups[["issue_norm", "issue_group"]], on="issue_norm", how="left")
         .merge(sent[["url", "label"]], on="url").merge(news, on="url"))
    m["issue_group"] = m.issue_group.fillna(m.issue)
    return m.drop_duplicates(["url", "issue_group"]), sent, kw, corp, disc


def build_card(card: dict, m: pd.DataFrame, kw: pd.DataFrame, corp: pd.DataFrame, disc: pd.DataFrame) -> dict:
    arts = m[m.issue_group.isin(card["groups"]) & (m.label == card["type"])].drop_duplicates("url")
    if arts.empty:
        raise SystemExit(f"{card['id']}: 근거 기사가 없다 — 이슈 묶음 이름을 확인한다")
    # 제목에 카드 주제어(prefer)가 있는 기사 → 본문 있는 국내 출처 → 최신 순
    on_topic = arts.title.str.contains(card["prefer"], regex=True).map({True: 0, False: 1})
    picks = (arts.assign(topic=on_topic, rank=arts.origin.map(ORIGIN_RANK).fillna(3))
             .sort_values(["topic", "rank", "published_date", "published_at"], ascending=[True, True, False, False])
             .drop_duplicates("press").head(N_EVIDENCE))
    evidence = [{"kind": "기사", "title": r.title, "press": r.press, "date": r.published_date, "url": r.url}
                for r in picks.sort_values("published_date", ascending=False).itertuples()]
    for rno in card["disclosures"]:
        d = disc[disc.rcept_no == rno]
        if d.empty:
            raise SystemExit(f"{card['id']}: 공시 {rno} 가 DB에 없다")
        d = d.iloc[0]
        evidence.append({"kind": "공시", "title": d.report_nm, "press": d.corp_name, "date": d.rcept_date,
                         "url": DART.format(rno)})
    companies = corp[corp.news_id.isin(arts.news_id)].corp_name.value_counts()
    keywords = kw[kw.news_id.isin(arts.news_id)].keyword.value_counts()
    return {
        "id": card["id"], "type": card["type"], "title": card["title"], "desc": card["desc"],
        "screen": card["screen"], "n_articles": int(len(arts)),
        "tags": {
            # 기사 10% 이상에 나온 기업·키워드만 태그로 둔다 (드물게 함께 언급된 기업 제외)
            "companies": [c for c, n in companies.items() if n >= max(2, 0.1 * len(arts))],
            "keywords": [k for k, n in keywords.items() if n >= max(2, 0.1 * len(arts))][:3],
            "start": arts.published_date.min(), "end": arts.published_date.max(),
        },
        "evidence": evidence,
    }


def main() -> None:
    m, sent, kw, corp, disc = load()
    news_dates = m.published_date
    counts = sent.label.value_counts()
    opp, risk = int(counts.get("기회", 0)), int(counts.get("위험", 0))
    cards = [build_card(c, m, kw, corp, disc) for c in CARDS]
    out = {
        "basis": BASIS,
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "conclusion": CONCLUSION.format(start=news_dates.min()[:7].replace("-", "년 ") + "월",
                                        end=news_dates.max()[:7].replace("-", "년 ") + "월",
                                        ratio=round(opp / risk) if risk else "—", opp=opp, risk=risk),
        "label_counts": {k: int(v) for k, v in counts.items()},
        "cards": cards,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장: {OUT} — 카드 {len(cards)}개")
    for c in cards:
        t = c["tags"]
        print(f"  {c['id']} {c['type']} 기사 {c['n_articles']} · 근거 {len(c['evidence'])} · "
              f"{t['start']}~{t['end']} · {', '.join(t['companies']) or '기업 없음'} · {', '.join(t['keywords'])}")


if __name__ == "__main__":
    main()
