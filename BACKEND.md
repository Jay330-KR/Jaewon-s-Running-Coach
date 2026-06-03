# Project 330 — 백엔드 구조 문서 (BACKEND.md)

> 이 문서는 **git 저장소에 없는** Supabase 백엔드 구성을 기록한 것입니다.
> (Edge Functions / DB / Cron / Secrets 는 Supabase 프로젝트에만 존재)

마지막 정리: 2026-06 · AI 러닝 코치 (Jack Daniels VDOT 기반)

---

## 1. 전체 아키텍처

```
[Strava] --운동 업로드--> (웹훅) --> [Supabase Edge Functions] --> [Supabase DB(Postgres)]
                                          |  ├ 잭 다니엘스 엔진(VDOT→페이스/워크아웃)
                                          |  └ LLM(Gemini 2.5-flash): 코치 코멘트·평가 한줄
[GitHub Pages 프론트(index.html)] <--fetch(CORS)--> [Edge Functions]
[GitHub Actions] --매일/푸시시--> coach.py 실행 --> index.html 재생성 --> Pages 배포
```

- **프론트**: GitHub Pages — https://jay330-kr.github.io/Jaewon-s-Running-Coach/
  - `index.html` 은 `coach.py` 가 생성(템플릿+데이터). **직접 편집 금지**, `coach.py` 를 고치고 푸시.
  - GitHub Actions(`.github/workflows/coach_sync.yml`)가 push 시 + 주기적으로 `coach.py` 실행 → 배포.
- **백엔드**: Supabase 프로젝트 (ref: `lalqqtpvphijkaliiopl`)
  - 함수 베이스 URL: `https://lalqqtpvphijkaliiopl.supabase.co/functions/v1`
  - 모든 함수 **Verify JWT = OFF** (외부/Strava 호출 허용). DB 접근은 service_role 키(RLS 우회)로만.

---

## 2. DB 테이블 (5개)

| 테이블 | 키 | 주요 컬럼 | 용도 |
|---|---|---|---|
| `settings` | id=1 | vdot, hr_max, hr_rest, phase, constraints | 코칭 기준값 (1행) |
| `training_days` | date | workout_type, target_distance_km, target_pace, target_hr, structure, rationale, coach_comment, vdot_at_time | 그날 추천 워크아웃 |
| `activities` | strava_id | date, type, distance_m, moving_time_s, avg_pace, avg_hr, max_hr, avg_cadence_spm, raw | Strava 활동(러닝+보강) |
| `evaluations` | date | strava_id, achievement_stars(0~3,0.5), breakdown, ai_feedback | 추천 대비 평가 |
| `user_feedback` | date | perceived_intensity, pain_areas[], comment | 사용자 피드백 |
| `weekplan` | date | dow, plan_type, user_set | 주간 러닝 계획(월~일) |

- **RLS: 모든 표 ON** (anon 키로 접근 불가). 백엔드 함수가 service_role 로만 접근.
- `settings` 시드값: VDOT 39, hr_max 183, hr_rest 54, phase 'base'.

---

## 3. Edge Functions (6개)

| 함수 | 메서드 | 역할 |
|---|---|---|
| `strava-webhook` | GET/POST | Strava 구독 검증(GET) + 이벤트 수신(POST) → 활동 적재 → 러닝이면 `evaluate` 자동 호출. (`{"sync":true,"object_id":N}` 디버그 모드 / `?diag=1` 환경점검) |
| `recommend` | POST | `{date?, for?, pt_today?}` → 주간계획·기록·피드백 기반 다니엘스 추천 생성 → `training_days` 저장. 통증 시 휴식 강제. 7월 진입 시 VDOT 재검토 알람. |
| `evaluate` | POST | `{date}` → 추천 대비 실제(러닝/보강) 별점 + Gemini 한줄 평가 → `evaluations` 저장. |
| `day` | GET/POST | `?date=&regen=&pt_today=` → 그날 묶음(추천+활동+평가+피드백). 오늘이면 추천 자동생성, 미평가면 평가 자동생성. (CORS) |
| `feedback` | POST | `{date, perceived_intensity, pain_areas[], comment}` → 저장 → 다음날 추천 자동 생성. (CORS) |
| `weekplan` | GET/POST | `action=get|generate|set`, `date`, `plan_type` → 주간계획 조회/생성/변경. `user_set` 인 날은 재생성 시 보존. (CORS) |

### 워크아웃 타입 (weekplan 드롭다운 / 추천 매핑)
`이지 · 롱런 · 역치 · 인터벌 · 휴식 · 보강 · PT · PT+셰이크아웃 · 보강+셰이크아웃`

### VDOT 페이스 테이블 (recommend 내장, 초/km)
| VDOT | E(이지) | T(역치) |
|---|---|---|
| 38 | 6:00–6:36 | 5:12 |
| 39 | 5:54–6:29 | 5:06 |
| 40 | 5:48–6:22 | 5:00 |
| 42 | 5:36–6:09 | 4:50 |
| 44 | 5:25–5:57 | 4:41 |
(I 페이스 ≈ T − 18초/km)

### 단계(phase) — 날짜 기준 자동
- `base`  ≤ 2026-06-30 (이지+볼륨 위주, 역치 없음)
- `build` 2026-07-01 ~ 08-31 (주1 역치 추가)
- `maintain` 2026-09-01 ~ 12-31 (출산 후 유지)
- `sharpen` ≥ 2027-01-01 (동아마라톤 샤프닝)

---

## 4. Cron (pg_cron + pg_net, 2개)

| 이름 | 스케줄(UTC) | KST | 동작 |
|---|---|---|---|
| `daily-recommend` | `0 20 * * *` | 매일 05:00 | `recommend {for:"today"}` 호출 |
| `monday-weekplan` | `0 0 * * 1` | 월 09:00 | `weekplan {action:"generate"}` 호출 |

확인: `select jobname, schedule from cron.job;`
재등록: `select cron.unschedule('이름');` 후 다시 `cron.schedule(...)`.

---

## 5. Secrets (Supabase Edge Functions → Secrets)

| 이름 | 비고 |
|---|---|
| `STRAVA_CLIENT_ID` | 248357 |
| `STRAVA_CLIENT_SECRET` | Strava 앱 시크릿 |
| `STRAVA_REFRESH_TOKEN` | OAuth refresh token (scope: activity:read_all) |
| `STRAVA_VERIFY_TOKEN` | 웹훅 검증용 (실값은 Supabase Secrets 참고 — 공개 금지) |
| `GEMINI_API_KEY` | Gemini (모델: **gemini-2.5-flash** — 2.0-flash 는 이 키 무료쿼터 0이라 사용불가) |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | 자동 주입(추가 불필요) |

> GitHub Actions Secrets 에도 STRAVA_* / GEMINI_API_KEY 동일하게 등록되어 있어야 매일 빌드가 동작.

---

## 6. Strava 웹훅 구독

- 앱당 1개만 허용. 현재 callback = `https://lalqqtpvphijkaliiopl.supabase.co/functions/v1/strava-webhook`
- 조회: `GET https://www.strava.com/api/v3/push_subscriptions?client_id=..&client_secret=..`
- 생성: `POST .../push_subscriptions` (client_id, client_secret, callback_url, verify_token)
- 삭제: `DELETE .../push_subscriptions/{id}?client_id=..&client_secret=..`

---

## 7. 운영 메모 / 주의

- **수동 즉시 갱신**: GitHub Actions → "Project 330 Sync" → Run workflow (cron 은 GitHub 사정상 지연될 수 있음).
- **Strava fetch 기간**: `coach.py` 는 최근 **120일** 조회 (이전 달이 30일 창에서 밀려 사라지는 문제 방지).
- **프론트엔 Strava 키 노출 안 함** (백엔드가 처리). 과거 노출 키는 revoke·재발급 완료.
- **VDOT 변경**: `update settings set vdot=NN, phase='build' where id=1;` (재배포 불필요, 함수가 즉시 반영). 7월 진입 시 추천 코멘트에 재검토 알람이 뜸.
- **디버그**: `strava-webhook` `?diag=1` (키 존재 확인) / `{"sync":true,"object_id":N}` (동기 적재).
