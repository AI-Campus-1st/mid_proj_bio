# API·인터페이스 명세

> **상태:** 작성 전 — 아래 주석의 가이드를 따라 작성한다. 작성을 시작하면 이 줄과 주석을 지우고 상태를 갱신한다.
> **관련 문서:** [masterplan](../masterplan.md)

<!--
[작성 가이드 — AI/작성자용]

목적:
  외부 API 사용 방식과 내부 모듈 간 인터페이스를 정의한다.

넣을 내용:
  - 외부 API: DART OpenAPI(엔드포인트, 파라미터, 제한, 에러 코드 014 등), 구글 뉴스 RSS(검색 문법, locale, 100건 제한), LLM API
  - 내부 인터페이스: 대시보드가 쓰는 조회 함수/SQL(뷰 v_documents, v_company_daily 등)과 반환 형식
  - RAG 체인의 입력·출력 형식(질문 → 답변 + 근거 목록)

참고할 기존 자료 (내용을 옮길 때 유실 없이 옮기고, 옮긴 뒤 masterplan.md 의 이전 현황을 갱신):
  - collect/*.py
  - db/schema.sql
  - docs/data_schema.md 6절(조회 예시)

연결 문서:
  - SYSTEM_ARCHITECTURE.md
  - DATABASE_SCHEMA.md

작성 규칙: masterplan.md 4절 "문서 작성 규칙"을 따른다.
-->
