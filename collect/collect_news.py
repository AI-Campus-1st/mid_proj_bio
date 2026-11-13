"""구글 뉴스 RSS 기반 뉴스 수집 (제목·매체·일자·링크).

- 키워드(가이드 2-3)와 후보 기업명을 기간 구간별로 검색한다.
- 한 번의 검색은 최대 100건이므로, 100건에 닿으면 구간을 반으로 나눠 다시 검색한다.
- 구간별 완료 기록을 남겨 재실행 시 이어서 수집한다.
실행: python collect/collect_news.py [keyword|company|all]
"""
import json
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from email.utils import parsedate_to_datetime

from config import COMPANIES, END, KEYWORDS, NEWS_ALIASES, RAW_DIR, START

OUT = RAW_DIR / "news"
DONE = OUT / "_done.txt"
DELAY = 1.0
LIMIT = 100


def fetch(query: str, start: date, end: date) -> list:
    """[start, end] 구간 검색. before는 해당 일을 포함하지 않으므로 하루를 더한다."""
    q = f"{query} after:{start - timedelta(days=1)} before:{end + timedelta(days=1)}"
    url = ("https://news.google.com/rss/search?q=" + urllib.parse.quote(q)
           + "&hl=ko&gl=KR&ceid=KR:ko")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                root = ET.fromstring(r.read())
            break
        except Exception as e:
            if attempt == 4:
                raise
            wait = 30 * (attempt + 1)
            print(f"  재시도({attempt + 1}) {wait}s: {type(e).__name__} {e}", file=sys.stderr)
            time.sleep(wait)
    time.sleep(DELAY)
    items = []
    for it in root.iter("item"):
        pub = it.findtext("pubDate")
        items.append({
            "title": it.findtext("title"),
            "source": it.findtext("source"),
            "pub_date": parsedate_to_datetime(pub).isoformat() if pub else None,
            "link": it.findtext("link"),
            "guid": it.findtext("guid"),
        })
    return items


def windows(step: int):
    s = START
    while s <= END:
        e = min(s + timedelta(days=step - 1), END)
        yield s, e
        s = e + timedelta(days=1)


def collect(query: str, meta: dict, step: int, done: set):
    path = OUT / f"{meta['kind']}_{meta['name'].replace(' ', '_').replace('&', 'n')}.jsonl"
    stack = list(windows(step))[::-1]
    n = 0
    while stack:
        s, e = stack.pop()
        tag = f"{query}|{s}|{e}"
        if tag in done:
            continue
        items = fetch(query, s, e)
        if len(items) >= LIMIT and s < e:  # 잘렸을 수 있으므로 구간을 나눈다
            mid = s + (e - s) // 2
            stack += [(mid + timedelta(days=1), e), (s, mid)]
            continue
        with path.open("a", encoding="utf-8") as f:
            for it in items:
                f.write(json.dumps({**meta, "query": query, "window_start": str(s),
                                    "window_end": str(e), "truncated": len(items) >= LIMIT,
                                    **it}, ensure_ascii=False) + "\n")
        with DONE.open("a", encoding="utf-8") as f:
            f.write(tag + "\n")
        done.add(tag)
        n += len(items)
    print(f"완료: {query} (+{n}건)", flush=True)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    OUT.mkdir(parents=True, exist_ok=True)
    done = set(DONE.read_text(encoding="utf-8").splitlines()) if DONE.exists() else set()

    if mode in ("keyword", "all"):
        for kw, cat in KEYWORDS.items():
            collect(kw, {"kind": "keyword", "name": kw, "category": cat}, 7, done)
    if mode in ("company", "all"):
        for name, field, status in COMPANIES:
            for alias in NEWS_ALIASES.get(name, [name]):
                collect(f'"{alias}"', {"kind": "company", "name": name, "category": field},
                        30, done)


if __name__ == "__main__":
    main()
