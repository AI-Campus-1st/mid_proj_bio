# 시스템 구조

> **상태:** 작성 전 — 아래 주석의 가이드를 따라 작성한다. 작성을 시작하면 이 줄과 주석을 지우고 상태를 갱신한다.
> **관련 문서:** [masterplan](../masterplan.md)

<!--
[작성 가이드 — AI/작성자용]

목적:
  계층 구조와 구성 요소 간 데이터 흐름을 정의한다.

넣을 내용:
  - 계층: 수집(collect) → 재분류(analysis) → 적재(db) → AI 사전 생성(LLM·임베딩) → 대시보드(app)
  - 구성 요소별 책임과 디렉터리, 저장소(SQLite, 벡터 DB, 파일)
  - 대시보드가 API·LLM을 실시간 호출하지 않는 구조(과제 요구)
  - 실행 환경(로컬/배포), 비밀 정보 관리(.env)

참고할 기존 자료 (내용을 옮길 때 유실 없이 옮기고, 옮긴 뒤 masterplan.md 의 이전 현황을 갱신):
  - README.md 디렉터리·실행 순서
  - docs/data_schema.md 1절
  - 가이드 5·6절

연결 문서:
  - API_SPECIFICATION.md
  - DATABASE_SCHEMA.md
  - TECH_STACK.md
  - ../03_data/DATA_PIPELINE.md

작성 규칙: masterplan.md 4절 "문서 작성 규칙"을 따른다.
-->
