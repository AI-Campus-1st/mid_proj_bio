# 뉴스-공시 연계와 공시 RAG

> **상태:** 작성 전 — 아래 주석의 가이드를 따라 작성한다. 작성을 시작하면 이 줄과 주석을 지우고 상태를 갱신한다.
> **관련 문서:** [masterplan](../masterplan.md)

<!--
[작성 가이드 — AI/작성자용]

목적:
  뉴스 이슈를 공시와 연결하는 규칙과 공시 Q&A(RAG) 구성을 정의한다.

넣을 내용:
  - 뉴스-공시 매칭 규칙: 같은 기업(news_companies의 title/body만), 시점 창(예: ±N일), 이슈 키워드 ↔ event_class 대응
  - 공시 원문 청킹 기준(본문/첨부, 표 처리), 임베딩 모델, 벡터 DB(chromadb) 구성과 메타데이터(rcept_no, corp, date, url)
  - 검색·답변 체인(LangChain), 근거 표시 형식, 근거 부족 시 거절 기준
  - 질의응답 예시(대표 시나리오: 정책 이후 수주 계약 내용)

참고할 기존 자료 (내용을 옮길 때 유실 없이 옮기고, 옮긴 뒤 masterplan.md 의 이전 현황을 갱신):
  - docs/data_schema.md (disclosures, disclosure_documents, v_company_daily, v_documents)
  - docs/02_product-requirements/PRD.md F5

연결 문서:
  - AI_REQUIREMENTS.md
  - AI_EVALUATION.md
  - ../03_data/DART_DATA_SPEC.md

작성 규칙: masterplan.md 4절 "문서 작성 규칙"을 따른다.
-->
