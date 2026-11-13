# 데이터 파이프라인

> **상태:** 작성 전 — 아래 주석의 가이드를 따라 작성한다. 작성을 시작하면 이 줄과 주석을 지우고 상태를 갱신한다.
> **관련 문서:** [masterplan](../masterplan.md)

<!--
[작성 가이드 — AI/작성자용]

목적:
  수집 → 재분류 → 적재 → 분석 산출물까지의 흐름과 재실행 방법을 정의한다.

넣을 내용:
  - 단계별 흐름도: collect(수집) → analysis/build_cdmo_news(통합·재분류) → db/build_db(적재) → LLM·임베딩(사전 생성) → 대시보드(조회)
  - 단계별 입력·출력 파일과 스크립트, 실행 순서(README 실행 순서와 일치시킬 것)
  - 재실행·이어받기 방식(_done.txt, 받은 파일 건너뛰기), 기간 변경 시 다시 돌릴 단계
  - Git에 올리는 산출물과 제외 산출물(data/db, data/raw/dart/document)
  - LLM 결과·번역(title_ko)·임베딩을 어디에 저장하고 DB 재빌드 시 어떻게 보존할지

참고할 기존 자료 (내용을 옮길 때 유실 없이 옮기고, 옮긴 뒤 masterplan.md 의 이전 현황을 갱신):
  - README.md 실행 순서
  - docs/data_schema.md 1절
  - docs/news_sort.md
  - .gitignore

연결 문서:
  - NEWS_DATA_SPEC.md
  - DART_DATA_SPEC.md
  - ../06_technical/SYSTEM_ARCHITECTURE.md

작성 규칙: masterplan.md 4절 "문서 작성 규칙"을 따른다.
-->
