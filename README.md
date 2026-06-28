# 카페 VoC — 가장 급한 불만 한 화면

여러 경로(앱리뷰·설문·전화메모·인스타DM)로 뒤섞여 들어온 카페 고객 피드백을
**정리 → 분류 → 한 화면**으로 만들어, 사장님이 *"지금 가장 급한 불만"* 을 한눈에 보게 하는 도구.

**🔗 라이브 데모**: https://fourth-app-tlxbic3f5zw7x8ewjlxbnp.streamlit.app/

> Day 3 과제. 상세 설계는 [PRD.md](PRD.md), 제출물은 [SUBMISSION.md](SUBMISSION.md), 작업·판단 기록은 [Worklog.md](Worklog.md).

---

## 빠른 시작

```bash
# 0) 의존성 (최초 1회)
py -m pip install -r requirements.txt

# 1) 데이터 파이프라인 한 번에 (정리 → 분류 → 검증)
py src/run_pipeline.py

# 2) 대시보드 실행
streamlit run app.py        # 브라우저에서 http://localhost:8501
```

> Windows 기준 `py`, macOS/Linux는 `python3`로 바꿔 실행.

## 배포 (선택) — 데이터 없는 사람도 URL만으로 보기

대시보드는 정적 CSV를 읽기만 하므로, CSV를 함께 커밋해 배포하면 방문자는 설치·실행 없이 그대로 본다.

1. push 전 로컬에서 `py src/run_pipeline.py` 1회 → `data/feedback_classified.csv` 최신화
2. 이 폴더를 GitHub 레포에 push (**`data/`의 CSV 포함**, `resolved.json`·캐시는 `.gitignore`로 제외)
3. Streamlit Cloud에서 레포 연결 → 메인 파일 `app.py` 지정 → Deploy

> 주의: 처리완료(`resolved.json`)는 서버 인스턴스 임시 저장이라 방문자 간 공유·영속되지 않는다(재배포 시 초기화). 공개 데이터의 민감정보(전화메모 등 PII)는 사전 점검.

## 로컬 운영 (매장 관리자용) — 권장

실매장 관리자는 공개 배포보다 **로컬 실행**이 적합하다: 처리상태가 디스크에 **영구 저장**(휘발 X), 단일 사용자라 충돌 없음, 데이터(PII)가 외부에 노출되지 않음.

- **`run.bat`** (더블클릭): 데이터 재생성·검증 후 대시보드를 띄우고 브라우저를 연다. 터미널 불필요.
- **`ingest.bat`**: 새 피드백 CSV를 창에 끌어다 놓거나 경로를 입력하면 `feedback_raw.csv`에 append + 중복 제거.
- **백업**: 데이터가 파일(CSV + `resolved.json`)이라 **폴더 복사**나 로컬 git 커밋으로 끝.
- **새 피드백 분류**: `ingest` 후 분류가 필요한 행은 분류 Skill(Claude)로 `classifications.csv`를 채운 뒤 `run.bat` 재실행. (보기·처리완료는 관리자 단독 가능)

---

## 데이터 흐름

```
data/feedback_raw.csv                 원본 (id·받은날짜·경로·별점·내용)
        │  ① normalize_dates  날짜 4형식 → YYYY-MM-DD
        ▼
data/feedback_step1_dates.csv
        │  ② classify         data/classifications.csv(분류)를 자연키로 적용 + 긴급도 계산
        ▼
data/feedback_classified.csv          대시보드 입력
        │  ③ verify           독립 로직으로 회귀 검증(게이트)
        ▼
app.py (Streamlit)                    유형 지표 · 급한 불만 TOP3 · 전체 표
```

`run_pipeline.py`가 ①→②→③을 순서대로 실행하고, 단계 실패 시 *어느 단계·왜* 를 알리고 중단한다.

**누가 판단하고, 누가 실행하나** — 헷갈리기 쉬운 부분:

| | 하는 일 | 누가 |
|---|---|---|
| 분류 *판단* (이 글이 불만인가·어느 영역인가) | 유형·감정·실패차원 결정 | **Claude** (언어 이해가 필요 → 코드가 못 함) |
| 그 외 *실행* | 날짜 변환 · 분류 적용 · 긴급도 계산 · 검증 | **파이썬(코드)** |

> 현재 22행의 분류 판단은 이미 `data/classifications.csv`에 들어 있어, `run_pipeline.py` 한 번이면 세 단계가 **전부 코드로 자동 실행**된다(실행 중 Claude 호출 없음). 파이썬은 분류를 *다시 판단하지 않고* 자연키로 매칭해 가져다 쓸 뿐이다.

---

## '가장 급한 불만'은 어떻게 정하나 (한 줄)

> **긴급도 = 심각도(S) × 불만강도(I)**, **I = max(별점신호, 텍스트신호)**

- **S(심각도)**: 어떤 서비스가 깨졌나. SERVQUAL 차원 중요도(신뢰성 최우선) 근거 — 신뢰성4·응답성3·유형성2·제품기호1.
- **I(불만강도)**: 별점신호(1→3,2→2,3→1,4·5→0)와 텍스트신호(환불·결제·오류·반복 키워드/강한부정→3, 부정2, 중립1, 긍정0) 중 **더 위험한 쪽**. 별점이 없어도 텍스트로 채워져 채널 편향이 없다.
- **불만 유형만** 점수화. 동점은 금전 손실·환불 우선 → 최근순.
- 가중치·키워드는 `src/classify.py` 상단 상수로 분리해 조정 가능.

근거: SERVQUAL(Parasuraman·Zeithaml·Berry 1988), 결측 임퓨테이션 위험(Chakraborty·Kim·Sudhir 2022, *JMR*), CS·VoC 실무(Zendesk·IrisAgent·edesk).

---

## 폴더 구조

```
Prac_01/
├─ app.py                     ③ 한 화면 (Streamlit)
├─ run.bat · ingest.bat       관리자용 실행기(더블클릭)
├─ requirements.txt
├─ README.md · PRD.md · SUBMISSION.md · Worklog.md
├─ src/
│  ├─ run_pipeline.py         원클릭: ①→②→③
│  ├─ ingest.py               지속 유입: 새 CSV append + 자연키 dedup(멱등)
│  ├─ normalize_dates.py      ① 날짜 통일
│  ├─ classify.py             ② 분류 적용(classifications.csv) + 긴급도 계산
│  ├─ validate.py             입력 검증·자연키 (파일·컬럼·별점범위·분류누락)
│  └─ verify.py               회귀 검증 안전망 (독립 재계산)
├─ .claude/skills/feedback-classify/SKILL.md   분류 Skill(판단 기준·Few-shot·출력 규약)
└─ data/
   ├─ feedback_raw.csv
   ├─ feedback_step1_dates.csv
   ├─ classifications.csv       분류 데이터(Claude/Skill 산출) — 자연키로 병합
   ├─ feedback_classified.csv
   └─ resolved.json             처리완료 상태(워크큐, 런타임 생성)
```

---

## 검증

```bash
py src/verify.py     # 무결성·날짜·긴급도·분류값·TOP3 독립 재계산. PASS면 exit 0
```

코드를 바꾼 뒤 `run_pipeline.py`(끝에 verify 포함) 또는 `verify.py`를 돌리면 회귀(깨짐)를 즉시 감지한다.

---

## 새 데이터가 들어오면

분류는 '내용' 텍스트만 보고 하며 **날짜와 무관**하다(날짜 변환이 분류의 선행조건이 아님). 새 피드백이 별도 CSV로 들어오면 **3단계** — 코드 수정 없음:

```
0) [명령]  py src/ingest.py <새_피드백.csv>
        └ feedback_raw.csv에 append + 자연키 dedup(멱등) + '분류 필요' 행 안내
1) [Claude가 1회]  안내된 새 줄을 분류 → data/classifications.csv 에 추가 (분류 Skill)
2) [명령]  py src/run_pipeline.py
        └ ① 날짜 변환 → ② 분류 적용 + 긴급도 → ③ 검증 → 대시보드 입력 완성
```

> 이미 분류된 줄만 있으면 0·2단계만으로 끝난다. `ingest`는 같은 파일을 다시 넣어도 중복이 안 생긴다(멱등).

- **날짜·긴급도·집계**는 새 행에도 그대로 동작(규칙·산술 기반).
- **분류 판단만 Claude가** 한다. 그 결과는 `data/classifications.csv`에 담기며, 신규 줄이 비면 검증이 *"분류 누락 id"* 로 막아 알려준다.
- **반복은 분류 Skill로** (`.claude/skills/feedback-classify`): 새 줄을 분류해 `data/classifications.csv`에 추가하면 `classify.py`가 자연키로 매칭해 적용한다 — **코드 수정 불필요**.

---

## 만든 것 / 안 만든 것

- **만든 것**: 날짜 통일 · Claude 분류(유형·감정·긴급도) · 급한 불만 TOP3 한 화면 · 검증·파이프라인·입력검증.
- **안 만든 것(덜어내기)**: 경로·날짜별 추세, 워드클라우드, 필터 UI, 런타임 LLM 호출, 로그인 — 사장님 요청("급한 불만 하나")에 집중.
