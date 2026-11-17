"""공시 RAG 색인 — 공시 원문을 청킹·임베딩해 chromadb 에 저장한다.

설계: docs/04_ai/NEWS_DISCLOSURE_MATCHING.md 4-2 ~ 4-4절
대상: disclosure_documents 의 본문(seq = 1). 첨부(seq >= 2)는 색인하지 않는다.
흐름: DB 조회 → 청킹(1,000자 / 겹침 150자) → 머리말 붙이기 → OpenAI 임베딩 → chroma_db/ 의 'disclosures' 컬렉션
      이 스크립트 한 번에 청킹·임베딩·적재가 모두 일어난다. chromadb 는 폴더에 저장되므로 따로 띄울 서버가 없다.
재실행: 이미 색인된 청크(ID 기준)는 건너뛴다. 중간에 끊기면 같은 명령을 다시 실행한다.
        임베딩 모델이나 청크 크기를 바꿀 때는 --reset 으로 컬렉션을 지우고 다시 만든다.

실행 (먼저 --dry-run 으로 청크 수와 예상 비용을 확인한다. 실제 실행은 임베딩 API 비용이 든다)
  python rag/build_index.py --event-class 수주 --dry-run   # 수주 공시만, 호출하지 않고 확인
  python rag/build_index.py --event-class 수주             # 수주 공시만 색인 (시험)
  python rag/build_index.py --dry-run                      # 전체, 호출하지 않고 확인
  python rag/build_index.py                                # 전체 색인 (이미 끝난 청크는 제외)
API 키: 환경변수 OPENAI_API_KEY, 없으면 .env 의 OPENAI_API_KEY.
"""
import argparse
import os
import sqlite3
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "collect"))
from config import DB_PATH  # noqa: E402

CHROMA_DIR = ROOT / "chroma_db"
COLLECTION = "disclosures"
EMBED_MODEL = "text-embedding-3-small"
CHUNK_SIZE = 1000       # 글자 수 (가설, 설계 문서 7절 D6)
CHUNK_OVERLAP = 150
SEPARATORS = ["\n\n", "\n", " ", ""]
BATCH = 64              # 임베딩 API 한 번에 보내는 청크 수
RETRIES = 4
KST = timezone(timedelta(hours=9))
# 예상 비용 계산용 (1M 토큰당 USD). 실제 청구액은 콘솔에서 확인한다.
PRICE = {"text-embedding-3-small": 0.02, "text-embedding-3-large": 0.13}
# dry-run 에서 쓰는 글자당 토큰 수. 한국어 공시는 실측 전이라 넉넉하게 1.0 으로 잡는다 (상한 추정).
TOKENS_PER_CHAR = 1.0

QUERY = """
SELECT d.rcept_no, x.seq, x.text, d.corp_code, c.corp_name, d.rcept_date, d.report_nm,
       d.event_class, d.is_amended, d.url
FROM disclosure_documents x
JOIN disclosures d ON d.rcept_no = x.rcept_no
JOIN companies c ON c.corp_code = d.corp_code
WHERE x.seq = 1 AND length(trim(x.text)) > 0
ORDER BY d.rcept_date, d.rcept_no
"""


def load_api_key() -> None:
    """환경변수에 키가 없으면 .env 에서 읽어 넣는다 (값은 출력하지 않는다)."""
    if os.environ.get("OPENAI_API_KEY"):
        return
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("OPENAI_API_KEY="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val:
                    os.environ["OPENAI_API_KEY"] = val


def load_documents(event_classes: list, limit: int) -> list:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(QUERY)]
    con.close()
    if event_classes:
        known = {r["event_class"] for r in rows}
        unknown = [e for e in event_classes if e not in known]
        if unknown:
            sys.exit(f"없는 event_class: {unknown}. 가능한 값: {sorted(known)}")
        rows = [r for r in rows if r["event_class"] in event_classes]
    return rows[:limit] if limit else rows


def header(doc: dict) -> str:
    """청크 앞에 붙이는 머리말. 청크만 떼어 놓아도 어느 회사의 어떤 공시인지 남도록 한다."""
    return f"[{doc['corp_name']} | {doc['report_nm']} | {doc['rcept_date']}]"


def make_chunks(docs: list, chunk_size: int, overlap: int) -> list:
    """공시마다 본문을 잘라 (id, 임베딩할 글, 메타데이터) 목록을 만든다."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap,
                                              separators=SEPARATORS)
    out = []
    for doc in docs:
        text = doc["text"].strip()
        parts = [text] if len(text) <= chunk_size else splitter.split_text(text)
        for i, part in enumerate(parts):
            out.append({
                "id": f"{doc['rcept_no']}-{doc['seq']}-{i}",
                "document": f"{header(doc)}\n{part}",
                "metadata": {
                    "rcept_no": doc["rcept_no"],
                    "seq": doc["seq"],
                    "chunk_idx": i,
                    "corp_code": doc["corp_code"],
                    "corp_name": doc["corp_name"],
                    "rcept_date": int(doc["rcept_date"].replace("-", "")),   # 기간 필터용 정수 YYYYMMDD
                    "report_nm": doc["report_nm"],
                    "event_class": doc["event_class"],
                    "is_amended": int(doc["is_amended"]),
                    "url": doc["url"],
                },
            })
    return out


def open_collection(model: str, chunk_size: int, overlap: int, reset: bool):
    import chromadb

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    if reset:
        try:
            client.delete_collection(COLLECTION)
            print(f"컬렉션 '{COLLECTION}' 을 지웠다 (--reset)")
        except Exception:
            pass
    settings = {"embed_model": model, "chunk_size": chunk_size, "chunk_overlap": overlap}
    col = client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine", **settings})
    saved = col.metadata or {}
    diff = {k: (saved.get(k), v) for k, v in settings.items() if saved.get(k) != v}
    if diff:
        sys.exit(f"기존 색인과 설정이 다르다 (기존, 지금): {diff}\n"
                 "한 컬렉션에 다른 모델·청크 크기를 섞을 수 없다. --reset 으로 다시 만든다.")
    return col


def existing_ids(col) -> set:
    ids, offset, page = set(), 0, 5000
    while True:
        got = col.get(include=[], limit=page, offset=offset)["ids"]
        ids.update(got)
        if len(got) < page:
            return ids
        offset += page


def embed(client, model: str, texts: list):
    """임베딩 호출. 일시적 오류는 간격을 늘려 다시 시도한다. (벡터 목록, 사용 토큰 수)를 돌려준다."""
    import openai

    for attempt in range(RETRIES):
        try:
            res = client.embeddings.create(model=model, input=texts)
            return [d.embedding for d in res.data], res.usage.total_tokens
        except (openai.RateLimitError, openai.APIConnectionError, openai.InternalServerError) as e:
            if attempt == RETRIES - 1:
                raise
            wait = 5 * 2 ** attempt
            print(f"  일시 오류({type(e).__name__}), {wait}초 뒤 재시도")
            time.sleep(wait)


def summarize(docs: list, chunks: list) -> None:
    by_class = Counter(d["event_class"] for d in docs)
    lens = sorted(len(c["document"]) for c in chunks)
    print(f"공시 {len(docs):,}건 → 청크 {len(chunks):,}개, 임베딩할 글자 {sum(lens):,}자")
    print("  event_class: " + ", ".join(f"{k} {v}" for k, v in by_class.most_common()))
    if lens:
        print(f"  청크 길이(머리말 포함): 최소 {lens[0]} / 중앙 {lens[len(lens) // 2]} / 최대 {lens[-1]}")
    per_doc = Counter(c["metadata"]["rcept_no"] for c in chunks)
    print(f"  공시당 청크: 1개짜리 {sum(v == 1 for v in per_doc.values())}건, 최대 {max(per_doc.values())}개")


def main() -> None:
    ap = argparse.ArgumentParser(description="공시 원문을 청킹·임베딩해 chromadb 에 색인한다")
    ap.add_argument("--event-class", action="append", default=[],
                    help="이 event_class 만 색인 (여러 번 지정 가능). 생략하면 전체")
    ap.add_argument("--limit", type=int, default=0, help="앞에서부터 이 건수의 공시만 (시험용)")
    ap.add_argument("--dry-run", action="store_true", help="API 를 호출하지 않고 청크 수·예상 비용만 출력")
    ap.add_argument("--reset", action="store_true", help="기존 컬렉션을 지우고 처음부터 색인")
    ap.add_argument("--model", default=EMBED_MODEL)
    ap.add_argument("--chunk-size", type=int, default=CHUNK_SIZE)
    ap.add_argument("--chunk-overlap", type=int, default=CHUNK_OVERLAP)
    args = ap.parse_args()

    if not Path(DB_PATH).exists():
        sys.exit(f"DB 가 없다: {DB_PATH}. 먼저 python db/build_db.py 를 실행한다.")
    docs = load_documents(args.event_class, args.limit)
    if not docs:
        sys.exit("색인할 공시 원문이 없다. disclosure_documents 가 비어 있으면 DB 를 다시 빌드한다.")
    chunks = make_chunks(docs, args.chunk_size, args.chunk_overlap)
    summarize(docs, chunks)
    price = PRICE.get(args.model)

    if args.dry_run:
        chars = sum(len(c["document"]) for c in chunks)
        tokens = chars * TOKENS_PER_CHAR
        cost = f"${tokens / 1e6 * price:.3f}" if price else "가격표에 없는 모델"
        print(f"[dry-run] 모델 {args.model}, 예상 토큰 최대 {tokens:,.0f} (글자당 {TOKENS_PER_CHAR} 가정), "
              f"예상 비용 최대 {cost}")
        print("[dry-run] API 를 호출하지 않았고 chroma_db/ 도 바꾸지 않았다.")
        return

    load_api_key()
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY 가 없다. .env 에 키를 넣는다.")
    import openai

    col = open_collection(args.model, args.chunk_size, args.chunk_overlap, args.reset)
    done = existing_ids(col)
    todo = [c for c in chunks if c["id"] not in done]
    print(f"이미 색인됨 {len(chunks) - len(todo):,}개, 이번에 색인 {len(todo):,}개 (모델 {args.model})")
    client = openai.OpenAI()
    total_tokens, start = 0, time.time()
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        vectors, used = embed(client, args.model, [c["document"] for c in batch])
        col.add(ids=[c["id"] for c in batch], embeddings=vectors,
                documents=[c["document"] for c in batch], metadatas=[c["metadata"] for c in batch])
        total_tokens += used
        n = i + len(batch)
        if n == len(todo) or (i // BATCH) % 20 == 19:
            print(f"  {n:,}/{len(todo):,} 청크, 누적 {total_tokens:,} 토큰")

    chars = sum(len(c["document"]) for c in todo)
    now = datetime.now(KST).isoformat(timespec="seconds")
    print(f"완료 {now}: 컬렉션 '{COLLECTION}' 청크 {col.count():,}개 ({CHROMA_DIR.name}/), "
          f"{time.time() - start:.0f}초")
    if todo:
        cost = f"${total_tokens / 1e6 * price:.4f}" if price else "가격표에 없는 모델"
        print(f"이번 실행: {total_tokens:,} 토큰 (글자당 {total_tokens / chars:.2f}), 예상 비용 {cost}")


if __name__ == "__main__":
    main()
