# 배포 — Docker 이미지(ghcr.io 비공개) + Render

대시보드를 Docker 이미지로 만들어 GitHub Container Registry(ghcr.io)의 **비공개 패키지**에 올리고, Render 웹 서비스로 공개 URL에 띄운다. 대시보드는 누구나 볼 수 있고, 이미지와 원천 데이터는 공개하지 않는다.

## 1. 구성

```
[데이터를 가진 팀원 PC] ── docker push (수동, 데이터가 바뀔 때) ──▶ ghcr.io/ai-campus-1st/mid_proj_bio-data  (비공개)
                                                                     │  DB · 공시 RAG 색인 · 기사 URL·제목이 든 산출물
[main 에 push] ─▶ GitHub Actions (.github/workflows/deploy.yml) ◀─────┘  COPY --from 으로 합침
                    │ 빌드 · push
                    ▼
                 ghcr.io/ai-campus-1st/mid_proj_bio  (비공개, 앱 + 데이터)
                    │ Render 배포 훅 (digest 고정)
                    ▼
                 Render 웹 서비스 (공개 URL) ── 등록한 자격 증명으로 비공개 이미지를 pull
```

| 파일 | 역할 |
|---|---|
| `Dockerfile` | 앱 이미지. 코드와 공개 산출물은 저장소에서, 비공개 데이터는 데이터 이미지에서 가져온다 |
| `.dockerignore` | 앱 이미지 빌드 맥락의 **허용 목록**. `.env`·원천 데이터·DB·색인은 들어가지 않는다 |
| `Dockerfile.data` | 데이터 이미지 (`FROM scratch`, 실행 파일 없음) |
| `Dockerfile.data.dockerignore` | 데이터 이미지 빌드 맥락의 허용 목록 |
| `requirements-app.txt` | 실행에 필요한 패키지만 (streamlit, pandas, numpy, plotly, openai, chromadb, langchain-core) |
| `.github/workflows/deploy.yml` | main push → 앱 이미지 빌드·push → Render 배포 훅 |

## 2. 공개하지 않는 데이터

| 분류 | 경로 | 이미지 |
|---|---|---|
| 뉴스 원문 | `02_BIO_news_3y/`, `03_CDMO_news_3y/`, `data/raw/cdmo_*.csv`, `data/raw/news*/` | 어느 이미지에도 넣지 않음 |
| DART 공시 원문 | `data/raw/dart/` | 어느 이미지에도 넣지 않음 |
| 통합 DB · 색인 | `data/db/bio_cdmo.sqlite`, `chroma_db/` | 데이터 이미지 |
| 기사 URL·제목이 든 산출물 | `data/processed/` 의 `eda_spikes.csv`, `issues_llm.csv`, `modality_llm.csv`, `news_disclosure_links.csv`, `sentiment_llm.csv`, `summary_cards.json`, `title_ko.csv` | 데이터 이미지 |

나머지 `data/processed/` 파일(집계표, 기업 점수, 공시 분류, 계약 금액, 이슈 묶음)은 기사 URL·제목이 없어 저장소에 둔다.

> 원천 데이터와 위 산출물은 **아직 git 에서 빼지 않았다** (팀 공지 후 진행 — 7절). 이미 커밋된 기록은 프로젝트를 마친 뒤 삭제를 검토한다.

## 3. 처음 한 번 설정

### 3-1. GitHub

1. **토큰** — 데이터 이미지를 올릴 팀원과 Render 용으로 classic PAT 를 만든다 (ghcr 는 fine-grained 토큰을 지원하지 않는다).
   - 데이터 이미지 push 용: `write:packages`
   - Render pull 용: `read:packages` 만 (별도 토큰 권장. 만든 사람 계정에 묶이므로 관리 담당자를 정한다)
2. **데이터 이미지 첫 push** — 4절 순서대로 올린다.
3. **패키지 공개 여부 확인** — 조직 > Packages 에서 `mid_proj_bio-data` 의 Visibility 가 **Private** 인지 확인한다. 앱 이미지 `mid_proj_bio` 도 첫 배포 후 같은 방식으로 확인한다.
4. **Actions 접근 허용** — `mid_proj_bio-data` 패키지 설정 > Manage Actions access 에 `mid_proj_bio` 저장소를 **Read** 로 추가한다. 없으면 CI 가 데이터 이미지를 받지 못한다.
5. 조직 설정에서 Actions 의 패키지 쓰기가 막혀 있으면 조직 관리자가 허용해야 한다.

### 3-2. Render

1. Workspace Settings > Registry Credentials 에 GitHub 자격 증명을 추가한다 (사용자 이름 + `read:packages` 토큰).
2. New > Web Service > Existing Image 에 `ghcr.io/ai-campus-1st/mid_proj_bio:latest` 와 위 자격 증명을 넣는다.
3. 설정
   - Region: Singapore (한국에서 가장 가까움)
   - Instance: **Standard (2GB) 권장**. 로컬 측정(2026-11-19, `docker stats`) — 7개 화면을 모두 연 뒤 약 200MB, 공시 색인을 열어 검색하는 프로세스의 최대 메모리 약 345MB. Q&A 를 쓰면 합쳐서 약 550MB 로 512MB(Free·Starter)를 넘는다. Free 는 쉬면 꺼지고, 깨어날 때 이미지(압축 약 730MB)를 받아 첫 접속이 느리다
   - Environment: `OPENAI_API_KEY` (S6 공시 Q&A). 없으면 S6 만 "설정 확인" 안내를 띄운다
   - Health Check Path: `/_stcore/health`
   - 포트는 Render 가 넘기는 `PORT` 를 이미지가 그대로 쓴다 (따로 설정하지 않는다)
4. Settings > Deploy Hook 의 URL 을 GitHub 저장소 Settings > Secrets and variables > Actions 에 `RENDER_DEPLOY_HOOK` 으로 넣는다. 이 값이 없으면 CI 는 이미지만 올리고 배포는 건너뛴다.

### 3-3. OpenAI 사용 한도

대시보드는 누구나 쓸 수 있어 S6 질문 수만큼 비용이 난다. 배포용 키는 OpenAI 플랫폼에서 **배포 전용 프로젝트**를 만들어 발급하고, 그 프로젝트에 월 사용 한도를 걸어 둔다 (질문 한 번에 1센트 미만, README "실행 — 대시보드").

## 4. 데이터 이미지 올리기 (데이터가 바뀔 때)

DB(`python db/build_db.py`), 색인(`python rag/build_index.py`), 2절의 산출물 중 하나라도 바뀌면 다시 올린다. 저장소 루트에서 실행한다.

```bash
docker login ghcr.io -u <GitHub 닉네임>
```

```bash
docker build -f Dockerfile.data -t ghcr.io/ai-campus-1st/mid_proj_bio-data:latest -t ghcr.io/ai-campus-1st/mid_proj_bio-data:2026-11-19 .
```

```bash
docker push --all-tags ghcr.io/ai-campus-1st/mid_proj_bio-data
```

태그의 날짜는 올리는 날로 바꾼다. 올린 뒤 GitHub 저장소 Actions > Build and deploy > Run workflow 로 앱을 다시 배포한다 (코드 변경이 없어도 새 데이터가 반영된다).

## 5. 앱 배포 (자동)

main 에 push 하면 `.github/workflows/deploy.yml` 이 실행된다.

1. ghcr 로그인 (`GITHUB_TOKEN`)
2. 앱 이미지 빌드 — 데이터 이미지(`mid_proj_bio-data:latest`)를 합침
3. `ghcr.io/ai-campus-1st/mid_proj_bio` 에 `latest`, `sha-<커밋>` 태그로 push
4. Render 배포 훅 호출 — 방금 올린 이미지의 digest 를 `imgURL` 로 넘겨 그 이미지를 배포

되돌리기: Render 서비스의 이미지 태그를 이전 `sha-<커밋>` 으로 바꿔 배포하거나, Actions 에서 이전 커밋으로 다시 실행한다.

## 6. 로컬에서 이미지 확인

데이터 이미지를 받을 수 있는 상태(`docker login ghcr.io`)에서 실행한다.

```bash
docker build -t mid_proj_bio:local .
```

```bash
docker run --rm -p 8501:8501 --env-file .env mid_proj_bio:local
```

http://localhost:8501 에서 7개 화면이 뜨는지 본다. 메모리 사용량은 다른 터미널에서 `docker stats` 로 본다. 데이터 이미지를 아직 올리지 않았다면 로컬에서 만든 데이터 이미지를 쓴다.

```bash
docker build -f Dockerfile.data -t mid_proj_bio-data:local .
```

```bash
docker build --build-arg DATA_IMAGE=mid_proj_bio-data:local -t mid_proj_bio:local .
```

## 7. 남은 일 — 원천 데이터를 git 에서 빼기 (팀 공지 후)

팀원의 수집·분석·DB 구축이 커밋된 데이터를 전제로 하므로, 공지하고 데이터를 받을 경로를 정한 뒤 실행한다. 로컬 파일은 지워지지 않는다.

```bash
git rm -r --cached 02_BIO_news_3y 03_CDMO_news_3y data/raw data/processed/eda_spikes.csv data/processed/issues_llm.csv data/processed/modality_llm.csv data/processed/news_disclosure_links.csv data/processed/sentiment_llm.csv data/processed/summary_cards.json data/processed/title_ko.csv
```

같은 커밋에서 `.gitignore` 에 위 경로를 추가한다. 이후 이 파일들은 데이터 이미지와 별도 공유 경로로만 주고받는다.
