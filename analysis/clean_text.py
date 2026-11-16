"""뉴스 제목·본문 텍스트 정제 (정규표현식).

원문(news.title, news.body)은 그대로 두고, 정제한 텍스트를 따로 만든다.
db/build_db.py 가 적재할 때 clean_title / clean_body 를 불러 news_clean 테이블을 채운다.
규칙은 "기사 내용이 아닌 것만 지운다"를 원칙으로 좁게 잡았다 (docs/eda_report.md 2절).

단독 실행하면 현재 DB 기준으로 규칙별 적용 건수와 전후 글자 수를 출력한다.
실행: python analysis/clean_text.py
"""
import html
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------- 공통
INVISIBLE = re.compile(r"[﻿​-‏⁠­]")      # BOM, 폭 없는 공백, soft hyphen
SPACES = re.compile(r"[ \t 　]+")
HTML_TAG = re.compile(r"</?[A-Za-z][A-Za-z0-9]*(?:\s[^<>]*)?/?>")  # <b>, <br/> 등. <앵커>·<히트뉴스>는 남는다
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
URL = re.compile(r"(?:https?://|www\.)[^\s<>\]\)]+")
QUOTES = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'", "＂": '"', "＇": "'"})


def _common(s: str) -> str:
    s = html.unescape(s)
    s = INVISIBLE.sub("", s)
    s = HTML_TAG.sub(" ", s)
    return s.translate(QUOTES)


def clean_title(title: str) -> str:
    """제목: 보이지 않는 문자·HTML 엔티티·태그 제거, 따옴표 통일, 공백 정리.
    [단독]·[르포] 같은 말머리와 말줄임표는 내용이므로 남긴다."""
    return SPACES.sub(" ", _common(title or "").replace("\n", " ")).strip()


# ---------------------------------------------------------------- 본문
# 기사 첫머리의 발신지·기자 표기: [팜뉴스=홍길동 기자], (서울=연합뉴스) 홍길동 기자 =, 【 청년일보 】
BYLINE_HEAD = re.compile(
    r"\A\s*(?:"
    r"[\[\(【][^\]\)】\n]{0,40}(?:=|기자|특파원|뉴스1|연합뉴스|뉴시스)[^\]\)】\n]{0,40}[\]\)】]"
    r"|【[^】\n]{1,20}】"
    r")\s*(?:[가-힣]{2,4}\s?(?:기자|특파원)\s?=\s*)?")
# 줄 전체가 기사 내용이 아닌 경우 (줄 단위 본문에만 적용)
BOILER_LINE = re.compile(
    r"무단\s?전재|재배포\s?금지|배포\s?금지|저작권자|All rights reserved|^\s*[\[<(]?\s*(?:[ⓒ©]|Copyright)"
    r"|제보를?\s?(?:기다|받습|로 함께)|제보가 .{0,20}(?:변화|뉴스)|구독해\s?주세요|구독하기 클릭"
    r"|^\s*\[(?:제보|구독)\]|^\s*▶\s?(?:카카오톡|이메일|뉴스 홈페이지|다른기사보기)"
    r"|퍼가실 때는|네이버뉴스제휴위원회 심사 규정"
    r"|^\s*(?:댓글|관련기사|관련종목|- 반대순|- 찬성순|- 최신순|우선적으로 보여줍니다\.)\s*$"
    r"|건전한 토론문화를 위해|문의메일\s?:|신문사업 등록번호|기사문의 및 제보|기사제보\s*$", re.I)
LINK_LEAD = re.compile(r"^\s*▶\s?기사 바로가기")               # 다음 줄(다른 기사 제목)까지 지운다
# 이메일·URL을 지운 뒤 기자 서명만 남은 줄: "김동주 기자", "보스턴(미국)=강민성기자", "[바이오타임즈=홍길동 기자]"
SIGNATURE = re.compile(
    r"^[\s\[\(【<\-|/_]*(?:[가-힣A-Za-z·()\s]{0,20}[=/]\s?)?[가-힣]{2,4}\s?(?:[가-힣A-Za-z]{0,6}\s)?"
    r"(?:기자|특파원|PD|대기자)[\s\]\)】>|/_.,]*$")
# 한 줄짜리 본문(제공 뉴스)의 끝에 붙은 문구
TAIL_ONELINE = re.compile(
    r"\s*(?:독자 문의\s+)?(?:[가-힣A-Za-z0-9 ]{0,12}\s)?Copyright\s.{0,80}$"
    r"|\s*무단\s?전재 및 재배포.{0,30}$"
    r"|\s*(?:당신의 제보가 뉴스로|발로 뛰는 .{0,10}는 24시간|[가-힣A-Za-z]{0,12}\s?는 여러분의 제보|기사문의 및 제보"
    r"|기자 프로필|제보하기 전화|응원의 한마디).{0,400}$")
# 본문 맨 끝, 문장이 끝난 뒤에 붙은 기자 서명: "...것이다. 장은파 기자", 마지막 줄 "굿모닝경제 김형수 기자"
TAIL_SIGNATURE = re.compile(
    r"(?<=[.\n\"'])\s*(?:[가-힣A-Za-z]{2,10} )?[가-힣]{2,4} (?:[가-힣A-Za-z]{2,10} )?기자\s*\Z")
CAPTION = re.compile(r"[\[\(](?:사진|자료|제공|출처)\s?[=:][^\]\)\n]{1,40}[\]\)]")


def clean_body(body: str | None) -> str | None:
    """본문: 기사 내용이 아닌 표기(발신지·기자 서명, 저작권·제보·구독 문구, 이메일·URL, 사진 출처)를
    지우고 공백을 정리한다. 줄바꿈은 문단 구분으로 남긴다."""
    if not body:
        return None
    s = _common(body).replace("\r\n", "\n").replace("\r", "\n")
    s = BYLINE_HEAD.sub("", s, count=1)
    s = CAPTION.sub(" ", s)
    if "\n" in s:
        out, skip = [], False
        for ln in s.split("\n"):
            if skip:                      # '▶기사 바로가기:' 다음 줄
                skip = False
                continue
            if LINK_LEAD.search(ln):
                skip = True
                continue
            if len(ln) <= 200 and BOILER_LINE.search(ln):
                continue
            had = bool(EMAIL.search(ln) or URL.search(ln))
            ln = SPACES.sub(" ", URL.sub(" ", EMAIL.sub(" ", ln))).strip()
            if had and (len(ln) <= 3 or SIGNATURE.match(ln)):
                continue                  # 이메일·URL만 있던 줄, 기자 서명 줄
            out.append(ln)
        s = "\n".join(out)
        s = re.sub(r"\n{3,}", "\n\n", s)
        last = s.rstrip().rsplit("\n", 1)[-1]
        if len(last) <= 40 and SIGNATURE.match(last):   # 맨 끝의 기자 서명 줄
            s = s.rstrip()[: -len(last)]
    else:
        for _ in range(3):                # 저작권 문구와 제보 문구가 겹쳐 붙은 경우
            s2 = TAIL_ONELINE.sub("", s)
            if s2 == s:
                break
            s = s2
        s = SPACES.sub(" ", URL.sub(" ", EMAIL.sub(" ", s)))
    s = TAIL_SIGNATURE.sub("", s)
    return s.strip() or None


# ---------------------------------------------------------------- 점검
def report() -> None:
    sys.path.insert(0, str(ROOT / "collect"))
    from config import DB_PATH
    con = sqlite3.connect(DB_PATH)
    rows = con.execute("SELECT origin, title, body FROM news").fetchall()
    stat = Counter()
    for origin, title, body in rows:
        stat[origin, "n"] += 1
        stat[origin, "title_changed"] += clean_title(title) != title
        if body:
            cb = clean_body(body) or ""
            stat[origin, "body_n"] += 1
            stat[origin, "body_changed"] += cb != body
            stat[origin, "chars_before"] += len(body)
            stat[origin, "chars_after"] += len(cb)
            for name, pat in (("email", EMAIL), ("url", URL), ("copyright", re.compile("무단\\s?전재|Copyright"))):
                stat[origin, name + "_before"] += bool(pat.search(body))
                stat[origin, name + "_after"] += bool(pat.search(cb))
    keys = ["n", "title_changed", "body_n", "body_changed", "chars_before", "chars_after",
            "email_before", "email_after", "url_before", "url_after", "copyright_before", "copyright_after"]
    print("origin," + ",".join(keys))
    for origin in sorted({o for o, _ in stat}):
        print(origin + "," + ",".join(str(stat[origin, k]) for k in keys))


if __name__ == "__main__":
    report()
