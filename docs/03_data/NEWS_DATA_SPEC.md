# 뉴스 데이터 명세

> **상태:** 작성 전 — 아래 주석의 가이드를 따라 작성한다. 작성을 시작하면 이 줄과 주석을 지우고 상태를 갱신한다.
> **관련 문서:** [masterplan](../masterplan.md)

<!--
[작성 가이드 — AI/작성자용]

목적:
  뉴스 데이터가 어디서 왔고 어떤 형태인지 정의한다.

넣을 내용:
  - 출처 5종(제공 / 팀원수집 / 기업명검색 / CDMO검색 / 해외검색)별 수집 방식, 원본 위치, 기간, 건수, 본문 유무
  - 원본 형식: 제공 CSV 컬럼, 구글 뉴스 RSS jsonl 필드(title, source, pub_date, link, guid, query, window_*), 팀원 CSV 컬럼
  - 통합본 `03_CDMO_news_3y/*묶음*.csv` 컬럼 정의(수집키워드, 대표키워드, CDMO관련근거, 키워드근거, 원수집키워드, 수집출처, 언어)
  - 검색어 목록: `collect/config.py` 의 `CDMO_QUERIES`, `GLOBAL_QUERIES`
  - 데이터 품질: 기간별 분포 편중(2026년 집중), 제목만 있는 기사, 구글 검색 100건 제한, 매체명 꼬리 제거

참고할 기존 자료 (내용을 옮길 때 유실 없이 옮기고, 옮긴 뒤 masterplan.md 의 이전 현황을 갱신):
  - docs/news_sort.md 1·2·4·5절
  - docs/data_schema.md 1·5절
  - collect/collect_news*.py
  - collect/config.py

연결 문서:
  - DATA_PIPELINE.md
  - NEWS_CLASSIFICATION.md
  - ../06_technical/DATABASE_SCHEMA.md

작성 규칙: masterplan.md 4절 "문서 작성 규칙"을 따른다.
-->
