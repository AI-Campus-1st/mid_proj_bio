# 뉴스 분류 체계

> **상태:** 작성 전 — 아래 주석의 가이드를 따라 작성한다. 작성을 시작하면 이 줄과 주석을 지우고 상태를 갱신한다.
> **관련 문서:** [masterplan](../masterplan.md)

<!--
[작성 가이드 — AI/작성자용]

목적:
  뉴스를 이슈 카테고리·키워드로 나누는 규칙 기반 분류를 정의한다. (LLM 분류는 04_ai/AI_CLASSIFICATION.md)

넣을 내용:
  - 카테고리 체계: 가이드의 4개 카테고리(규제 및 정책 / 기술 및 트렌드 / 시장 및 경쟁 / 공급망 및 인프라)와 바이오 키워드 5개
  - CDMO 키워드 6개(규제·정책, 지정학, 모달리티, 생산능력, 수주, 경쟁 구도)의 정의·주요 이슈·카테고리
  - CDMO 관련성 게이트(GATE, GATE_EN)와 키워드 규칙(RULES, RULES_EN), 제목·본문 기준 임계값
  - 근거 컬럼(title/body/query/none)의 의미와 신뢰도
  - 중복 판정 규칙(정규화 제목 + 7일, URL)
  - 분류 결과 집계표와 알려진 오분류 사례

참고할 기존 자료 (내용을 옮길 때 유실 없이 옮기고, 옮긴 뒤 masterplan.md 의 이전 현황을 갱신):
  - docs/news_sort.md 1·3·4·5절
  - analysis/build_cdmo_news.py
  - docs/data_schema.md 3절

연결 문서:
  - NEWS_DATA_SPEC.md
  - ../04_ai/AI_CLASSIFICATION.md
  - ../04_ai/AI_EVALUATION.md

작성 규칙: masterplan.md 4절 "문서 작성 규칙"을 따른다.
-->
