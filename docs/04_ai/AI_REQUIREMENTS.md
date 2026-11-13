# AI 기능 요구사항

> **상태:** 작성 전 — 아래 주석의 가이드를 따라 작성한다. 작성을 시작하면 이 줄과 주석을 지우고 상태를 갱신한다.
> **관련 문서:** [masterplan](../masterplan.md)

<!--
[작성 가이드 — AI/작성자용]

목적:
  LLM·RAG가 맡는 일과 지켜야 할 조건을 정의한다.

넣을 내용:
  - AI 기능 목록: 감성(기회/위험) 분류, 핵심 이슈 추출, 모달리티 태깅, 영어 기사 번역, 기회·위험 요약, 공시 RAG Q&A
  - 기능별 입력 데이터 범위(제목 기준 / 본문 기준, 표본 추출 여부)와 그 근거 — 과제 요구: 처리 범위와 근거를 기록
  - 사전 생성 원칙: 대시보드에서 실시간 호출 금지, 결과 저장 위치
  - RAG 필수 조건: 근거 공시(공시명·제출일·링크) 표시, 근거 없으면 거절
  - 사용 모델·비용·호출량 추정, API 키 관리(.env)
  - PRD 기능(F1~F8)과의 대응표

참고할 기존 자료 (내용을 옮길 때 유실 없이 옮기고, 옮긴 뒤 masterplan.md 의 이전 현황을 갱신):
  - docs/02_product-requirements/PRD.md 2·3절
  - 가이드 6절(구현 시 유의사항)
  - requirements.txt (anthropic, langchain, chromadb)

연결 문서:
  - AI_CLASSIFICATION.md
  - NEWS_DISCLOSURE_MATCHING.md
  - AI_EVALUATION.md

작성 규칙: masterplan.md 4절 "문서 작성 규칙"을 따른다.
-->
