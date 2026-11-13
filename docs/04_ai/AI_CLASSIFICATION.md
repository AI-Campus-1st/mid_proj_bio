# LLM 분류·추출 설계

> **상태:** 작성 전 — 아래 주석의 가이드를 따라 작성한다. 작성을 시작하면 이 줄과 주석을 지우고 상태를 갱신한다.
> **관련 문서:** [masterplan](../masterplan.md)

<!--
[작성 가이드 — AI/작성자용]

목적:
  LLM으로 수행하는 감성 분류·이슈 추출·태깅의 프롬프트와 출력 형식을 정의한다.

넣을 내용:
  - 작업별 프롬프트 설계(시스템 프롬프트, 예시, 출력 JSON 스키마)
  - 라벨 정의: 감성(기회/위험/중립)의 판단 기준, 이슈 추출 단위, 모달리티 태그 목록
  - 규칙 기반 분류(03_data/NEWS_CLASSIFICATION.md)와의 관계 — 대체인지 보완인지
  - 처리 범위와 배치 방식, 실패·재시도 처리, 결과 저장 테이블
  - 영어 기사 번역 프롬프트와 title_ko 저장 방식

참고할 기존 자료 (내용을 옮길 때 유실 없이 옮기고, 옮긴 뒤 masterplan.md 의 이전 현황을 갱신):
  - docs/news_sort.md 3절
  - docs/02_product-requirements/PRD.md F1~F3·F8

연결 문서:
  - AI_REQUIREMENTS.md
  - AI_EVALUATION.md
  - ../03_data/NEWS_CLASSIFICATION.md

작성 규칙: masterplan.md 4절 "문서 작성 규칙"을 따른다.
-->
