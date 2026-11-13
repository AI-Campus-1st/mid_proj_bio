# 바이오 CDMO 산업 이슈 대시보드 (중간프로젝트)

뉴스와 DART 공시로 바이오 CDMO 5개사(삼성바이오로직스, SK바이오사이언스, 프레스티지바이오로직스, 에스티팜, 바이넥스)의 이슈를 분석한다.

- 과제 안내: `중간프로젝트_가이드_뉴스공시_산업이슈_대시보드.md`
- 기업 선정 근거: `docs/기업선정_근거.md`
- 데이터 구조: `docs/데이터_스키마.md`

## 디렉터리

| 경로 | 내용 |
|---|---|
| `02_BIO_news_3y/` | 제공 뉴스 CSV (2023-10-19 ~ 2026-10-19) |
| `collect/` | 수집 계층 — DART 공시, 추가 뉴스. 응답 원본을 `data/raw/` 에 저장 |
| `db/` | 적재 계층 — 통합 스키마(`schema.sql`)와 DB 구축(`build_db.py`) |
| `analysis/` | 분석 계층 — 기업 선정용 공시 가중 점수 |
| `data/raw/` | 수집 원본 (JSON, JSONL, zip) |
| `data/db/` | 통합 DB `bio_cdmo.sqlite` (git 제외, 아래 순서로 재생성) |
| `docs/` | 선정 근거, 스키마 문서 |

## 준비

- Python 3.10 이상. 수집·적재는 표준 라이브러리만 사용한다.
- 프로젝트 루트의 `.env` 에 DART 인증키를 둔다. (`.gitignore` 등록됨)

```
DART_OPEN_API=발급받은_키
```

## 실행 순서 — 통합 DB 구축

모든 수집 스크립트는 받은 파일을 건너뛰므로 중간에 끊겨도 다시 실행하면 이어서 받는다.

1. 기업 코드와 후보 14개사 공시 목록 (기업 선정 단계에서 실행, `companies.json` 생성)

```bash
python collect/collect_dart_list.py
```

2. 5개사 기업명 뉴스 (구글 뉴스 RSS)

```bash
python collect/collect_news.py company
```

```bash
python collect/collect_news_selected.py
```

3. 5개사 공시 목록과 원문 (제공 뉴스와 같은 기간)

```bash
python collect/collect_dart_selected.py
```

4. 통합 DB 생성

```bash
python db/build_db.py
```

기간은 `collect/config.py` 의 `DB_START`, `DB_END` 로 정한다. 값을 바꾸면 `data/raw/dart/list_selected/` 를 비우고 3번부터 다시 실행한다.

## 기업 선정 근거 재현

`docs/기업선정_근거.md` 7절 참고.
