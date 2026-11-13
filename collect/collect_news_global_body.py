"""해외(영어) 뉴스 본문 수집 — 제목만 있는 구글 뉴스 기사의 원문 URL과 본문을 채운다.

collect_news_global.py 가 받은 data/raw/news_global/*_en.jsonl 은 구글 뉴스 리다이렉트 링크
(news.google.com/rss/articles/CBM...)와 제목만 있다. 이 스크립트는
  1) 구글 뉴스 링크를 실제 기사 URL로 바꾸고 (구글 batchexecute 디코딩)
  2) 기사 페이지에서 본문을 추출해 (JSON-LD articleBody → <article> 문단 → 전체 문단 순)
  3) data/raw/news_global/_bodies.jsonl 에 guid 단위로 쌓는다.
이미 처리한 guid 는 건너뛰므로 중단 후 다시 실행하면 이어서 수집한다.
실패 건(유료 구독벽, 차단 등)은 status 로 남기고, --retry 로 다시 시도할 수 있다.
수집한 본문은 analysis/build_cdmo_news.py 가 통합본에 합친다.

실행: python collect/collect_news_global_body.py [--limit N] [--retry]
"""
import argparse
import base64
import json
import re
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from config import GLOBAL_NEWS_DIR

OUT = GLOBAL_NEWS_DIR / "_bodies.jsonl"  # *_en.jsonl 과 이름이 겹치지 않게 한다 (원본 읽기 glob 제외)
DELAY = 1.5        # 요청 사이 대기(초)
TIMEOUT = 30
MIN_BODY = 300     # 이보다 짧으면 본문 추출 실패로 본다 (구독벽·요약 페이지)
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
}
BATCH_URL = "https://news.google.com/_/DotsSplashUi/data/batchexecute"


# ---------------------------------------------------------------------------
# 1) 구글 뉴스 링크 → 원문 URL
# ---------------------------------------------------------------------------
def article_id(link: str) -> str:
    return urlparse(link).path.rstrip("/").split("/")[-1]


def decode_offline(aid: str) -> str | None:
    """예전 형식(CBMi…)은 base64 안에 URL이 그대로 들어 있다."""
    try:
        raw = base64.urlsafe_b64decode(aid + "=" * (-len(aid) % 4))
    except Exception:
        return None
    m = re.search(rb"https?://[\x21-\x7e]+", raw)
    if not m or raw[m.start():].startswith(b"AU_yqL"):
        return None
    url = m.group().decode("ascii", "ignore")
    return url if "AU_yqL" not in url else None


def decode_online(session: requests.Session, aid: str) -> str:
    """새 형식(AU_yqL…)은 기사 페이지의 서명·타임스탬프로 batchexecute 를 호출해야 한다."""
    r = session.get(f"https://news.google.com/rss/articles/{aid}", timeout=TIMEOUT)
    r.raise_for_status()
    div = BeautifulSoup(r.text, "lxml").select_one("c-wiz > div[jscontroller]")
    if div is None or not div.get("data-n-a-sg"):
        raise ValueError("구글 뉴스 서명 없음")
    req = ["garturlreq", [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None,
                           None, None, None, 0, 1], "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0,
                          None, 0],
           aid, int(div["data-n-a-ts"]), div["data-n-a-sg"]]
    payload = {"f.req": json.dumps([[["Fbv4je", json.dumps(req), None, "generic"]]])}
    r = session.post(BATCH_URL, data=payload, timeout=TIMEOUT,
                     headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"})
    r.raise_for_status()
    body = json.loads(r.text.split("\n\n", 1)[1])
    return json.loads(body[0][2])[1]


def resolve(session: requests.Session, link: str) -> str:
    if "news.google.com" not in link:
        return link
    aid = article_id(link)
    return decode_offline(aid) or decode_online(session, aid)


# ---------------------------------------------------------------------------
# 2) 기사 페이지 → 본문
# ---------------------------------------------------------------------------
# 화면에 보이지 않는 태그만 지운다. nav·header·footer 등은 지우지 않는다: HTML 이 깨진 사이트
# (예: Contract Pharma)는 파서가 본문까지 메뉴 태그 안에 넣어 버려 본문이 함께 지워진다.
# 메뉴·사이드바는 "긴 문단(LONG_P 이상)이 많은 블록" 규칙으로 걸러낸다 (메뉴 설명은 짧다).
NOISE = ("script", "style", "noscript", "iframe", "svg")
LONG_P = 150
BOILER = re.compile(r"(?i)^(subscribe|sign up|advertisement|related|read more|copyright|©|"
                    r"click here|share this|follow us|this article)")


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def from_jsonld(soup: BeautifulSoup) -> str:
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        stack = [data]
        while stack:
            d = stack.pop()
            if isinstance(d, list):
                stack += d
            elif isinstance(d, dict):
                if isinstance(d.get("articleBody"), str):
                    return clean(d["articleBody"])
                stack += [v for v in d.values() if isinstance(v, (dict, list))]
    return ""


def paragraphs(node) -> str:
    ps = [clean(p.get_text(" ")) for p in node.find_all("p")]
    return "\n".join(p for p in ps if len(p) >= 40 and not BOILER.match(p))


def extract_body(html: str) -> tuple[str, str]:
    """(본문, 추출 방법). JSON-LD → <article> → 문단이 가장 많은 블록 순으로 시도한다."""
    soup = BeautifulSoup(html, "lxml")
    body = from_jsonld(soup)
    if len(body) >= MIN_BODY:
        return body, "jsonld"
    for t in soup(NOISE):
        t.decompose()
    candidates = soup.find_all("article") or []
    best = max((paragraphs(c) for c in candidates), key=len, default="")
    if len(best) >= MIN_BODY:
        return best, "article"
    # 직속 부모 블록별로 (긴 문단 길이 합, 40자 이상 문단 길이 합)을 세어 가장 큰 블록을 본문으로 본다.
    # 긴 문단이 있는 블록이 우선이고, 어디에도 없으면 전체 문단 길이로 고른다.
    score, parents = {}, {}
    for p in soup.find_all("p"):
        if p.parent is None:
            continue
        n = len(clean(p.get_text(" ")))
        k = id(p.parent)
        parents[k] = p.parent
        long_sum, all_sum = score.get(k, (0, 0))
        score[k] = (long_sum + (n if n >= LONG_P else 0), all_sum + (n if n >= 40 else 0))
    best = paragraphs(parents[max(score, key=score.get)]) if score else ""
    if len(best) >= MIN_BODY:
        return best, "paragraphs"
    # 국내 언론사 CMS 는 본문을 <p> 없이 <br> 로만 나누는 곳이 많다 → 직속 글자가 가장 많은 블록
    text = max((clean(" ".join(node.find_all(string=True, recursive=False)))
                for node in soup.find_all(["div", "section", "td"])), key=len, default="")
    if len(text) > len(best):
        return text, "text_block"
    return best, "paragraphs"


# ---------------------------------------------------------------------------
# 3) 실행
# ---------------------------------------------------------------------------
def load_targets() -> dict:
    """원본 *_en.jsonl 에서 guid 단위 기사 목록 (검색어가 달라 중복 수집된 기사는 하나로)."""
    targets = {}
    for f in sorted(GLOBAL_NEWS_DIR.glob("*_en.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            key = r.get("guid") or r.get("link")
            if key and r.get("link"):
                targets.setdefault(key, {"title": r.get("title"), "link": r["link"],
                                         "source": r.get("source")})
    return targets


def load_done(retry: bool) -> set:
    """이미 처리한 guid. --retry 면 성공(ok)한 것만 건너뛴다."""
    if not OUT.exists():
        return set()
    last = {}
    for line in OUT.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        last[r["guid"]] = r["status"]  # 같은 guid 가 여러 번 있으면 마지막 기록이 유효
    return {g for g, s in last.items() if s == "ok" or not retry}


def process(session: requests.Session, guid: str, t: dict) -> dict:
    rec = {"guid": guid, "title": t["title"], "source": t["source"], "google_link": t["link"],
           "url": None, "status": None, "method": None, "body": None, "body_len": 0,
           "error": None, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    try:
        rec["url"] = resolve(session, t["link"])
    except Exception as e:
        rec.update(status="decode_fail", error=f"{type(e).__name__}: {e}"[:300])
        return rec
    time.sleep(DELAY)
    try:
        r = session.get(rec["url"], timeout=TIMEOUT)
        if r.status_code >= 400:
            rec.update(status=f"http_{r.status_code}")
            return rec
        r.encoding = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" \
            else r.apparent_encoding
        body, method = extract_body(r.text)
    except Exception as e:
        rec.update(status="fetch_fail", error=f"{type(e).__name__}: {e}"[:300])
        return rec
    rec.update(method=method, body_len=len(body))
    if len(body) >= MIN_BODY:
        rec.update(status="ok", body=body)
    else:
        rec.update(status="short", body=body or None)  # 구독벽·요약만 있는 페이지
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, default=0, help="이번 실행에서 처리할 최대 건수 (0=전체)")
    ap.add_argument("--retry", action="store_true", help="실패·짧은 본문 건을 다시 시도")
    args = ap.parse_args()

    targets = load_targets()
    done = load_done(args.retry)
    todo = [(g, t) for g, t in targets.items() if g not in done]
    if args.limit:
        todo = todo[:args.limit]
    print(f"대상 {len(targets)}건, 처리됨 {len(done)}건, 이번 실행 {len(todo)}건", flush=True)

    session = requests.Session()
    session.headers.update(HEADERS)
    stats = {}
    for i, (guid, t) in enumerate(todo, 1):
        rec = process(session, guid, t)
        with OUT.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        stats[rec["status"]] = stats.get(rec["status"], 0) + 1
        print(f"[{i}/{len(todo)}] {rec['status']:<12} {rec['body_len']:>6}자  "
              f"{(rec['url'] or t['link'])[:90]}", flush=True)
        time.sleep(DELAY)
    print("결과:", ", ".join(f"{k} {v}건" for k, v in sorted(stats.items())), file=sys.stderr)


if __name__ == "__main__":
    main()
