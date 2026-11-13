"""분석 대상 5개사의 기업명 뉴스(구글 뉴스 RSS)를 제공 뉴스 기간에 맞춰 보충 수집.

collect_news.py 는 START~END(2023-11-13~2026-11-12)를 수집했다. 제공 뉴스 기간
(DB_START~DB_END) 가운데 그보다 앞선 구간만 추가로 받아 같은 파일에 이어 쓴다.
DB_END 이후 기사는 db/build_db.py 가 적재할 때 걸러낸다.
실행: python collect/collect_news_selected.py
"""
import json
from datetime import timedelta

from collect_news import DONE, LIMIT, OUT, fetch
from config import DB_START, SELECTED, START


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    done = set(DONE.read_text(encoding="utf-8").splitlines()) if DONE.exists() else set()
    for name in SELECTED:
        query = f'"{name}"'
        path = OUT / f"company_{name}.jsonl"
        stack = [(DB_START, START - timedelta(days=1))]
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
                    f.write(json.dumps({"kind": "company", "name": name, "category": "CDMO",
                                        "query": query, "window_start": str(s),
                                        "window_end": str(e), "truncated": len(items) >= LIMIT,
                                        **it}, ensure_ascii=False) + "\n")
            with DONE.open("a", encoding="utf-8") as f:
                f.write(tag + "\n")
            done.add(tag)
            n += len(items)
        print(f"완료: {query} {DB_START}~{START - timedelta(days=1)} (+{n}건)", flush=True)


if __name__ == "__main__":
    main()
