# 데이터베이스 스키마

> **상태:** 작성 전 — 아래 주석의 가이드를 따라 작성한다. 작성을 시작하면 이 줄과 주석을 지우고 상태를 갱신한다.
> **관련 문서:** [masterplan](../masterplan.md)

<!--
[작성 가이드 — AI/작성자용]

목적:
  통합 DB 스키마의 공식 문서. `docs/data_schema.md` 를 이 문서로 옮긴다.

넣을 내용:
  - 테이블·뷰 정의와 관계도: companies, news, news_cdmo_keywords, news_keywords, news_companies, disclosures, disclosure_documents, meta, v_documents, v_company_daily
  - 컬럼 설명(lang, title_ko 포함), 적재 규칙, 적재 결과 건수, 조회 예시
  - 추가 예정 테이블: LLM 분류 결과, 모달리티 태그, 뉴스-공시 매칭 결과, 번역
  - DB 재빌드 시 보존해야 할 데이터(title_ko 등)와 처리 방법

참고할 기존 자료 (내용을 옮길 때 유실 없이 옮기고, 옮긴 뒤 masterplan.md 의 이전 현황을 갱신):
  - docs/data_schema.md (전체)
  - db/schema.sql
  - db/build_db.py

연결 문서:
  - ../03_data/DATA_PIPELINE.md
  - SYSTEM_ARCHITECTURE.md

작성 규칙: masterplan.md 4절 "문서 작성 규칙"을 따른다.
-->
