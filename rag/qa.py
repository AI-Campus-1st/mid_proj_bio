"""공시 RAG 질의응답 — 색인된 공시에서 근거를 찾아 답하고, 근거가 없으면 거절한다.

설계: docs/04_ai/NEWS_DISCLOSURE_MATCHING.md 4-5 ~ 4-8절
흐름: 질문 → ① 범위 확인 → ② 검색(필터 + 유사도) → ③ 답변 생성 → ④ 인용 검증 → 답변 또는 거절
      LangChain 의 Runnable 로 네 단계를 잇는다 (CHAIN). 어느 단계에서든 거절이 정해지면 뒤 단계는 건너뛴다.
호출: 질문 한 번에 임베딩 1회 + 답변 LLM 1회 (검색 전·검색 후에 거절되면 LLM 은 부르지 않는다).
먼저 python rag/build_index.py 로 색인(chroma_db/)을 만들어 둔다.

실행 (API 비용이 든다)
  python rag/qa.py "에스티팜의 최근 단일판매·공급계약 금액은?"
  python rag/qa.py "수주 계약은?" --corp 삼성바이오로직스 --from 2025-01-01 --to 2025-12-31
  python rag/qa.py "질문" --json          # 결과 전체를 JSON 으로 출력
대시보드에서는 ask(question, corp_names=..., date_from=..., date_to=...) 를 불러 쓴다.
  - 돌려주는 값은 ask() 의 설명을 본다. 화면에는 answer 대신 answer_display([n] 번호)를 쓰면 된다.
  - 키·색인이 없거나 API 호출이 실패하면 QAError 를 던진다 (프로그램을 끝내지 않는다).
    QAError.code 는 "no_api_key" / "no_index" / "api_error".
API 키: 환경변수 OPENAI_API_KEY, 없으면 .env 의 OPENAI_API_KEY.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

from langchain_core.runnables import RunnableLambda

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "collect"))
sys.path.insert(0, str(ROOT / "rag"))
from build_index import CHROMA_DIR, COLLECTION, load_api_key  # noqa: E402
from config import COMPANIES, COMPANY_PATTERNS, DB_END, DB_START  # noqa: E402

ANSWER_MODEL = "gpt-6-luna"   # 감성 분류와 같은 모델 (설계 문서 7절 D2)
EFFORT = "low"
MAX_TOKENS = 4096             # 추론(reasoning) 토큰도 여기에 포함된다
N_CANDIDATES = 20             # 유사도 검색 한 번에 가져오는 후보 청크 수
MAX_PER_DOC = 2               # 같은 공시에서 남기는 청크 수
# 검색은 두 갈래로 한다 (AI_EVALUATION 6절). 사업·분기보고서와 증권신고서는 한 건이 수백~천 개 청크라
# 전체를 한 번에 검색하면 1~2청크짜리 수시 공시가 밀려난다. 그래서 사건성 공시만 따로 검색해 자리를 먼저 준다.
EVENT_CLASSES = ["수주", "증설", "M&A·구조개편", "자금조달", "실적", "임상·허가·기술계약", "리스크"]
N_EVENT = 5                   # 사건성 공시 검색에서 넘기는 청크 수
N_GENERAL = 2                 # 전체 검색에서 추가로 넘기는 청크 수 (정기보고서·IR·기타 포함)
N_FINAL = N_EVENT + N_GENERAL  # 답변 LLM 에 넘기는 청크 수 (최대)
# 최상위 청크의 코사인 유사도가 이 값보다 낮으면 검색 후 거절한다.
# 평가 질문의 점수 분포로 정할 값이다 (설계 문서 7절 D7). 0 이면 이 단계에서는 거절하지 않는다.
MIN_SIMILARITY = 0.0

class QAError(RuntimeError):
    """질의응답을 할 수 없는 상태 (설정 문제·API 실패). 근거가 없어 답하지 않는 거절(refused)과는 다르다."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


REFUSAL_TEXT = (f"수집한 5개사 공시({DB_START} ~ {DB_END})에서 근거를 찾지 못해 답변하지 않습니다.")
# 기업 순서는 INFORMATION_ARCHITECTURE 4-1절 (UI 명세 Q10)
OUT_OF_SCOPE_TEXT = ("이 서비스는 5개사(삼성바이오로직스, SK바이오사이언스, 프레스티지바이오로직스, 에스티팜, "
                     "바이넥스)의 공시만 다룹니다. {names} 의 공시는 수집하지 않아 답변하지 않습니다.")
NO_FLAGS = {"judgment_declined": False, "causality_unconfirmed": False}

# 범위 밖 기업. 질문에 5개사 이름 없이 이 이름만 있으면 검색하지 않고 거절한다.
# 목록에 없는 기업은 여기서 걸러지지 않고 뒤 단계(유사도·LLM·인용 검증)에서 거절된다.
OTHER_COMPANIES = [name for name, _, status in COMPANIES if status != "선정"] + [
    "론자", "Lonza", "우시", "WuXi", "캐털란트", "카탈란트", "Catalent", "후지필름", "Fujifilm",
    "써모피셔", "Thermo Fisher", "베링거인겔하임", "셀트리온", "롯데바이오로직스", "삼성바이오에피스",
    "프레스티지바이오파마", "SK팜테코", "SK바이오팜", "한미약품", "유한양행", "대웅제약", "종근당", "녹십자",
]

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "refused": {"type": "boolean"},
        "answer": {"type": "string"},
        "citations": {"type": "array", "items": {
            "type": "object",
            "properties": {"rcept_no": {"type": "string"}, "quote": {"type": "string"}},
            "required": ["rcept_no", "quote"],
            "additionalProperties": False,
        }},
        "refusal_reason": {"type": ["string", "null"]},
        "judgment_declined": {"type": "boolean"},
        "causality_unconfirmed": {"type": "boolean"},
    },
    "required": ["refused", "answer", "citations", "refusal_reason", "judgment_declined",
                 "causality_unconfirmed"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """당신은 국내 바이오 CDMO 5개사의 DART 공시를 근거로 질문에 답하는 도우미입니다.
아래 [공시 발췌]에 적힌 내용만으로 답합니다.

[규칙]
1. 발췌에 없는 수치·날짜·계약 상대방·사실을 추측하거나 보태지 않는다. 일반 지식으로 답하지 않는다.
2. 답의 각 문장 끝에 근거 공시의 접수번호를 (rcept_no) 형태로 붙인다.
3. citations 에는 답에 쓴 공시마다 rcept_no 와 quote 를 넣는다.
   quote 는 발췌에서 **글자 그대로 복사한** 한 구절(80자 이내)이다. 고쳐 쓰거나 줄이거나 이어 붙이지 않는다.
4. 발췌로 답할 수 없으면 refused 를 true 로 하고 refusal_reason 에 이유를 한 문장으로 쓴다.
   이때 answer 는 빈 문자열, citations 는 빈 배열이다.
5. 투자 판단·전망·추천을 묻는 질문에는 판단하지 않는다. 발췌에 관련 사실이 있으면 그 사실만 전하고
   "투자 판단은 하지 않는다"고 덧붙인다. 관련 사실이 없으면 4번대로 거절한다.
   질문이 투자 판단·전망·추천을 요구했으면 judgment_declined 를 true 로 한다 (답하든 거절하든).
6. 공시에 인과 관계가 적혀 있지 않으면(예: 정책 때문에 수주가 늘었다) 인과를 말하지 않고,
   "인과는 공시로 확인되지 않는다"고 덧붙인다. 이렇게 덧붙였으면 causality_unconfirmed 를 true 로 한다.
   그 밖의 경우 judgment_declined 와 causality_unconfirmed 는 false 이다.
7. 같은 계약의 원공시와 정정 공시가 함께 있으면 접수일이 늦은 정정 공시의 내용을 기준으로 답한다.
8. 답은 한국어로, 군더더기 없이 쓴다."""


def find_companies(question: str) -> list:
    return [name for name, pat in COMPANY_PATTERNS.items() if re.search(pat, question)]


def find_other_companies(question: str) -> list:
    q = question.lower()
    return [name for name in OTHER_COMPANIES if name.lower() in q]


def to_int_date(value):
    """'YYYY-MM-DD' 또는 date → 정수 YYYYMMDD (색인 메타데이터와 같은 형식)."""
    return int(str(value).replace("-", "")) if value else None


def base_report_name(report_nm: str) -> str:
    """'[기재정정]단일판매ㆍ공급계약체결' → '단일판매ㆍ공급계약체결'"""
    return re.sub(r"^(\[[^\]]*\])+", "", report_nm).strip()


def squash(text: str) -> str:
    return re.sub(r"\s+", "", text)


def refuse(state: dict, stage: str, reason: str, text: str = REFUSAL_TEXT) -> dict:
    return {**state, "refused": True, "stage": stage, "answer": text, "answer_display": text,
            "refusal_reason": reason, "citations": [], "flags": state.get("flags", dict(NO_FLAGS))}


RCEPT_REF = re.compile(r"\(\s*(\d{14}(?:\s*[,，]\s*\d{14})*)\s*\)")


def number_references(answer: str, numbers: dict) -> str:
    """답변의 '(20260918900224)' · '(번호, 번호)' 를 근거 번호 '[1]' · '[1][2]' 로 바꾼다.
    인용 목록에 없는 접수번호가 섞인 괄호는 그대로 둔다."""
    def sub(m):
        nos = re.findall(r"\d{14}", m.group(1))
        if not all(n in numbers for n in nos):
            return m.group(0)
        return "".join(f"[{numbers[n]}]" for n in dict.fromkeys(nos))
    return RCEPT_REF.sub(sub, answer)


# ---------------------------------------------------------------- ① 범위 확인
def check_scope(state: dict) -> dict:
    question = state["question"]
    in_scope = find_companies(question)
    others = find_other_companies(question)
    state = {**state, "question_companies": in_scope}
    if others and not in_scope:
        return refuse(state, "scope", f"범위 밖 기업: {', '.join(others)}",
                      OUT_OF_SCOPE_TEXT.format(names=", ".join(others)))
    return state


# ---------------------------------------------------------------- ② 검색
def build_where(corp_names: list, date_from, date_to, event_classes=None):
    conds = []
    if event_classes:
        conds.append({"event_class": {"$in": list(event_classes)}})
    if corp_names:
        conds.append({"corp_name": {"$in": list(corp_names)}})
    if date_from:
        conds.append({"rcept_date": {"$gte": to_int_date(date_from)}})
    if date_to:
        conds.append({"rcept_date": {"$lte": to_int_date(date_to)}})
    if not conds:
        return None
    return conds[0] if len(conds) == 1 else {"$and": conds}


def amended_first(chunks: list) -> list:
    """같은 기업·같은 보고서명의 공시가 여럿이면, 그 자리들 안에서 접수일이 늦은 것을 앞에 둔다."""
    groups = {}
    for i, c in enumerate(chunks):
        m = c["metadata"]
        groups.setdefault((m["corp_code"], base_report_name(m["report_nm"])), []).append(i)
    out = list(chunks)
    for idxs in groups.values():
        ordered = sorted((chunks[i] for i in idxs), key=lambda c: -c["metadata"]["rcept_date"])
        for i, c in zip(idxs, ordered):
            out[i] = c
    return out


def retrieve(state: dict) -> dict:
    if state.get("refused"):
        return state
    import chromadb
    import openai

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        col = client.get_collection(COLLECTION)
    except Exception:
        raise QAError("no_index", f"색인이 없다: {CHROMA_DIR}. 먼저 python rag/build_index.py 를 실행한다.")
    embed_model = (col.metadata or {}).get("embed_model")
    # 화면 필터의 기업과 질문에서 찾은 기업을 함께 건다. 둘 다 있으면 겹치는 기업만 본다.
    corp_names = state.get("corp_names") or []
    asked = state["question_companies"]
    if corp_names and asked:
        both = [c for c in asked if c in corp_names]
        if not both:
            return refuse(state, "search", "질문의 기업이 선택한 기업 필터 밖에 있다")
        corp_names = both
    else:
        corp_names = corp_names or asked
    date_from, date_to = state.get("date_from"), state.get("date_to")
    emb = openai.OpenAI().embeddings.create(model=embed_model, input=[state["question"]])

    def search(event_classes=None) -> list:
        res = col.query(query_embeddings=[emb.data[0].embedding], n_results=N_CANDIDATES,
                        where=build_where(corp_names, date_from, date_to, event_classes),
                        include=["documents", "metadatas", "distances"])
        return [{"id": i, "text": d, "metadata": m, "similarity": round(1 - dist, 4)}
                for i, d, m, dist in zip(res["ids"][0], res["documents"][0], res["metadatas"][0],
                                         res["distances"][0])]

    picked, per_doc = [], {}

    def take(candidates: list, limit: int) -> None:
        """유사도 높은 순으로, 같은 공시는 MAX_PER_DOC 개까지, picked 가 limit 개가 될 때까지 담는다."""
        seen = {c["id"] for c in picked}
        for c in candidates:
            if len(picked) >= limit:
                return
            no = c["metadata"]["rcept_no"]
            if c["id"] not in seen and per_doc.get(no, 0) < MAX_PER_DOC:
                per_doc[no] = per_doc.get(no, 0) + 1
                picked.append(c)

    event, general = search(EVENT_CLASSES), search()
    take(event, N_EVENT)            # 사건성 공시 먼저
    take(general, N_FINAL)          # 남은 자리는 전체 검색 결과로 채운다
    top = max((c["similarity"] for c in event[:1] + general[:1]), default=None)
    state = {**state, "retrieved": amended_first(picked), "top_similarity": top,
             "filter": {"corp_names": corp_names, "date_from": date_from, "date_to": date_to},
             "usage": {"embedding_tokens": emb.usage.total_tokens}}
    if not picked:
        return refuse(state, "search", "조건에 맞는 공시가 없다")
    if top < MIN_SIMILARITY:
        return refuse(state, "search", f"최상위 유사도 {top} < 임계값 {MIN_SIMILARITY}")
    return state


# ---------------------------------------------------------------- ③ 답변 생성
def build_context(chunks: list) -> str:
    blocks = []
    for c in chunks:
        m = c["metadata"]
        kind = "정정 공시" if m["is_amended"] else "원공시"
        blocks.append(f"<공시 rcept_no=\"{m['rcept_no']}\" 구분=\"{kind}\">\n{c['text']}\n</공시>")
    return "\n\n".join(blocks)


def generate(state: dict) -> dict:
    if state.get("refused"):
        return state
    import openai

    user = f"[공시 발췌]\n{build_context(state['retrieved'])}\n\n[질문]\n{state['question']}"
    res = openai.OpenAI().chat.completions.create(
        model=ANSWER_MODEL,
        max_completion_tokens=MAX_TOKENS,
        reasoning_effort=EFFORT,
        messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}],
        response_format={"type": "json_schema", "json_schema": {
            "name": "disclosure_answer", "strict": True, "schema": OUTPUT_SCHEMA}},
    )
    usage = {**state["usage"], "input_tokens": res.usage.prompt_tokens,
             "output_tokens": res.usage.completion_tokens}
    state = {**state, "usage": usage, "model": ANSWER_MODEL}
    try:
        out = json.loads(res.choices[0].message.content or "")
    except json.JSONDecodeError:
        return refuse(state, "generate", "LLM 응답이 JSON 이 아니다")
    state["flags"] = {k: bool(out.get(k)) for k in NO_FLAGS}
    if out["refused"]:
        return refuse(state, "generate", out.get("refusal_reason") or "LLM 이 답할 수 없다고 판단")
    return {**state, "answer": out["answer"], "raw_citations": out["citations"]}


# ---------------------------------------------------------------- ④ 인용 검증
def verify(state: dict) -> dict:
    if state.get("refused"):
        return state
    by_doc = {}
    for c in state["retrieved"]:
        by_doc.setdefault(c["metadata"]["rcept_no"], []).append(c)
    raw = state.pop("raw_citations")
    if not raw:
        return refuse(state, "verify", "인용이 없다")
    citations, numbers = [], {}
    for cit in raw:
        chunks = by_doc.get(cit["rcept_no"])
        if not chunks:
            return refuse(state, "verify", f"검색되지 않은 공시를 인용했다: {cit['rcept_no']}")
        quote = squash(cit["quote"])
        if not quote or not any(quote in squash(c["text"]) for c in chunks):
            return refuse(state, "verify", f"인용 구절이 원문에 없다: {cit['quote'][:60]}")
        # 같은 공시를 여러 번 인용하면 한 항목으로 합치고 구절만 모은다 (같은 공시 = 같은 번호)
        if cit["rcept_no"] in numbers:
            citations[numbers[cit["rcept_no"]] - 1]["quotes"].append(cit["quote"])
            continue
        # 공시명·접수일·링크는 LLM 이 쓰지 않고 색인 메타데이터에서 채운다
        m = chunks[0]["metadata"]
        d = str(m["rcept_date"])
        numbers[m["rcept_no"]] = len(citations) + 1
        citations.append({"n": numbers[m["rcept_no"]], "rcept_no": m["rcept_no"], "quote": cit["quote"],
                          "quotes": [cit["quote"]], "corp_name": m["corp_name"],
                          "report_nm": m["report_nm"], "is_amended": m["is_amended"],
                          "rcept_date": f"{d[:4]}-{d[4:6]}-{d[6:]}", "url": m["url"]})
    return {**state, "refused": False, "stage": "answered", "refusal_reason": None,
            "citations": citations, "answer_display": number_references(state["answer"], numbers)}


CHAIN = (RunnableLambda(check_scope) | RunnableLambda(retrieve) | RunnableLambda(generate)
         | RunnableLambda(verify))


def ask(question: str, corp_names=None, date_from=None, date_to=None) -> dict:
    """질문에 답한다. 돌려주는 값의 주요 키:
    refused        bool. True 면 answer 에 거절 문구가 들어 있다
    stage          scope(검색 전 거절) / search(검색 후 거절) / generate(LLM 이 거절) / verify(인용 검증 실패)
                   / answered
    answer         LLM 답변 원문. 문장 끝에 (접수번호) 가 붙어 있다
    answer_display 화면용. (접수번호) 를 citations 의 번호 [1], [2] 로 바꾼 것 (같은 공시는 같은 번호)
    refusal_reason 거절 이유 (답변이면 None)
    citations      [{n, rcept_no, corp_name, report_nm, is_amended, rcept_date, url, quote, quotes}]
                   n 은 answer_display 의 번호. quote 는 첫 인용 구절, quotes 는 같은 공시의 구절 전부
    flags          {judgment_declined: 투자 판단을 요구한 질문이라 판단하지 않음,
                    causality_unconfirmed: "인과는 공시로 확인되지 않는다"를 덧붙임}
    retrieved, top_similarity, filter, usage  검색·사용량 정보
    설정 문제나 API 실패는 거절이 아니라 QAError 로 알린다.
    """
    import openai

    load_api_key()
    if not os.environ.get("OPENAI_API_KEY"):
        raise QAError("no_api_key", "OPENAI_API_KEY 가 없다. .env 에 키를 넣는다.")
    try:
        return CHAIN.invoke({"question": question.strip(), "corp_names": corp_names,
                             "date_from": date_from, "date_to": date_to})
    except openai.OpenAIError as e:
        raise QAError("api_error", f"OpenAI 호출 실패: {type(e).__name__}") from e


def format_result(r: dict) -> str:
    lines = [f"질문: {r['question']}"]
    if r["refused"]:
        lines += [f"[거절 — {r['stage']} 단계] {r['answer']}", f"  이유: {r['refusal_reason']}"]
    else:
        lines += ["답변: " + r["answer_display"], "", "근거 공시",
                  "| # | 기업 | 공시명 | 제출일 | 근거 구절 | 링크 |", "|---|---|---|---|---|---|"]
        for c in r["citations"]:
            lines.append(f"| [{c['n']}] | {c['corp_name']} | {c['report_nm']} | {c['rcept_date']} | "
                         f"{' / '.join(c['quotes'])} | {c['url']} |")
    if any(r.get("flags", {}).values()):
        lines.append(f"표시: {r['flags']}")
    if r.get("top_similarity") is not None:
        found = ", ".join(f"{c['metadata']['rcept_no']}({c['similarity']})" for c in r["retrieved"])
        lines.append(f"\n검색: 최상위 유사도 {r['top_similarity']}, 넘긴 청크 {found}")
    if r.get("usage"):
        lines.append(f"사용량: {r['usage']}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="공시 RAG 질의응답")
    ap.add_argument("question")
    ap.add_argument("--corp", action="append", default=[], help="기업 필터 (여러 번 지정 가능)")
    ap.add_argument("--from", dest="date_from", help="접수일 시작 YYYY-MM-DD")
    ap.add_argument("--to", dest="date_to", help="접수일 끝 YYYY-MM-DD")
    ap.add_argument("--json", action="store_true", help="결과 전체를 JSON 으로 출력")
    args = ap.parse_args()
    try:
        r = ask(args.question, args.corp, args.date_from, args.date_to)
    except QAError as e:
        sys.exit(f"[{e.code}] {e}")
    print(json.dumps(r, ensure_ascii=False, indent=2) if args.json else format_result(r))


if __name__ == "__main__":
    main()
