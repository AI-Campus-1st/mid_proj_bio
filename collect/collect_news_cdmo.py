"""CDMO 키워드 뉴스 추가 수집 (구글 뉴스 RSS — 제목·매체·일자·링크).

- config.CDMO_QUERIES 의 검색어를 제공 뉴스 기간(DB_START~DB_END)에 30일 구간으로 검색한다.
- 한 번에 최대 100건이므로 100건에 닿으면 구간을 반으로 나눈다.
- 원본은 data/raw/news_cdmo/{키워드}.jsonl 에 그대로 쌓고, 구간별 완료 기록으로 이어받는다.
- 기존 자료와의 중복 제거와 재분류는 analysis/build_cdmo_news.py 에서 한다.
실행: python collect/collect_news_cdmo.py
"""
import json
from datetime import timedelta

from collect_news import LIMIT, fetch
from config import CDMO_KEYWORDS, CDMO_NEWS_DIR, CDMO_QUERIES, DB_END, DB_START

DONE = CDMO_NEWS_DIR / "_done.txt"
STEP = 30


def windows():
    s = DB_START
    while s <= DB_END:
        e = min(s + timedelta(days=STEP - 1), DB_END)
        yield s, e
        s = e + timedelta(days=1)


def main():
    CDMO_NEWS_DIR.mkdir(parents=True, exist_ok=True)
    done = set(DONE.read_text(encoding="utf-8").splitlines()) if DONE.exists() else set()
    for kw, queries in CDMO_QUERIES.items():
        path = CDMO_NEWS_DIR / (kw.replace(" ", "_").replace("·", "") + ".jsonl")
        for query in queries:
            stack = list(windows())[::-1]
            n = 0
            while stack:
                s, e = stack.pop()
                tag = f"{query}|{s}|{e}"
                if tag in done:
                    continue
                items = fetch(query, s, e)
                if len(items) >= LIMIT and s < e:
                    mid = s + (e - s) // 2
                    stack += [(mid + timedelta(days=1), e), (s, mid)]
                    continue
                with path.open("a", encoding="utf-8") as f:
                    for it in items:
                        f.write(json.dumps({"kind": "cdmo", "name": kw,
                                            "category": CDMO_KEYWORDS[kw], "query": query,
                                            "window_start": str(s), "window_end": str(e),
                                            "truncated": len(items) >= LIMIT, **it},
                                           ensure_ascii=False) + "\n")
                with DONE.open("a", encoding="utf-8") as f:
                    f.write(tag + "\n")
                done.add(tag)
                n += len(items)
            print(f"완료: [{kw}] {query} (+{n}건)", flush=True)


if __name__ == "__main__":
    main()
