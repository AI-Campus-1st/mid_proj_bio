# DART 공시 데이터 명세

> **상태:** 작성 전 — 아래 주석의 가이드를 따라 작성한다. 작성을 시작하면 이 줄과 주석을 지우고 상태를 갱신한다.
> **관련 문서:** [masterplan](../masterplan.md)

<!--
[작성 가이드 — AI/작성자용]

목적:
  DART 공시 데이터의 수집 범위·형식·분류 규칙을 정의한다.

넣을 내용:
  - 분석 대상 기업 선정 근거 전체 (14개사 비교, 자격 요건 G1~G3, 공시 유형별 가중치 표, 결과 표, 기업별 선정 이유, 한계) — `docs/company_selection.md` 를 이 문서로 옮긴다
  - 사용 API: corpCode.xml, list.json, document.xml, fnlttSinglAcnt.json 과 호출 딜레이·재시도 방식
  - 공시 목록 필드(rcept_no, report_nm, pblntf_ty 등)와 공시 유형 코드 A~J
  - `event_class` / `event_weight` 분류 규칙 (`analysis/disclosure_weights.py`), 정정 공시 처리
  - 원문 zip 보관 방식과 텍스트 추출 규칙(표 → 행·칸 구분), 원문 누락 3건 사유
  - 기업별 공시·원문 건수

참고할 기존 자료 (내용을 옮길 때 유실 없이 옮기고, 옮긴 뒤 masterplan.md 의 이전 현황을 갱신):
  - docs/company_selection.md (전체)
  - docs/data_schema.md 2·3·4절
  - collect/collect_dart_*.py
  - analysis/disclosure_weights.py

연결 문서:
  - DATA_PIPELINE.md
  - ../04_ai/NEWS_DISCLOSURE_MATCHING.md
  - ../06_technical/DATABASE_SCHEMA.md

작성 규칙: masterplan.md 4절 "문서 작성 규칙"을 따른다.
-->
