# 배포 — Docker 이미지(ghcr.io 비공개) + Render

대시보드를 Docker 이미지로 만들어 GitHub Container Registry(ghcr.io)의 **비공개 패키지**에 올리고, Render 웹 서비스가 그 이미지를 받아 공개 URL로 띄운다. 대시보드는 누구나 볼 수 있고, 이미지와 원천 데이터는 공개하지 않는다.

## 1. 결정 사항

| 항목 | 결정 | 이유·비고 |
|---|---|---|
| 실행 서버 | **Render 웹 서비스, Existing Image 방식** | Render 는 빌드하지 않고 완성된 이미지를 받기만 한다. Render 가 저장소를 직접 빌드하면 비공개 데이터 이미지를 받지 못한다 (9절) |
| 레지스트리 | **ghcr.io 비공개 패키지 2개** | 앱 이미지 `mid_proj_bio`, 데이터 이미지 `mid_proj_bio-data` |
| 빌드 위치 | **로컬 PC 에서 빌드·push (수동)** | GitHub Actions 자동 배포는 데이터 패키지 권한 문제로 실패해 삭제했다 (2026-11-20, 9절) |
| 배포 시점 | 이미지를 push 한 뒤 Render 에서 수동 배포 | Render 는 이미지 기반 서비스를 새 이미지가 올라와도 자동으로 다시 배포하지 않는다 |
| 공시 RAG 색인(`chroma_db/`) | 데이터 이미지에 넣고 앱 이미지 빌드 때 합친다 | Render 서비스는 이미지 하나만 실행하므로 따로 붙일 수 없다 |
| 공개하지 않는 데이터 | 뉴스 원문, DART 공시 원문, 통합 DB, 기사 URL·제목이 든 산출물 | 3절. 이미 커밋된 기록은 프로젝트를 마친 뒤 삭제를 검토한다 |
| Q&A 비용 보호 | OpenAI 배포 전용 프로젝트의 월 사용 한도만 설정 | 코드에는 질문 수 제한을 두지 않는다 |
| Render 인스턴스 | **Standard (2GB) 권장** | Q&A 를 쓰면 약 550MB 가 필요해 512MB(Free·Starter)를 넘는다 (5절) |

## 2. 구성

```
[데이터를 가진 팀원 PC]
   │ ① docker build -f Dockerfile.data → push (데이터가 바뀔 때만)
   ▼
ghcr.io/ai-campus-1st/mid_proj_bio-data   (비공개: DB · 공시 RAG 색인 · 기사 URL·제목이 든 산출물)
   │ ② docker build (Dockerfile 이 COPY --from 으로 합침) → push
   ▼
ghcr.io/ai-campus-1st/mid_proj_bio        (비공개: 코드 + 공개 산출물 + 위 데이터)
   │ ③ Render: Manual Deploy (또는 배포 훅)
   ▼
Render 웹 서비스 (공개 URL) ── 등록한 자격 증명(read:packages)으로 비공개 이미지를 pull
```

## 3. 저장소의 배포 파일

| 파일 | 역할 |
|---|---|
| `Dockerfile` | 앱 이미지. `python:3.12-slim` 에 실행 패키지를 설치하고 코드·테마·공개 산출물을 넣은 뒤, 데이터 이미지(`ARG DATA_IMAGE`, 기본 `ghcr.io/ai-campus-1st/mid_proj_bio-data:latest`)에서 비공개 데이터를 복사한다. 비루트 사용자 `app`(uid 10001)으로 `PORT`(기본 8501)에서 Streamlit 실행, 파일 감시 끔, `/_stcore/health` 헬스체크 |
| `.dockerignore` | 앱 이미지 빌드 맥락의 **허용 목록**. 적힌 파일만 들어가므로 `.env`·원천 데이터·DB·색인·팀원 기록은 들어가지 않는다. 기사 URL·제목이 든 산출물 7개는 저장소가 아니라 데이터 이미지에서 가져오도록 제외 |
| `Dockerfile.data` | 데이터 이미지 (`FROM scratch`, 실행 파일 없음) |
| `Dockerfile.data.dockerignore` | 데이터 이미지 빌드 맥락의 허용 목록 (BuildKit 이 Dockerfile 이름에 맞춰 읽는다) |
| `requirements-app.txt` | 실행 패키지 7개 — streamlit 1.67.0, pandas 3.1.1, numpy 2.5.4, plotly 7.1.0, openai 3.51.0, chromadb 1.5.9, langchain-core 1.8.3 (`requirements.txt` 와 같은 버전) |

## 4. 이미지에 들어가는 파일

### 4-1. 앱 이미지 `ghcr.io/ai-campus-1st/mid_proj_bio`

| 경로 (`/app/`) | 출처 |
|---|---|
| `dashboard/` (app.py, core/, views/) | 저장소 |
| `rag/build_index.py`, `rag/qa.py` | 저장소 |
| `collect/config.py` | 저장소 (기업·기간 설정) |
| `.streamlit/config.toml` | 저장소 (테마) |
| `requirements-app.txt` | 저장소 |
| `data/processed/` 공개 파일 12개 — `company_screening.csv`, `company_weighted_score.csv`, `contract_amounts.csv`, `dart_disclosures_weighted.csv`, `eda_company_monthly.csv`, `eda_disclosure_class.csv`, `eda_disclosure_quarterly.csv`, `eda_keyword_monthly.csv`, `eda_news_monthly.csv`, `eda_news_scope.csv`, `eda_weekly.csv`, `issue_groups.csv` | 저장소 |
| `data/db/bio_cdmo.sqlite`, `data/processed/` 비공개 파일 7개, `chroma_db/` | 데이터 이미지 |

### 4-2. 데이터 이미지 `ghcr.io/ai-campus-1st/mid_proj_bio-data`

| 경로 | 만드는 방법 |
|---|---|
| `/data/db/bio_cdmo.sqlite` | `python db/build_db.py` |
| `/data/processed/eda_spikes.csv`, `issues_llm.csv`, `modality_llm.csv`, `news_disclosure_links.csv`, `sentiment_llm.csv`, `summary_cards.json`, `title_ko.csv` | `analysis/` 의 각 스크립트 |
| `/chroma_db/` | `python rag/build_index.py` |

### 4-3. 확인 결과 (2026-11-19, 로컬 Docker 29.9.3)

| 항목 | 결과 |
|---|---|
| 크기 | 앱 이미지 압축 약 733MB (디스크 2.76GB: 패키지 977MB, 색인 692MB, 데이터 116MB), 데이터 이미지 압축 약 418MB |
| 앱 빌드 맥락 | 1.12MB — 허용 목록만 전송됨 |
| 유출 점검 | `.env*`, `*.jsonl`, `corpCode.xml`, 뉴스 CSV 폴더, `secrets.toml`, 팀원 기록 파일이 이미지 안에 없음 |
| 실행 | `PORT=10000` 으로 `/_stcore/health` → `ok`, 7개 화면 오류 0건, 컨테이너 안 통합 점검(`tests/check_dashboard_filters.py`) 119회 실행·오류 0건 |
| 공개 여부 | 두 패키지 모두 로그인 없이 받을 수 없음 (익명 토큰 요청 401) |

## 5. 처음 한 번 설정

### 5-1. GitHub 토큰

GitHub → Settings → Developer settings → Personal access tokens → **Tokens (classic)** 에서 만든다 (ghcr 는 classic 토큰만 지원).

| 용도 | 권한 | 쓰는 곳 |
|---|---|---|
| 이미지 push | `write:packages` | 빌드하는 팀원 PC 의 `docker login` |
| Render 의 이미지 pull | `read:packages` 만 | Render Registry Credential. 만든 사람 계정에 묶이므로 만료일과 관리 담당자를 정한다 |

### 5-2. ghcr 패키지

첫 push 뒤 github.com/orgs/AI-Campus-1st/packages 에서 `mid_proj_bio-data`, `mid_proj_bio` 의 Package settings → Visibility 가 **Private** 인지 확인한다. 패키지를 만들 권한이 없으면 조직 관리자에게 요청한다.

### 5-3. OpenAI

대시보드는 누구나 쓸 수 있어 S6 질문 수만큼 비용이 난다 (질문 한 번에 1센트 미만). OpenAI 플랫폼에서 **배포 전용 프로젝트**를 만들어 월 사용 한도를 걸고, 그 프로젝트에서 키를 발급한다.

### 5-4. Render

1. (선택) New → **Project** 로 프로젝트를 만들고 첫 환경을 `Production` 으로 둔다.
2. Workspace Settings → **Container Registry Credentials** 에 추가한다 — Registry: GitHub Container Registry, Username: GitHub 닉네임, Personal Access Token: 5-1 의 `read:packages` 토큰.
3. **+ New → Web Service → Source Code: Existing Image** 를 고른다 (Git 저장소를 고르지 않는다).
4. Image URL `ghcr.io/ai-campus-1st/mid_proj_bio:latest`, Credential 은 2 에서 만든 것 → **Connect**.
5. 설정

| 항목 | 값 |
|---|---|
| Project / Environment | 1 의 프로젝트 / `Production` |
| Region | Singapore (한국에서 가장 가까움) |
| Instance Type | Standard (2GB). 로컬 측정 — 7개 화면을 연 뒤 약 200MB, 공시 색인 검색 최대 약 345MB, Q&A 사용 시 약 550MB |
| Environment Variables | `OPENAI_API_KEY` = 5-3 의 키. 없으면 S6 만 "설정 확인" 안내를 띄운다 |
| Health Check Path | `/_stcore/health` |
| Docker Command | 비워 둔다 (이미지의 실행 명령이 Render 의 `PORT` 를 그대로 쓴다) |

6. **Deploy** 를 누르면 첫 배포가 시작된다. Logs 에 `Uvicorn server started on 0.0.0.0:10000` 이 나오면 서버가 뜬 것이다.
7. (선택) 팀원은 Workspace Settings 에서 초대한다. 프로젝트 환경의 ••• → All settings → Permissions → **Protected** 로 두면 Admin 만 환경변수(OpenAI 키)를 보거나 바꿀 수 있다.

## 6. 빌드·배포 방법

저장소 루트에서 실행한다. 이 PC(Windows, amd64)는 그대로 빌드하면 된다. **Apple Silicon Mac** 은 Render(`linux/amd64`)에서 실행되지 않는 이미지가 만들어지므로 `docker buildx build --platform linux/amd64 ... --push .` 로 빌드와 push 를 한 번에 한다.

### 6-1. 준비

Docker Desktop 을 실행하고 ghcr 에 로그인한다. 비밀번호 자리에 5-1 의 `write:packages` 토큰을 붙여 넣는다.

```bash
docker login ghcr.io -u <GitHub 닉네임>
```

로컬 빌드는 **커밋 여부와 관계없이 작업 폴더의 파일**을 넣는다. main 을 최신으로 받고 변경이 없는지 확인한다.

```bash
git pull
```

```bash
git status
```

### 6-2. 데이터 이미지 (DB · 색인 · 비공개 산출물이 바뀌었을 때만)

`data/db/bio_cdmo.sqlite`, `chroma_db/`, 4-2 의 산출물 7개가 로컬에 있어야 한다. 날짜 태그는 올리는 날로 바꾼다 (되돌릴 때 쓴다).

```bash
docker build -f Dockerfile.data -t ghcr.io/ai-campus-1st/mid_proj_bio-data:latest -t ghcr.io/ai-campus-1st/mid_proj_bio-data:2026-11-20 .
```

```bash
docker push --all-tags ghcr.io/ai-campus-1st/mid_proj_bio-data
```

데이터 이미지를 올렸으면 앱 이미지도 다시 빌드해야 새 데이터가 반영된다.

### 6-3. 앱 이미지 빌드

`latest` 와 커밋 해시 태그(`sha-<커밋>`)를 함께 붙인다. 빌드할 때 ghcr 의 `mid_proj_bio-data:latest` 를 받으므로 6-1 로그인이 필요하다.

```bash
docker build -t ghcr.io/ai-campus-1st/mid_proj_bio:latest -t ghcr.io/ai-campus-1st/mid_proj_bio:sha-$(git rev-parse --short HEAD) .
```

ghcr 에 올리지 않은 로컬 데이터 이미지로 빌드하려면 `--build-arg` 로 지정한다.

```bash
docker build --build-arg DATA_IMAGE=mid_proj_bio-data:local -t ghcr.io/ai-campus-1st/mid_proj_bio:latest .
```

### 6-4. 로컬 확인

http://localhost:8501 에서 7개 화면이 뜨는지 본다. `--env-file` 은 실행할 때만 쓰이고 이미지에 남지 않는다. 메모리는 다른 터미널에서 `docker stats` 로 본다.

```bash
docker run --rm -p 8501:8501 --env-file .env ghcr.io/ai-campus-1st/mid_proj_bio:latest
```

### 6-5. 앱 이미지 push

처음에는 약 730MB 를 올리고, 이후에는 바뀐 층만 올라간다 (코드만 바뀌면 수 MB).

```bash
docker push --all-tags ghcr.io/ai-campus-1st/mid_proj_bio
```

### 6-6. Render 배포

Render 는 새 이미지를 올려도 스스로 배포하지 않는다. 둘 중 하나로 배포를 요청한다.

- **대시보드에서**: 서비스 → **Manual Deploy → Deploy latest reference** (`latest` 태그가 가리키는 이미지를 받는다)
- **배포 훅으로**: 서비스 Settings → Deploy Hook 의 URL 로 요청한다. 훅 URL 은 비밀값이니 문서·기록·채팅에 남기지 않는다. 아래는 방금 push 한 이미지를 digest 로 고정해 배포하는 예로, Git Bash 에서 실행한다 (Windows PowerShell 5.1 의 `curl` 은 다른 명령의 별칭이라 동작하지 않는다)

```bash
curl -fsS -G "<Deploy Hook URL>" --data-urlencode "imgURL=$(docker inspect --format '{{index .RepoDigests 0}}' ghcr.io/ai-campus-1st/mid_proj_bio:latest)"
```

배포 뒤 서비스 주소에서 7개 화면과 S6 질문 하나를 확인한다.

### 6-7. 되돌리기

Render 서비스 Settings 에서 이미지 태그를 이전 `sha-<커밋>` 으로 바꾸고 Manual Deploy 한다. 데이터를 되돌릴 때는 이전 날짜 태그의 데이터 이미지를 `--build-arg DATA_IMAGE=ghcr.io/ai-campus-1st/mid_proj_bio-data:<날짜>` 로 지정해 앱 이미지를 다시 빌드·push 한다.

## 7. 공개하지 않는 데이터

| 분류 | 경로 | 이미지 |
|---|---|---|
| 뉴스 원문 | `02_BIO_news_3y/`, `03_CDMO_news_3y/`, `data/raw/cdmo_*.csv`, `data/raw/news*/` | 어느 이미지에도 넣지 않음 |
| DART 공시 원문 | `data/raw/dart/` | 어느 이미지에도 넣지 않음 |
| 통합 DB · 색인 | `data/db/bio_cdmo.sqlite`, `chroma_db/` | 데이터 이미지 |
| 기사 URL·제목이 든 산출물 | `data/processed/` 의 `eda_spikes.csv`, `issues_llm.csv`, `modality_llm.csv`, `news_disclosure_links.csv`, `sentiment_llm.csv`, `summary_cards.json`, `title_ko.csv` | 데이터 이미지 |

나머지 `data/processed/` 파일(집계표, 기업 점수, 공시 분류, 계약 금액, 이슈 묶음)은 기사 URL·제목이 없어 저장소와 앱 이미지에 둔다.

> 원천 데이터와 위 산출물은 **아직 git 에서 빼지 않았다** (팀 공지 후 진행 — 10절). 이미 커밋된 기록은 프로젝트를 마친 뒤 삭제를 검토한다.

## 8. 실행 환경 정리

| 항목 | 값 |
|---|---|
| 포트 | Render 가 넘기는 `PORT` (Render 기본 10000), 로컬 기본 8501 |
| 비밀 정보 | `OPENAI_API_KEY` 만 필요 — Render 환경변수로 넣는다. 이미지에는 넣지 않는다 |
| 쓰기 권한 | `chroma_db/` 는 `app` 사용자 소유 (chromadb 가 열 때 `chroma.sqlite3` 를 고쳐 쓴다). DB 는 읽기 전용으로 연다 |
| 헬스체크 | `/_stcore/health` (Docker HEALTHCHECK 와 Render Health Check Path) |

## 9. 문제 해결 (겪은 오류)

| 증상 | 원인 | 해결 |
|---|---|---|
| Render 빌드 중 `failed to fetch anonymous token ... mid_proj_bio-data ... 401 Unauthorized` (2026-11-19) | 서비스를 Git 저장소로 만들어 Render 가 Dockerfile 을 직접 빌드했고, Render 빌드 서버에는 ghcr 로그인 정보가 없다 | 서비스를 **Existing Image** 로 다시 만든다 (5-4) |
| 로컬 빌드 중 같은 401 | `docker login ghcr.io` 를 하지 않았거나, 로그인한 곳과 다른 환경(WSL·다른 PC)에서 빌드 | 빌드하는 환경에서 6-1 로그인 |
| GitHub Actions `HEAD .../mid_proj_bio-data/manifests/latest: 403 Forbidden` (2026-11-19, main 병합 직후) | 데이터 패키지의 Manage Actions access 에 저장소가 없어 Actions 토큰이 비공개 패키지를 읽지 못함 | 워크플로(`.github/workflows/deploy.yml`)를 삭제하고 로컬 빌드로 일원화 (2026-11-20). 다시 자동화하려면 데이터 패키지에 저장소 Read 권한을 주고 워크플로를 되살린다 (`git show feec338:.github/workflows/deploy.yml`) |
| Render 에서 메모리 부족으로 재시작 | 512MB 인스턴스에서 Q&A 를 쓰면 약 550MB 필요 | Standard (2GB) 로 올린다 |

## 10. 남은 일

1. **원천 데이터 git 제외 (팀 공지 후)** — 팀원의 수집·분석·DB 구축이 커밋된 데이터를 전제로 하므로, 공지하고 데이터를 받을 경로를 정한 뒤 실행한다. 로컬 파일은 지워지지 않는다. 같은 커밋에서 `.gitignore` 에 같은 경로를 추가한다.

```bash
git rm -r --cached 02_BIO_news_3y 03_CDMO_news_3y data/raw data/processed/eda_spikes.csv data/processed/issues_llm.csv data/processed/modality_llm.csv data/processed/news_disclosure_links.csv data/processed/sentiment_llm.csv data/processed/summary_cards.json data/processed/title_ko.csv
```

2. **문서 갱신 (배포 확인 후)** — README 에 배포 URL, `SYSTEM_ARCHITECTURE.md` 6절 "배포 미검토"를 이 문서 기준으로 고친다.
