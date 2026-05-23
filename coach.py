import os
import json
import requests
import urllib.parse
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import google.generativeai as genai

# 1. 타임존 설정 및 환경변수 로드
kst = timezone(timedelta(hours=9))
now_dt = datetime.now(timezone.utc).astimezone(kst)
now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
today_date = now_dt.strftime("%Y-%m-%d")
today_weekday = now_dt.strftime("%A")  # Monday, Tuesday, ...

load_dotenv()

# API Keys
STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
STRAVA_REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# 2. 로컬 캐시 및 입력 데이터 로드 함수들
def load_condition():
    """condition.txt에서 오늘의 피드백 및 몸 상태 정보를 파싱합니다."""
    condition_path = "condition.txt"
    default_condition = {
        "피로도": "하",
        "통증": "없음",
        "기타": "특이사항 없음. 가벼운 조깅 예정."
    }
    if not os.path.exists(condition_path):
        return default_condition

    try:
        with open(condition_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        parsed = {}
        for line in lines:
            if ":" in line:
                k, v = line.split(":", 1)
                parsed[k.strip()] = v.strip()
        
        return {
            "피로도": parsed.get("피로도", "하"),
            "통증": parsed.get("통증", "없음"),
            "기타": parsed.get("기타 메모", parsed.get("기타", "특이사항 없음"))
        }
    except Exception as e:
        print(f"⚠️ [Condition] 로드 중 오류 발생 (기본값 사용): {e}")
        return default_condition

def load_notion_routines():
    """notion_routines.md 파일의 내용을 텍스트로 그대로 읽어옵니다."""
    routines_path = "notion_routines.md"
    if not os.path.exists(routines_path):
        return "사용 가능한 노션 보강운동 루틴 데이터가 없습니다."
    try:
        with open(routines_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"⚠️ [Notion Routines] 로드 중 오류 발생: {e}")
        return "노션 운동 루틴 라이브러리를 불러올 수 없습니다."

# 3. Strava API 통신 & 데이터 수집 (Fallback 포함)
def get_strava_activities():
    """스트라바 API를 통해 최근 30일 간의 러닝 데이터를 가져옵니다 (오프라인/에러 시 Fallback 데모 데이터 사용)."""
    cache_dir = "data"
    cache_path = os.path.join(cache_dir, "strava_cache.json")
    
    # 캐시 폴더 생성
    os.makedirs(cache_dir, exist_ok=True)

    # 1단계: API 연동 정보가 없으면 로컬 캐시 또는 데모 데이터 활용
    if not STRAVA_CLIENT_ID or not STRAVA_CLIENT_SECRET or not STRAVA_REFRESH_TOKEN:
        print("⚠️ [Strava] API 설정 정보(.env)가 부족합니다. Fallback 데모 데이터를 로드합니다.")
        return get_demo_activities()

    # 2단계: Strava OAuth2 토큰 갱신 (Refresh Token 사용)
    print("🔄 [Strava] 토큰 갱신 시도 중...")
    token_url = "https://www.strava.com/oauth/token"
    payload = {
        "client_id": STRAVA_CLIENT_ID,
        "client_secret": STRAVA_CLIENT_SECRET,
        "refresh_token": STRAVA_REFRESH_TOKEN,
        "grant_type": "refresh_token"
    }
    
    try:
        token_res = requests.post(token_url, data=payload)
        if token_res.status_code != 200:
            print(f"❌ [Strava] 토큰 갱신 실패 (HTTP {token_res.status_code}). 캐시 또는 데모 데이터를 사용합니다.")
            return load_cached_activities(cache_path)

        token_data = token_res.json()
        access_token = token_data.get("access_token")
        
        # 3단계: 최근 30일간의 액티비티 목록 조회
        print("📥 [Strava] 최근 30일 활동 데이터 다운로드 중...")
        activities_url = "https://www.strava.com/api/v3/athlete/activities"
        # 30일 전 타임스탬프 계산
        after_timestamp = int((datetime.now() - timedelta(days=30)).timestamp())
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"after": after_timestamp, "per_page": 100}
        
        act_res = requests.get(activities_url, headers=headers, params=params)
        if act_res.status_code != 200:
            print(f"❌ [Strava] 활동 데이터 조회 실패 (HTTP {act_res.status_code}).")
            return load_cached_activities(cache_path)

        all_activities = act_res.json()
        # 'Run' 타입의 러닝 데이터만 필터링
        run_activities = [act for act in all_activities if act.get("type") == "Run"]
        
        # 로컬 캐시에 저장
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(run_activities, f, ensure_ascii=False, indent=2)
        print("💾 [Strava] 최근 러닝 데이터를 성공적으로 동기화하여 캐싱했습니다.")
        return run_activities

    except Exception as e:
        print(f"❌ [Strava] 연동 중 예상치 못한 에러 발생: {str(e)}")
        return load_cached_activities(cache_path)

def load_cached_activities(cache_path):
    """로컬 캐시 파일에서 활동 데이터를 로드합니다."""
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                print("💾 [Strava] 로컬 캐시 파일에서 데이터를 성공적으로 읽었습니다.")
                return json.load(f)
        except:
            pass
    return get_demo_activities()

def get_demo_activities():
    """API 미연동 또는 네트워크 오류 시 사용할 리얼한 5월 데모 러닝 데이터 세트"""
    print("💡 [Strava] 데모 데이터를 빌드합니다.")
    demo = [
        {"start_date_local": "2026-05-01T08:30:00Z", "distance": 8310, "moving_time": 2700, "average_heartrate": 142, "name": "모닝 조깅"},
        {"start_date_local": "2026-05-02T07:15:00Z", "distance": 7000, "moving_time": 2280, "average_heartrate": 138, "name": "회복 런"},
        {"start_date_local": "2026-05-03T06:00:00Z", "distance": 9000, "moving_time": 2950, "average_heartrate": 145, "name": "일요 빌드업"},
        {"start_date_local": "2026-05-04T19:30:00Z", "distance": 5000, "moving_time": 1650, "average_heartrate": 135, "name": "나이트 조깅"},
        {"start_date_local": "2026-05-05T08:00:00Z", "distance": 11420, "moving_time": 3720, "average_heartrate": 148, "name": "어린이날 지속주"},
        {"start_date_local": "2026-05-06T19:40:00Z", "distance": 5080, "moving_time": 1700, "average_heartrate": 137, "name": "가벼운 조깅"},
        {"start_date_local": "2026-05-08T19:00:00Z", "distance": 8740, "moving_time": 2880, "average_heartrate": 143, "name": "지속 조깅"},
        {"start_date_local": "2026-05-10T06:30:00Z", "distance": 12820, "moving_time": 4200, "average_heartrate": 149, "name": "주말 장거리 조깅"},
        {"start_date_local": "2026-05-11T19:30:00Z", "distance": 10630, "moving_time": 3480, "average_heartrate": 146, "name": "월요 빌드업"},
        {"start_date_local": "2026-05-12T20:00:00Z", "distance": 5390, "moving_time": 1820, "average_heartrate": 136, "name": "회복 런"},
        {"start_date_local": "2026-05-14T19:30:00Z", "distance": 8820, "moving_time": 2900, "average_heartrate": 142, "name": "목요 조깅"},
        {"start_date_local": "2026-05-15T19:40:00Z", "distance": 10030, "moving_time": 3280, "average_heartrate": 144, "name": "불금 빌드업"},
        {"start_date_local": "2026-05-17T06:30:00Z", "distance": 12670, "moving_time": 4150, "average_heartrate": 148, "name": "일요 장거리"},
        {"start_date_local": "2026-05-19T20:00:00Z", "distance": 6580, "moving_time": 2180, "average_heartrate": 139, "name": "퇴근길 런"}
    ]
    return demo

# 4. 러닝 통계 분석 & QuickChart API 링크 생성
def calculate_mileage_and_build_charts(activities):
    """활동 데이터를 바탕으로 통계 계산 및 QuickChart 차트 이미지 URL을 빌드합니다."""
    may_activities = []
    weekly_activities = []

    today_weekday_idx = now_dt.weekday()
    start_of_week = (now_dt - timedelta(days=today_weekday_idx)).replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_week = start_of_week + timedelta(days=7)

    may_daily_mileage = [0.0] * 31
    weekly_daily_mileage = [0.0] * 7

    for act in activities:
        date_str = act.get("start_date_local")[:10]
        try:
            act_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            continue
        
        dist_km = round(act.get("distance", 0) / 1000.0, 2)
        
        if act_date.year == 2026 and act_date.month == 5:
            may_activities.append(act)
            day_idx = act_date.day - 1
            if 0 <= day_idx < 31:
                may_daily_mileage[day_idx] += dist_km
        
        act_datetime = datetime.strptime(act.get("start_date_local")[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).astimezone(kst)
        if start_of_week <= act_datetime < end_of_week:
            weekly_activities.append(act)
            w_day_idx = act_datetime.weekday()
            if 0 <= w_day_idx < 7:
                weekly_daily_mileage[w_day_idx] += dist_km

    total_may_mileage = round(sum(may_daily_mileage), 1)
    total_weekly_mileage = round(sum(weekly_daily_mileage), 1)

    today_run = None
    for act in activities:
        if act.get("start_date_local")[:10] == today_date:
            today_run = act
            break

    # QuickChart URL-encoding
    may_chart_payload = {
        "type": "bar",
        "data": {
            "labels": [str(i) for i in range(1, 32)],
            "datasets": [{
                "data": [round(val, 2) for val in may_daily_mileage],
                "backgroundColor": "#FC4C02",
                "borderRadius": 4,
                "datalabels": {"display": False}
            }]
        },
        "options": {
            "title": {"display": False},
            "legend": {"display": False},
            "scales": {
                "yAxes": [{
                    "ticks": {"beginAtZero": True, "max": 18, "stepSize": 6, "fontColor": "#888888"},
                    "gridLines": {"color": "rgba(252, 76, 2, 0.15)", "zeroLineColor": "rgba(252, 76, 2, 0.3)"}
                }],
                "xAxes": [{
                    "ticks": {"fontColor": "#888888", "fontSize": 9},
                    "gridLines": {"display": False}
                }]
            },
            "plugins": {"datalabels": False}
        }
    }
    may_chart_url = f"https://quickchart.io/chart?c={urllib.parse.quote(json.dumps(may_chart_payload))}&format=svg"

    week_chart_payload = {
        "type": "bar",
        "data": {
            "labels": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            "datasets": [{
                "data": [round(val, 2) for val in weekly_daily_mileage],
                "backgroundColor": "#FC4C02",
                "borderRadius": 5,
                "datalabels": {
                    "display": True,
                    "align": "end",
                    "anchor": "end",
                    "color": "#FC4C02",
                    "font": {"weight": "bold", "size": 9}
                }
            }]
        },
        "options": {
            "title": {"display": False},
            "legend": {"display": False},
            "scales": {
                "yAxes": [{
                    "ticks": {"beginAtZero": True, "max": 20, "stepSize": 5, "fontColor": "#888888"},
                    "gridLines": {"color": "rgba(252, 76, 2, 0.2)", "zeroLineColor": "rgba(252, 76, 2, 0.4)"}
                }],
                "xAxes": [{
                    "ticks": {"fontColor": "#888888", "fontSize": 11, "fontStyle": "bold"},
                    "gridLines": {"display": False}
                }]
            },
            "plugins": {"datalabels": False}
        }
    }
    week_chart_url = f"https://quickchart.io/chart?c={urllib.parse.quote(json.dumps(week_chart_payload))}&format=svg"

    return {
        "total_may_mileage": total_may_mileage,
        "total_weekly_mileage": total_weekly_mileage,
        "may_chart_url": may_chart_url,
        "week_chart_url": week_chart_url,
        "today_run": today_run
    }

# 5. Gemini AI 통합 추론 파이프라인
def get_ai_coaching_content(stats, condition, routines):
    """Gemini API를 호출하여 동적인 Week Plan, Next Running, 코칭 코멘트, 오늘의 보강운동 루틴을 큐레이션합니다."""
    today_run = stats["today_run"]
    if today_run:
        dist_km = round(today_run.get("distance", 0) / 1000.0, 2)
        pace_min = int((today_run.get("moving_time", 0) / 60) // dist_km)
        pace_sec = int((today_run.get("moving_time", 0) / 60) % dist_km * 60 / dist_km)
        avg_hr = today_run.get("average_heartrate", "정보 없음")
        run_info_str = f"이름: {today_run.get('name')}, 거리: {dist_km}km, 평균 페이스: {pace_min}분 {pace_sec}초/km, 평균 심박수: {avg_hr}bpm"
    else:
        run_info_str = "오늘 수행한 러닝 기록이 없습니다. (휴식일)"

    prompt = f"""
역할: 전문 마라톤 코치이자 부상 방지 재활 및 임산부/육아 러닝 전문가.
사용자의 배경 정보:
- 러닝 숙련도: 2022년부터 마라톤 풀코스 PR 3시간 46분 24초 보유자. (숙련된 서브 4 러너)
- 미래 목표: 2027년 3월 서울마라톤 풀코스 3시간 30분(Project330) 목표.
- 현실적 제약 및 특별 상황: 2026년 9월 출산 예정. 이후 육아 동반 예정으로, 강도 높은 하드 트레이닝보다는 "부상 없이 여름철을 나며 보강운동을 병행하고 장거리를 소화할 수 있는 튼튼한 하체와 코어 몸 만들기"가 핵심 목표.
- 현재 날짜: {today_date} (요일: {today_weekday})

투입 데이터:
1. 최근 30일 스트라바 러닝 통계:
   - 5월 누적 마일리지: {stats["total_may_mileage"]} km (목표: 200 km)
   - 이번 주 누적 마일리지: {stats["total_weekly_mileage"]} km (목표: 50 km)
   - 오늘 수행한 러닝 실적: {run_info_str}
2. 사용자 몸 상태 및 컨디션 (condition.txt):
   - 피로도: {condition["피로도"]}
   - 통증 여부: {condition["통증"]}
   - 특이사항 및 메모: {condition["기타"]}
3. 사용자의 노션 보강운동 데이터베이스 (notion_routines.md):
{routines}

위 변수들을 고도로 분석하여, 아래 출력 형식을 마크다운이나 다른 기호 없이 오직 **순수한 JSON 형식**으로 응답해 주세요. JSON의 키(Key) 명칭은 정확히 지켜야 하며, 백틱(```)이나 json 마크다운 표시를 절대로 붙이지 말고 중괄호 `{{` 로 시작해서 `}}` 로 끝나는 순수한 문자열만 반환해 주세요.

출력 JSON 형식:
{{
  "week_plan": [
    {{
      "day": "월",
      "type": "훈련 종류 (예: 빌드업 조깅, 이지 조깅, 보강 운동, 완전 휴식)",
      "distance": "목표 거리 (예: '6.5km', '-' 등)",
      "intensity": "강도 표시 (예: '🟢 가볍게', '🟡 중간', '🟠 높음', '💤 OFF')",
      "detail": "훈련 목표 세부 설명 (예: '심박수 135-140 유지', '폼롤러 및 하체 스트레칭' 등)"
    }},
    {{
      "day": "화",
      "type": "훈련 종류",
      "distance": "목표 거리",
      "intensity": "강도 표시",
      "detail": "훈련 목표 세부 설명"
    }},
    {{
      "day": "수",
      "type": "훈련 종류",
      "distance": "목표 거리",
      "intensity": "강도 표시",
      "detail": "훈련 목표 세부 설명"
    }},
    {{
      "day": "목",
      "type": "훈련 종류",
      "distance": "목표 거리",
      "intensity": "강도 표시",
      "detail": "훈련 목표 세부 설명"
    }},
    {{
      "day": "금",
      "type": "훈련 종류",
      "distance": "목표 거리",
      "intensity": "강도 표시",
      "detail": "훈련 목표 세부 설명"
    }},
    {{
      "day": "토",
      "type": "훈련 종류",
      "distance": "목표 거리",
      "intensity": "강도 표시",
      "detail": "훈련 목표 세부 설명"
    }},
    {{
      "day": "일",
      "type": "훈련 종류",
      "distance": "목표 거리",
      "intensity": "강도 표시",
      "detail": "훈련 목표 세부 설명"
    }}
  ],
  "next_running": "오늘의 훈련 결과와 몸 상태에 기반하여 예측한 다음 목표 훈련의 권장 명칭, 타겟 거리 및 목표 심박수 가이드를 담은 한 줄 요약 텍스트 (예: '🏃‍♂️ Next Target: 6km 가벼운 회복 조깅 (평균 심박수 135-140 유지)')",
  "coach_comment": "사용자의 피로도, 통증, 오늘 달리기 결과, 그리고 임신/출산/육아 상황을 다정하고 부드럽게 케어하면서도 러닝 생리학적으로 유익한 지식을 전달하는 따뜻한 조언 3~4줄 (무조건 친절한 반말 혹은 격려의 존댓말 중 격식 있고 따뜻한 어투 사용)",
  "routines": [
    {{
      "name": "운동 이름 (notion_routines.md에서 피로도/통증 부위에 따라 매칭 선별된 운동)",
      "target": "타겟 부위 (예: '하체', '코어', '둔근' 등)",
      "reps": "횟수 (예: '10회', '각 12회' 등)",
      "sets": "세트수 (예: '3세트')",
      "tips": "수행 팁 및 설명 (notion_routines.md 참고)"
    }},
    ... (당일 상태에 최적화된 3~5개의 추천 운동 목록)
  ]
}}
"""
    if not GEMINI_API_KEY:
        print("⚠️ [Gemini] API Key가 설정되지 않았습니다. 기본 정적 코칭 데이터를 출력합니다.")
        return get_fallback_ai_content(stats, condition)
        
    try:
        print("🤖 [Gemini] AI 러닝 코치 동적 추론 실행 중...")
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")
        
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        content_text = response.text.strip()
        if content_text.startswith("```"):
            content_text = content_text.split("```")[1]
            if content_text.startswith("json"):
                content_text = content_text[4:]
        content_text = content_text.strip()
        
        ai_data = json.loads(content_text)
        print("🎉 [Gemini] AI 연산 성공 및 JSON 파싱 완료!")
        return ai_data
        
    except Exception as e:
        print(f"❌ [Gemini] AI 호출 중 오류 발생: {str(e)}. Fallback 데이터로 전환합니다.")
        return get_fallback_ai_content(stats, condition)

def get_fallback_ai_content(stats, condition):
    """Gemini API 오류 또는 키 미설정 시 사용하는 Fallback 데이터 빌더"""
    if condition["통증"] != "없음":
        comment = f"아 통증이 있으시군요. {condition['통증']} 부위는 무리해서 뛰지 마시고 오늘은 완전 휴식하거나 가벼운 마사지와 함께 폼롤러로 근막을 풀어주는 보강의 날로 삼아 주세요. 장거리 소화 몸 만들기는 조급하지 않게 부상을 관리하는 것부터 시작됩니다."
        next_run = "💤 Next Target: 완전 휴식 또는 하체 무부하 스트레칭"
        routines = [
            {"name": "Foam Roller Set & Stretching", "target": "하체 전반", "reps": "1~2분 (부위별)", "sets": "1세트", "tips": "폼롤러 / 종아리, 중둔근, 대퇴사두 등 통증 부위 집중 이완"},
            {"name": "Ankle Mobility Exercise", "target": "발목", "reps": "12회", "sets": "3세트", "tips": "발목의 전반적인 가동성 확보"},
            {"name": "Deadbug", "target": "코어", "reps": "10회", "sets": "3세트", "tips": "허리를 바닥에 강하게 밀착하여 코어 재건 / 어깨 석회 통증 주의"}
        ]
    else:
        comment = "현재 피로도와 컨디션이 매우 양호합니다! 무더운 여름이 다가오기 전에 주 5일 러닝 일정을 잘 소화하시되, 심박수 존 2~3 영역(135-145bpm) 내에서 조깅 마일리지를 차근차근 누적하는 것이 최고의 보약입니다. 러닝 전 웜업 기동성 스트레칭은 부상 방지의 핵심이니 잊지 마세요."
        next_run = "🏃‍♂️ Next Target: 6~8km 편안한 존2 조깅 (타겟 심박수 138-144bpm)"
        routines = [
            {"name": "90/90 Stretch", "target": "고관절", "reps": "좌우 각 5회", "sets": "1세트", "tips": "10초 유지 / 고관절 가동성 확보 및 골반 정렬"},
            {"name": "Hip Chair Circle", "target": "고관절", "reps": "좌우 각 15회", "sets": "1세트", "tips": "의자 활용 / 고관절 소켓을 부드럽게 열어주기"},
            {"name": "Toe Yoga", "target": "발바닥 / 아치", "reps": "좌우 각 10회", "sets": "3세트", "tips": "발바닥 고유수용감각 촉진 및 아치 활성화"},
            {"name": "Deadbug", "target": "코어", "reps": "10회", "sets": "3세트", "tips": "허리를 바닥에 강하게 밀착하여 코어 재건"},
            {"name": "Side Plank + Clamshell", "target": "둔근 (중둔근)", "reps": "좌우 각 12회", "sets": "3세트", "tips": "골반 고정, 엉덩이 옆쪽 중둔근 자극 확인"}
        ]
    
    week_plan = [
        {"day": "월", "type": "완전 휴식", "distance": "-", "intensity": "💤 OFF", "detail": "완전 휴식 및 가벼운 마사지"},
        {"day": "화", "type": "이지 조깅", "distance": "6.58 km", "intensity": "🟢 가볍게", "detail": "심박수 135-140 이지 조깅"},
        {"day": "수", "type": "빌드업 조깅", "distance": "8.00 km", "intensity": "🟡 중간", "detail": "후반 가속 훈련"},
        {"day": "목", "type": "보강 운동", "distance": "-", "intensity": "🟠 코어 집중", "detail": "고관절 기동성 및 코어 보강"},
        {"day": "금", "type": "지속주 런", "distance": "10.00 km", "intensity": "🟡 중간", "detail": "일정한 페이스 유지 지속주"},
        {"day": "토", "type": "조깅 + 질주", "distance": "5.00 km", "intensity": "🟢 가볍게", "detail": "가벼운 5km 조깅 및 100m 질주 3회"},
        {"day": "일", "type": "주말 장거리", "distance": "15.00 km", "intensity": "🟠 약간 높음", "detail": "LSD 마일리지 누적"}
    ]
    
    return {
        "week_plan": week_plan,
        "next_running": next_run,
        "coach_comment": comment,
        "routines": routines
    }

# 6. HTML 생성 및 프리미엄 Glassmorphism 스타일 적용
def build_html_dashboard(stats, ai):
    """최종 분석 데이터와 AI 콘텐츠를 조합하여 아주 아름다운 프리미엄 Glassmorphism 웹 대시보드(index.html)를 렌더링합니다."""
    
    # 데이터 직렬화
    week_plan_json = json.dumps(ai["week_plan"], ensure_ascii=False)
    routines_json = json.dumps(ai["routines"], ensure_ascii=False)
    stats_json = json.dumps({
        "total_may_mileage": stats["total_may_mileage"],
        "total_weekly_mileage": stats["total_weekly_mileage"],
        "today_run": stats["today_run"],
        "today_date": today_date,
        "today_weekday_idx": now_dt.weekday(), # 0: Mon, ..., 6: Sun
        "may_chart_url": stats["may_chart_url"],
        "week_chart_url": stats["week_chart_url"]
    }, ensure_ascii=False)
    coach_comment_json = json.dumps(ai["coach_comment"], ensure_ascii=False)
    next_running_json = json.dumps(ai["next_running"], ensure_ascii=False)
    condition_json = json.dumps(load_condition(), ensure_ascii=False)

    # 대시보드 HTML/CSS/JS 뼈대 (plain raw string으로 선언하여 f-string curly-brace 충돌 원천 배제)
    html_template = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Project 330 - AI Running Coach</title>
    <!-- Google Fonts 연동 (Outfit & Inter) -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;600;800&display=swap" rel="stylesheet">
    
    <style>
        :root {
            --primary: #FC4C02;
            --primary-glow: rgba(252, 76, 2, 0.35);
            --bg: #0b0c10;
            --card-bg: rgba(30, 30, 35, 0.45);
            --card-border: rgba(255, 255, 255, 0.08);
            --text: #e5e7eb;
            --text-muted: #9ca3af;
            --badge-green: rgba(16, 185, 129, 0.2);
            --badge-yellow: rgba(245, 158, 11, 0.2);
            --badge-orange: rgba(249, 115, 22, 0.2);
            --badge-red: rgba(239, 68, 68, 0.2);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg);
            background-image: 
                radial-gradient(circle at 10% 20%, rgba(252, 76, 2, 0.08) 0%, transparent 40%),
                radial-gradient(circle at 90% 80%, rgba(252, 76, 2, 0.05) 0%, transparent 40%);
            background-attachment: fixed;
            color: var(--text);
            line-height: 1.6;
            padding: 16px;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }

        .container {
            width: 100%;
            max-width: 500px;
            background: rgba(20, 20, 25, 0.7);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--card-border);
            border-radius: 24px;
            padding: 24px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.6), inset 0 1px 1px rgba(255,255,255,0.1);
            position: relative;
        }

        /* Header */
        header {
            text-align: center;
            margin-bottom: 25px;
            position: relative;
        }

        .brand {
            font-family: 'Outfit', sans-serif;
            font-size: 28px;
            font-weight: 800;
            color: #fff;
            letter-spacing: -0.5px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }

        .brand span {
            color: var(--primary);
            text-shadow: 0 0 15px var(--primary-glow);
        }

        .sync-time {
            font-size: 11px;
            color: var(--text-muted);
            margin-top: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 4px;
        }
        
        .sync-pulse {
            width: 6px;
            height: 6px;
            background-color: #10b981;
            border-radius: 50%;
            display: inline-block;
            box-shadow: 0 0 8px #10b981;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
        }

        /* Settings Floating Button */
        .settings-btn {
            position: absolute;
            right: 0;
            top: 4px;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            color: #fff;
            width: 32px;
            height: 32px;
            border-radius: 50%;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s ease;
        }
        .settings-btn:hover {
            background: var(--primary);
            border-color: var(--primary);
            box-shadow: 0 0 10px var(--primary-glow);
        }

        /* Section Global */
        section {
            margin-bottom: 28px;
        }

        h2 {
            font-family: 'Outfit', sans-serif;
            font-size: 17px;
            font-weight: 600;
            color: #fff;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        /* Progress Card */
        .progress-card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 16px;
            margin-bottom: 16px;
            position: relative;
            overflow: hidden;
        }

        .progress-header {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            margin-bottom: 8px;
        }}

        .progress-title {
            font-size: 13px;
            color: var(--text-muted);
            font-weight: 500;
        }

        .progress-value {
            font-family: 'Outfit', sans-serif;
            font-size: 20px;
            font-weight: 800;
            color: #fff;
        }

        .progress-value span {
            color: var(--primary);
        }

        .progress-bar-container {
            width: 100%;
            height: 8px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 999px;
            overflow: hidden;
            margin-top: 4px;
        }

        .progress-bar {
            height: 100%;
            background: linear-gradient(90deg, #ff7e40, var(--primary));
            border-radius: 999px;
            box-shadow: 0 0 10px rgba(252, 76, 2, 0.5);
            transition: width 1s ease-out;
        }

        .chart-box {
            text-align: center;
            margin-top: 12px;
            background: rgba(0, 0, 0, 0.2);
            padding: 10px;
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.03);
            min-height: 140px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .chart-box img {
            max-width: 100%;
            height: auto;
        }

        /* Daily Running Cards */
        .stat-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
        }

        .stat-card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 14px;
            padding: 12px;
            text-align: center;
        }

        .stat-title {
            font-size: 10px;
            color: var(--text-muted);
            margin-bottom: 4px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .stat-value {
            font-family: 'Outfit', sans-serif;
            font-size: 18px;
            font-weight: 800;
            color: #fff;
        }

        .stat-unit {
            font-size: 10px;
            color: var(--text-muted);
            font-weight: 400;
        }

        .rest-card {
            background: rgba(252, 76, 2, 0.05);
            border: 1px dashed rgba(252, 76, 2, 0.25);
            border-radius: 16px;
            padding: 18px;
            text-align: center;
        }

        .rest-icon {
            font-size: 24px;
            display: block;
            margin-bottom: 6px;
        }

        .rest-title {
            font-family: 'Outfit', sans-serif;
            font-size: 15px;
            font-weight: 600;
            color: #fff;
        }

        .rest-desc {
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 4px;
        }

        /* Week Plan Table */
        .week-plan-card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 14px;
            overflow-x: auto;
        }

        .week-table {
            width: 100%;
            border-collapse: collapse;
            text-align: center;
            font-size: 13px;
        }

        .week-table th {
            padding: 8px 4px;
            border-bottom: 1px solid #444;
            color: var(--primary);
            font-weight: bold;
        }

        .week-table td {
            padding: 8px 4px;
            border-bottom: 1px solid #2a2a2a;
            vertical-align: middle;
            color: #fff;
        }

        .week-table input[type="text"] {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: #fff;
            border-radius: 4px;
            padding: 3px 6px;
            font-size: 12px;
            width: 100%;
            text-align: center;
            outline: none;
            transition: all 0.2s ease;
        }

        .week-table input[type="text"]:focus {
            border-color: var(--primary);
            background: rgba(255, 255, 255, 0.1);
        }

        .week-table select {
            background: #1e1e24;
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: #fff;
            border-radius: 4px;
            padding: 2px 4px;
            font-size: 12px;
            outline: none;
            cursor: pointer;
            width: 100%;
        }

        .week-table tr.active-today td {
            background: rgba(252, 76, 2, 0.07);
        }
        .week-table tr.active-today td:first-child {
            border-left: 3px solid var(--primary);
        }

        /* Coach's Comment Block */
        .coach-comment-box {
            background: rgba(252, 76, 2, 0.07);
            border-left: 4px solid var(--primary);
            border-radius: 4px 14px 14px 4px;
            padding: 14px;
            font-size: 13px;
            color: #f3f4f6;
            margin: 15px 0;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.15);
        }
        
        .comment-header {
            font-family: 'Outfit', sans-serif;
            font-weight: 600;
            color: var(--primary);
            font-size: 13px;
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            gap: 4px;
        }

        /* Next Running Recommend Box */
        .next-recommend-box {
            background: linear-gradient(135deg, rgba(252, 76, 2, 0.15) 0%, rgba(20, 20, 25, 0.5) 100%);
            border: 1px solid rgba(252, 76, 2, 0.25);
            border-radius: 14px;
            padding: 12px 14px;
            font-size: 13px;
            font-weight: 500;
            color: #fff;
            box-shadow: 0 4px 10px var(--primary-glow);
            margin-top: 10px;
        }

        /* Action Buttons */
        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 100%;
            background: linear-gradient(90deg, #ff7e40, var(--primary));
            color: #fff;
            border: none;
            border-radius: 12px;
            padding: 12px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            box-shadow: 0 4px 15px var(--primary-glow);
            gap: 6px;
            margin-top: 12px;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(252, 76, 2, 0.5);
        }
        .btn:active {
            transform: translateY(0);
        }
        .btn-secondary {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            box-shadow: none;
            color: #fff;
        }
        .btn-secondary:hover {
            background: rgba(255,255,255,0.1);
            border-color: rgba(255,255,255,0.2);
            box-shadow: none;
            transform: none;
        }

        /* Condition Editor */
        .condition-editor-card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 14px;
            margin-bottom: 20px;
        }

        .input-group {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-bottom: 10px;
        }
        
        .input-item {
            display: flex;
            flex-direction: column;
        }

        .input-item label {
            font-size: 10px;
            color: var(--text-muted);
            margin-bottom: 4px;
            text-transform: uppercase;
            font-weight: 600;
        }

        .input-item select, .input-item input {
            background: #1e1e24;
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: #fff;
            border-radius: 6px;
            padding: 8px;
            font-size: 12px;
            outline: none;
        }

        .notes-item {
            display: flex;
            flex-direction: column;
        }
        .notes-item label {
            font-size: 10px;
            color: var(--text-muted);
            margin-bottom: 4px;
            text-transform: uppercase;
            font-weight: 600;
        }
        .notes-item input {
            background: #1e1e24;
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: #fff;
            border-radius: 6px;
            padding: 8px;
            font-size: 12px;
            outline: none;
            width: 100%;
        }

        /* Block Routine checklist */
        .routine-container-list {
            display: flex;
            flex-direction: column;
            gap: 10px;
            margin-top: 10px;
        }

        .routine-block {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 14px;
            padding: 14px;
            position: relative;
            transition: all 0.2s ease;
            display: flex;
            align-items: flex-start;
            gap: 12px;
            user-select: none;
        }

        .routine-block.completed {
            border-color: rgba(16, 185, 129, 0.2);
            background: rgba(16, 185, 129, 0.03);
        }

        .routine-block.completed .routine-details-box span.routine-name {
            text-decoration: line-through;
            color: var(--text-muted);
        }

        .routine-check {
            margin-top: 4px;
            flex-shrink: 0;
        }

        .routine-check input[type="checkbox"] {
            appearance: none;
            -webkit-appearance: none;
            width: 19px;
            height: 19px;
            border: 2px solid var(--text-muted);
            border-radius: 6px;
            outline: none;
            background-color: transparent;
            cursor: pointer;
            display: grid;
            place-content: center;
            transition: all 0.2s ease;
        }

        .routine-check input[type="checkbox"]::before {
            content: "✓";
            font-size: 12px;
            font-weight: bold;
            color: #fff;
            transform: scale(0);
            transition: transform 0.15s ease-in-out;
        }

        .routine-check input[type="checkbox"]:checked {
            background-color: #10b981;
            border-color: #10b981;
            box-shadow: 0 0 8px rgba(16, 185, 129, 0.4);
        }

        .routine-check input[type="checkbox"]:checked::before {
            transform: scale(1);
        }

        .routine-details-box {
            flex-grow: 1;
        }

        .routine-meta-row {
            display: flex;
            align-items: center;
            gap: 6px;
            margin-bottom: 4px;
        }

        .routine-badge {
            font-size: 9px;
            font-weight: bold;
            padding: 2px 6px;
            border-radius: 4px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #fff;
        }

        .badge-core { background: rgba(59, 130, 246, 0.2); border: 1px solid rgba(59, 130, 246, 0.4); }
        .badge-lower { background: rgba(139, 92, 246, 0.2); border: 1px solid rgba(139, 92, 246, 0.4); }
        .badge-ankle { background: rgba(236, 72, 153, 0.2); border: 1px solid rgba(236, 72, 153, 0.4); }
        .badge-general { background: rgba(107, 114, 128, 0.2); border: 1px solid rgba(107, 114, 128, 0.4); }

        .routine-sets-reps {
            font-size: 10px;
            color: var(--text-muted);
            font-weight: 500;
        }

        .routine-name {
            font-size: 13.5px;
            font-weight: 600;
            color: #fff;
            display: block;
            margin-bottom: 2px;
        }

        .routine-tips {
            font-size: 11.5px;
            color: var(--text-muted);
            margin-top: 4px;
            line-height: 1.4;
            display: block;
        }

        .routine-controls {
            display: flex;
            flex-direction: column;
            gap: 6px;
            margin-left: 8px;
            flex-shrink: 0;
            opacity: 0.3;
            transition: opacity 0.2s ease;
        }

        .routine-block:hover .routine-controls {
            opacity: 1;
        }

        .ctrl-btn {
            background: transparent;
            border: none;
            color: var(--text-muted);
            cursor: pointer;
            font-size: 11px;
            display: flex;
            align-items: center;
            justify-content: center;
            width: 18px;
            height: 18px;
            border-radius: 4px;
            transition: all 0.2s ease;
        }

        .ctrl-btn:hover {
            background: rgba(255,255,255,0.07);
            color: #fff;
        }
        .ctrl-btn.btn-delete:hover {
            background: rgba(239, 68, 68, 0.15);
            color: #ef4444;
        }

        /* Modal / Overlay Settings */
        .overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: rgba(0,0,0,0.6);
            backdrop-filter: blur(8px);
            z-index: 1000;
            display: flex;
            align-items: center;
            justify-content: center;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.3s ease;
        }

        .overlay.active {
            opacity: 1;
            pointer-events: auto;
        }

        .modal {
            background: rgba(25, 25, 30, 0.85);
            border: 1px solid var(--card-border);
            width: 90%;
            max-width: 400px;
            border-radius: 20px;
            padding: 24px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.8);
            transform: scale(0.9);
            transition: transform 0.3s ease;
        }

        .overlay.active .modal {
            transform: scale(1);
        }

        .modal-header {
            font-family: 'Outfit', sans-serif;
            font-size: 18px;
            font-weight: 700;
            color: #fff;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .modal-close {
            background: transparent;
            border: none;
            color: var(--text-muted);
            cursor: pointer;
            font-size: 20px;
        }

        .modal-body p {
            font-size: 12.5px;
            color: var(--text-muted);
            margin-bottom: 16px;
            line-height: 1.5;
        }

        .modal-body input[type="password"], .modal-body input[type="text"] {
            background: #1e1e24;
            border: 1px solid rgba(255,255,255,0.1);
            color: #fff;
            width: 100%;
            border-radius: 8px;
            padding: 10px;
            font-size: 13px;
            outline: none;
            margin-bottom: 16px;
        }

        .modal-body input:focus {
            border-color: var(--primary);
        }

        /* Loading Spinner */
        .spinner-container {
            display: none;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 20px 0;
        }
        .spinner {
            width: 32px;
            height: 32px;
            border: 3px solid rgba(252, 76, 2, 0.1);
            border-radius: 50%;
            border-top-color: var(--primary);
            animation: spin 1s linear infinite;
            box-shadow: 0 0 10px var(--primary-glow);
        }
        @keyframes spin {
            100% { transform: rotate(360deg); }
        }
        .spinner-text {
            font-size: 11px;
            color: var(--text-muted);
            margin-top: 10px;
            font-weight: 500;
        }

        /* Add Exercise Dropdown Card */
        .add-routine-drawer {
            margin-top: 10px;
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 14px;
            padding: 12px;
            display: none;
            animation: slideDown 0.25s ease-out;
        }

        @keyframes slideDown {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .add-routine-drawer select {
            background: #1e1e24;
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: #fff;
            border-radius: 6px;
            padding: 8px;
            font-size: 12px;
            outline: none;
            width: 100%;
            cursor: pointer;
            margin-bottom: 10px;
        }

        /* Footer */
        footer {
            text-align: center;
            font-size: 10px;
            color: var(--text-muted);
            margin-top: 24px;
            border-top: 1px solid rgba(255,255,255,0.05);
            padding-top: 14px;
        }

        footer a {
            color: var(--primary);
            text-decoration: none;
        }

        /* Scroll Custom */
        ::-webkit-scrollbar {
            width: 6px;
        }
        ::-webkit-scrollbar-track {
            background: transparent;
        }
        ::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 99px;
        }
    </style>
    <!-- Local API Key Config Loader (In gitignore) -->
    <script src="api_key.js" onerror="console.log('Local api_key.js not found - using localStorage')"></script>
</head>
<body>
    <div class="container">
        <!-- Settings Button -->
        <button class="settings-btn" id="open-settings-btn" title="AI API Key 설정">⚙️</button>

        <!-- Header -->
        <header>
            <div class="brand">🏃‍♂️ Project <span>330</span></div>
            <div class="sync-time">
                <span class="sync-pulse"></span>
                <span>Last Sync: __NOW_STR__ (KST)</span>
            </div>
        </header>

        <!-- Mileage Progress -->
        <section>
            <h2>📈 Monthly Mileage (May)</h2>
            <div class="progress-card">
                <div class="progress-header">
                    <span class="progress-title">목표 달성률</span>
                    <span class="progress-value"><span id="may-mileage-val">__TOTAL_MAY_MILEAGE__</span> / 200 km</span>
                </div>
                <div class="progress-bar-container">
                    <div class="progress-bar" id="may-progress-bar" style="width: __MAY_PROGRESS_PERCENT__%;"></div>
                </div>
                <div class="chart-box">
                    <img src="__MAY_CHART_URL__" alt="May Mileage Chart" />
                </div>
            </div>

            <h2>⏱️ Weekly Mileage</h2>
            <div class="progress-card">
                <div class="progress-header">
                    <span class="progress-title">목표 달성률</span>
                    <span class="progress-value"><span id="week-mileage-val">__TOTAL_WEEKLY_MILEAGE__</span> / 50 km</span>
                </div>
                <div class="progress-bar-container">
                    <div class="progress-bar" id="week-progress-bar" style="width: __WEEK_PROGRESS_PERCENT__%;"></div>
                </div>
                <div class="chart-box">
                    <img src="__WEEK_CHART_URL__" alt="Weekly Mileage Chart" />
                </div>
            </div>
        </section>

        <!-- Week Plan (Dynamic & Editable) -->
        <section>
            <h2>📅 Week Plan (주간 계획표)</h2>
            <div class="week-plan-card">
                <table class="week-table" id="week-plan-table">
                    <thead>
                        <tr style="border-bottom:1px solid #444; color: var(--primary);">
                            <th style="width: 12%;">요일</th>
                            <th style="width: 28%;">훈련 타입</th>
                            <th style="width: 20%;">거리</th>
                            <th style="width: 25%;">강도</th>
                        </tr>
                    </thead>
                    <tbody id="week-plan-tbody">
                        <!-- JS로 렌더링 -->
                    </tbody>
                </table>
            </div>
        </section>

        <!-- Daily Running stats -->
        <section>
            <h2>🏃‍♂️ Daily Running (<span id="today-date-header">__TODAY_DATE__</span>)</h2>
            <div id="daily-running-container">
                <!-- Real Run Stats OR Dynamic Pending Card OR Planned Rest Card rendered via JS -->
            </div>
            
            <!-- AI Coach Box -->
            <div class="coach-comment-box" style="margin-top: 15px;">
                <div class="comment-header">📋 AI COACH'S COMMENT</div>
                <div id="coach-comment-content">
                    <!-- JS로 바인딩 -->
                </div>
            </div>
            
            <div class="next-recommend-box" id="next-running-content">
                <!-- JS로 바인딩 -->
            </div>
        </section>

        <!-- Condition Editor Card -->
        <section>
            <h2>🧠 Today's Condition & AI Feedback</h2>
            <div class="condition-editor-card">
                <div class="input-group">
                    <div class="input-item">
                        <label for="cond-fatigue">피로도</label>
                        <select id="cond-fatigue">
                            <option value="하">하 (쾌조)</option>
                            <option value="중">중 (약간 피로)</option>
                            <option value="상">상 (강한 피로)</option>
                        </select>
                    </div>
                    <div class="input-item">
                        <label for="cond-pain">통증 부위</label>
                        <select id="cond-pain">
                            <option value="없음">없음 (양호)</option>
                            <option value="발목">발목 통증</option>
                            <option value="아킬레스건">아킬레스건</option>
                            <option value="무릎">무릎 (슬개건)</option>
                            <option value="허리/골반">허리 / 골반</option>
                            <option value="종아리">종아리/정강이</option>
                        </select>
                    </div>
                </div>
                <div class="notes-item" style="margin-bottom: 12px;">
                    <label for="cond-notes">특이사항 및 메모</label>
                    <input type="text" id="cond-notes" value="" placeholder="예: 어깨가 결림. 오늘은 가볍게 달릴 예정..." />
                </div>
                <button class="btn" id="evaluate-btn">
                    <span>✨ 수정 후 AI 코치 평가받기</span>
                </button>
                <div class="spinner-container" id="ai-loading">
                    <div class="spinner"></div>
                    <div class="spinner-text">AI 코치가 훈련 세션을 평가하고 있습니다...</div>
                </div>
            </div>
        </section>

        <!-- Today's Routine checklist -->
        <section>
            <h2>🛠️ Routine For Today (보강/스트레칭 블록)</h2>
            <div id="routine-block-list" class="routine-container-list">
                <!-- JS로 블록 렌더링 -->
            </div>
            
            <button class="btn btn-secondary" id="open-add-routine-btn" style="margin-top: 10px; border-style: dashed;">
                <span>➕ 보강운동 라이브러리에서 추가</span>
            </button>

            <!-- 운동 추가 영역 -->
            <div class="add-routine-drawer" id="add-routine-drawer">
                <select id="exercise-library-select">
                    <option value="">-- 추가할 운동을 골라주세요 --</option>
                </select>
                <div style="display: flex; gap: 8px;">
                    <button class="btn" id="add-exercise-confirm" style="margin-top: 0; padding: 8px; font-size: 12px;">추가 완료</button>
                    <button class="btn btn-secondary" id="add-exercise-cancel" style="margin-top: 0; padding: 8px; font-size: 12px;">취소</button>
                </div>
            </div>
        </section>

        <!-- Footer -->
        <footer>
            <p>Automated with Strava API & Gemini 2.0 & QuickChart</p>
            <p style="margin-top: 4px;">Designed by Antigravity for <a href="https://github.com/Jay330-KR/Jaewon-s-Running-Coach" target="_blank">Project330</a></p>
        </footer>
    </div>

    <!-- API Key Settings Modal -->
    <div class="overlay" id="settings-overlay">
        <div class="modal">
            <div class="modal-header">
                <span>🔑 Gemini API Key 설정</span>
                <button class="modal-close" id="close-settings-btn">&times;</button>
            </div>
            <div class="modal-body">
                <p>수정 후 실시간 AI 평가를 받으려면 Gemini API Key가 필요합니다. 입력된 키는 외부 서버로 전송되지 않고 브라우저에 안전하게 저장됩니다.</p>
                <label style="font-size: 11px; color: var(--text-muted); font-weight: bold; margin-bottom: 4px; display: block;">GEMINI API KEY</label>
                <input type="password" id="api-key-input" placeholder="AIzaSy..." />
                <button class="btn" id="save-settings-btn">설정 저장</button>
            </div>
        </div>
    </div>

    <!-- State & Core Dynamic Script -->
    <script>
        // 1. Python에서 전달된 초기 전역 데이터 바인딩
        const INITIAL_WEEK_PLAN = __WEEK_PLAN_JSON__;
        const INITIAL_ROUTINES = __ROUTINES_JSON__;
        const STATS_DATA = __STATS_JSON__;
        const INITIAL_COACH_COMMENT = __COACH_COMMENT_JSON__;
        const INITIAL_NEXT_RUNNING = __NEXT_RUNNING_JSON__;
        const CONDITION_DATA = __CONDITION_JSON__;

        // 32종의 노션 보강운동 라이브러리 전체 데이터
        const EXERCISE_LIBRARY = [
            { "target": "하체 전반", "name": "Foam Roller Set & Stretching", "reps": "1~2분 (부위별)", "sets": "1세트", "tips": "폼롤러 / 종아리, 중둔근, 대퇴사두 등 이완 중심" },
            { "target": "코어", "name": "Deadbug", "reps": "10회", "sets": "3세트", "tips": "허리를 바닥에 강하게 밀착하여 코어 재건 / 어깨 석회 통증 주의" },
            { "target": "둔근 (중둔근)", "name": "Side Plank + Clamshell", "reps": "좌우 각 12회", "sets": "3세트", "tips": "골반 고정, 엉덩이 옆쪽 중둔근 자극 확인" },
            { "target": "둔근", "name": "Single Leg Hip Bridge", "reps": "각 10회", "sets": "3세트", "tips": "든 다리 골반이 처지지 않게 수평 유지" },
            { "target": "종아리 / 발목", "name": "Eccentric Calf Raise", "reps": "15회", "sets": "3세트", "tips": "5초 동안 소리 없이 천천히 뒤꿈치 내리기" },
            { "target": "고관절", "name": "90/90 Stretch", "reps": "좌우 각 5회", "sets": "1세트", "tips": "10초 유지 / 고관절 가동성 확보 및 골반 정렬" },
            { "target": "발목", "name": "Ankle Mobility Exercise", "reps": "12회", "sets": "3세트", "tips": "발목의 전반적인 가동성 확보" },
            { "target": "햄스트링", "name": "Hamstring Stretch", "reps": "각 1분", "sets": "2세트", "tips": "반동 없이 길게 늘려 후방 사슬 이완" },
            { "target": "둔근", "name": "Hip Bridge", "reps": "12회", "sets": "3세트", "tips": "골반 수평 유지 및 둔근 시동 (신경계 활성화)" },
            { "target": "후방 사슬", "name": "Romanian Deadlift", "reps": "10~15회", "sets": "3세트", "tips": "저중량으로 힙힌지 감각 각인 (무릎 고정, 엉덩이 멀리)" },
            { "target": "하체 / 편측성", "name": "Split Squat", "reps": "각 8회", "sets": "3세트", "tips": "무릎이 안으로 굽지 않게 외회전 토크 유지" },
            { "target": "하체 / 둔근", "name": "Backward Lunge", "reps": "각 8회", "sets": "3세트", "tips": "덤벨 활용 편측성 훈련" },
            { "target": "하체 전반", "name": "Goblet Squat", "reps": "12회", "sets": "3세트", "tips": "무릎을 바깥으로 밀어내며 엉덩이 강한 자극" },
            { "target": "하체 전반", "name": "Weighted Squat", "reps": "12회", "sets": "5세트", "tips": "점진적 과부하 트레이닝" },
            { "target": "발바닥 / 아치", "name": "Toe Yoga", "reps": "좌우 각 10회", "sets": "3세트", "tips": "발바닥 고유수용감각 촉진 및 아치 활성화" },
            { "target": "둔근 / 하체", "name": "Pigeon Lift (S-Lunge)", "reps": "좌우 각 10회", "sets": "3세트", "tips": "힌지 포지션 잡고 엉덩이 힘으로 상체 리프트" },
            { "target": "햄스트링", "name": "Elephant Walk", "reps": "10~20회", "sets": "2세트", "tips": "햄스트링 가벼운 동적 가동성 확보" },
            { "target": "고관절", "name": "Hip Chair Circle", "reps": "좌우 각 15회", "sets": "1세트", "tips": "의자 활용 / 고관절 소켓을 부드럽게 열어주기" },
            { "target": "후방 사슬", "name": "Standing Hamstring Sweep", "reps": "좌우 각 15회", "sets": "1세트", "tips": "메인 운동 전 후방 사슬 예열" },
            { "target": "하체 / 내전근", "name": "Cossack Squat Hold", "reps": "좌우 각 3회", "sets": "1세트", "tips": "10초 정지 / 내전근 능동 활성화" },
            { "target": "둔근", "name": "Kickback", "reps": "좌우 각 10회", "sets": "3세트", "tips": "둔근 활성 및 러닝 보행 동작 연동" },
            { "target": "무릎 / 발목", "name": "Tibial Rotation Drill", "reps": "15회", "sets": "3세트", "tips": "무릎 고정하고 정강이뼈만 회전 훈련" },
            { "target": "대퇴사두", "name": "Foam Roller Quad Setting", "reps": "12회", "sets": "3세트", "tips": "오금으로 짓누르며 허벅지 내측광근 수축" },
            { "target": "대퇴사두", "name": "Internal Rotation Extension", "reps": "12회", "sets": "3세트", "tips": "내회전 상태로 편측 저항 버티며 내리기" },
            { "target": "무릎 결합조직", "name": "Lean Forward Isometric Hold", "reps": "20초", "sets": "3세트", "tips": "뒤꿈치 든 채 정적 버티기" },
            { "target": "하체 협응력", "name": "Bosu Ball Tap & Hold", "reps": "10회", "sets": "3세트", "tips": "불안정한 지면 딛고 발바닥 미세 제어" },
            { "target": "둔근 / 하체", "name": "Band Diagonal Kickback", "reps": "좌우 각 12회", "sets": "3세트", "tips": "루프 밴드로 엉덩이 측면 및 뒤 활성" },
            { "target": "하체 / 고관절", "name": "Band Monster Walk", "reps": "사방 10걸음", "sets": "3세트", "tips": "밴드 착용 상태로 사방 걷기" },
            { "target": "장요근 / 고관절", "name": "Band Hip Flexor Lift", "reps": "좌우 각 12회", "sets": "3세트", "tips": "고관절 및 장요근 굴곡력 강화" },
            { "target": "플라이오메트릭", "name": "Skate Drill & Landing", "reps": "좌우 각 8회", "sets": "3세트", "tips": "양발 랜딩 후 한발 도약 측면 점프" },
            { "target": "전신 / 코어", "name": "Forward Lean Walk with Waterbag", "reps": "15걸음", "sets": "3세트", "tips": "워터백 부하 저항 극복 전진" },
            { "target": "발목 / 민첩성", "name": "Plate Quick Tap", "reps": "좌우 각 15회", "sets": "3세트", "tips": "원판 빠르게 찍고 복귀 발목 탄성 제어" }
        ];

        // 2. 어플리케이션 상태(State) 관리 객체
        let appState = {
            weekPlan: [],
            routines: [],
            apiKey: ""
        };

        // 3. 요일 헬퍼
        const WEEKDAYS_KO = ["월", "화", "수", "목", "금", "토", "일"];

        // 4. 초기화 실행
        document.addEventListener('DOMContentLoaded', () => {
            initAppState();
            renderSettingsModal();
            renderWeekPlanTable();
            renderDailyRunning();
            renderRoutines();
            setupAddExerciseLibrary();
            bindEvents();
        });

        // 상태 초기화 (localStorage 우선 로드)
        function initAppState() {
            // API 키
            appState.apiKey = localStorage.getItem('gemini_api_key') || "";
            if (!appState.apiKey && window.LOCAL_GEMINI_API_KEY) {
                appState.apiKey = window.LOCAL_GEMINI_API_KEY;
                localStorage.setItem('gemini_api_key', appState.apiKey);
            }

            // 주간 계획
            const cachedWeekPlan = localStorage.getItem('project330_week_plan');
            if (cachedWeekPlan) {
                appState.weekPlan = JSON.parse(cachedWeekPlan);
            } else {
                appState.weekPlan = INITIAL_WEEK_PLAN;
                localStorage.setItem('project330_week_plan', JSON.stringify(appState.weekPlan));
            }

            // 보강운동 루틴
            const cachedRoutines = localStorage.getItem('project330_routines_today');
            if (cachedRoutines) {
                appState.routines = JSON.parse(cachedRoutines);
            } else {
                appState.routines = INITIAL_ROUTINES.map((item, idx) => ({ ...item, id: idx, checked: false }));
                localStorage.setItem('project330_routines_today', JSON.stringify(appState.routines));
            }

            // 몸 상태 UI 세팅
            document.getElementById('cond-fatigue').value = CONDITION_DATA.피로도 || "하";
            document.getElementById('cond-pain').value = CONDITION_DATA.통증 || "없음";
            document.getElementById('cond-notes').value = CONDITION_DATA.기타 || "";
        }

        // 5. Weekly Plan 테이블 렌더러
        function renderWeekPlanTable() {
            const tbody = document.getElementById('week-plan-tbody');
            if (!tbody) return;

            tbody.innerHTML = "";
            const todayIdx = STATS_DATA.today_weekday_idx;

            appState.weekPlan.forEach((plan, index) => {
                const tr = document.createElement('tr');
                if (index === todayIdx) {
                    tr.classList.add('active-today');
                }

                const isTodayLabel = index === todayIdx ? `${plan.day} (오늘)` : plan.day;
                const fontStyle = index === todayIdx ? 'font-weight: bold; color: var(--primary);' : 'font-weight: bold;';

                tr.innerHTML = `
                    <td style="padding: 8px 4px; ${fontStyle}">${isTodayLabel}</td>
                    <td>
                        <input type="text" value="${plan.type}" class="week-edit-input" data-idx="${index}" data-field="type" />
                    </td>
                    <td>
                        <input type="text" value="${plan.distance}" class="week-edit-input" data-idx="${index}" data-field="distance" style="width: 80%;" />
                    </td>
                    <td>
                        <select class="week-edit-select" data-idx="${index}" data-field="intensity">
                            <option value="🟢 가볍게" ${plan.intensity === '🟢 가볍게' ? 'selected' : ''}>🟢 가볍게</option>
                            <option value="🟡 중간" ${plan.intensity === '🟡 중간' ? 'selected' : ''}>🟡 중간</option>
                            <option value="🟠 높음" ${plan.intensity === '🟠 높음' ? 'selected' : ''}>🟠 높음</option>
                            <option value="💤 OFF" ${plan.intensity === '💤 OFF' ? 'selected' : ''}>💤 OFF</option>
                        </select>
                    </td>
                `;
                tbody.appendChild(tr);
            });

            // 입력 이벤트 바인딩
            tbody.querySelectorAll('.week-edit-input').forEach(input => {
                input.addEventListener('change', (e) => {
                    const idx = e.target.dataset.idx;
                    const field = e.target.dataset.field;
                    appState.weekPlan[idx][field] = e.target.value;
                    localStorage.setItem('project330_week_plan', JSON.stringify(appState.weekPlan));
                    
                    if (parseInt(idx) === todayIdx) {
                        renderDailyRunning();
                    }
                });
            });

            tbody.querySelectorAll('.week-edit-select').forEach(select => {
                select.addEventListener('change', (e) => {
                    const idx = e.target.dataset.idx;
                    const field = e.target.dataset.field;
                    appState.weekPlan[idx][field] = e.target.value;
                    localStorage.setItem('project330_week_plan', JSON.stringify(appState.weekPlan));
                    
                    if (parseInt(idx) === todayIdx) {
                        renderDailyRunning();
                    }
                });
            });
        }

        // 6. Daily Running 동적 렌더러
        function renderDailyRunning() {
            const container = document.getElementById('daily-running-container');
            const commentBox = document.getElementById('coach-comment-content');
            const nextRecommendBox = document.getElementById('next-running-content');
            if (!container) return;

            commentBox.innerHTML = localStorage.getItem('project330_coach_comment') || INITIAL_COACH_COMMENT;
            nextRecommendBox.innerHTML = localStorage.getItem('project330_next_running') || INITIAL_NEXT_RUNNING;

            const todayRun = STATS_DATA.today_run;
            if (todayRun) {
                const distKm = (todayRun.distance / 1000.0).toFixed(2);
                const movingMin = Math.floor(todayRun.moving_time / 60);
                
                let paceMin = 0;
                let paceSec = 0;
                if (parseFloat(distKm) > 0) {
                    const totalSec = todayRun.moving_time;
                    const secPerKm = totalSec / parseFloat(distKm);
                    paceMin = Math.floor(secPerKm / 60);
                    paceSec = Math.round(secPerKm % 60);
                }
                
                const avgHr = todayRun.average_heartrate || "-";

                container.innerHTML = `
                    <div class="stat-grid">
                        <div class="stat-card">
                            <div class="stat-title">실제 거리</div>
                            <div class="stat-value">${distKm} <span class="stat-unit">km</span></div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-title">실제 페이스</div>
                            <div class="stat-value">${paceMin}'${paceSec.toString().padStart(2, '0')}" <span class="stat-unit">/km</span></div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-title">평균 심박수</div>
                            <div class="stat-value">${avgHr} <span class="stat-unit">bpm</span></div>
                        </div>
                    </div>
                `;
                return;
            }

            const todayIdx = STATS_DATA.today_weekday_idx;
            const todayPlan = appState.weekPlan[todayIdx] || { type: "완전 휴식", distance: "-", intensity: "💤 OFF", detail: "휴식" };

            if (todayPlan.intensity.includes("OFF") || todayPlan.type.includes("휴식")) {
                container.innerHTML = `
                    <div class="rest-card">
                        <span class="rest-icon">💤</span>
                        <div class="rest-title">Today is a Rest Day! (계획된 휴식)</div>
                        <div class="rest-desc">근섬유의 재건과 피로 회복도 훈련의 연장선입니다. 폼롤러나 코어 보강운동에 집중해 주세요.</div>
                    </div>
                `;
            } else {
                container.innerHTML = `
                    <div class="rest-card" style="background: rgba(252,76,2,0.03); border: 1px dashed rgba(252,76,2,0.4);">
                        <span class="rest-icon">🏃‍♂️</span>
                        <div class="rest-title" style="color: var(--primary);">오늘 예정된 본운동: ${todayPlan.type} (${todayPlan.distance})</div>
                        <div class="rest-desc" style="color: #fff; font-weight:500; margin-top: 6px;">아직 오늘 달린 러닝 기록이 스트라바에 연동되지 않았습니다.</div>
                        <div class="rest-desc" style="font-size: 11px; margin-top: 2px;">운동을 마친 후 자동으로 동기화되거나, 아래 보강 루틴을 먼저 실천해 보세요!</div>
                    </div>
                `;
            }
        }

        // 7. Routine 블록형 렌더러
        function renderRoutines() {
            const list = document.getElementById('routine-block-list');
            if (!list) return;

            list.innerHTML = "";

            if (appState.routines.length === 0) {
                list.innerHTML = `<p style="text-align: center; color: var(--text-muted); font-size:12px; padding: 20px;">오늘 예정된 보강 운동이 비어있습니다. 라이브러리에서 자유롭게 추가해 보세요!</p>`;
                return;
            }

            appState.routines.forEach((item, index) => {
                let badgeClass = "badge-general";
                if (item.target.includes("코어")) badgeClass = "badge-core";
                else if (item.target.includes("하체") || item.target.includes("둔근") || item.target.includes("햄스트링")) badgeClass = "badge-lower";
                else if (item.target.includes("발목") || item.target.includes("종아리")) badgeClass = "badge-ankle";

                const block = document.createElement('div');
                block.className = `routine-block ${item.checked ? 'completed' : ''}`;
                block.dataset.id = item.id;

                block.innerHTML = `
                    <div class="routine-check">
                        <input type="checkbox" id="check_${item.id}" ${item.checked ? 'checked' : ''}>
                    </div>
                    <div class="routine-details-box">
                        <div class="routine-meta-row">
                            <span class="routine-badge ${badgeClass}">${item.target}</span>
                            <span class="routine-sets-reps">${item.sets} x ${item.reps}</span>
                        </div>
                        <span class="routine-name" id="name_text_${item.id}">${item.name}</span>
                        <span class="routine-tips" id="tips_text_${item.id}">${item.tips}</span>
                    </div>
                    
                    <div class="routine-controls">
                        <button class="ctrl-btn" onclick="moveRoutine(${index}, -1)" title="위로 이동">▲</button>
                        <button class="ctrl-btn" onclick="moveRoutine(${index}, 1)" title="아래로 이동">▼</button>
                        <button class="ctrl-btn" onclick="editRoutineInline(${item.id})" title="상세 편집">✏️</button>
                        <button class="ctrl-btn btn-delete" onclick="deleteRoutine(${item.id})" title="삭제">🗑️</button>
                    </div>
                `;

                const checkbox = block.querySelector('input[type="checkbox"]');
                checkbox.addEventListener('change', (e) => {
                    item.checked = e.target.checked;
                    if (item.checked) {
                        block.classList.add('completed');
                    } else {
                        block.classList.remove('completed');
                    }
                    localStorage.setItem('project330_routines_today', JSON.stringify(appState.routines));
                });

                list.appendChild(block);
            });
        }

        window.moveRoutine = function(index, direction) {
            const targetIndex = index + direction;
            if (targetIndex < 0 || targetIndex >= appState.routines.length) return;

            const temp = appState.routines[index];
            appState.routines[index] = appState.routines[targetIndex];
            appState.routines[targetIndex] = temp;

            localStorage.setItem('project330_routines_today', JSON.stringify(appState.routines));
            renderRoutines();
        };

        window.deleteRoutine = function(id) {
            appState.routines = appState.routines.filter(item => item.id !== id);
            localStorage.setItem('project330_routines_today', JSON.stringify(appState.routines));
            renderRoutines();
        };

        window.editRoutineInline = function(id) {
            const item = appState.routines.find(x => x.id === id);
            if (!item) return;

            const newSets = prompt("세트수를 입력하세요 (예: 3세트):", item.sets);
            if (newSets === null) return;
            const newReps = prompt("반복 횟수 또는 시간을 입력하세요 (예: 15회):", item.reps);
            if (newReps === null) return;
            const newTips = prompt("수행 팁 또는 설명 정보:", item.tips);
            if (newTips === null) return;

            item.sets = newSets || item.sets;
            item.reps = newReps || item.reps;
            item.tips = newTips || item.tips;

            localStorage.setItem('project330_routines_today', JSON.stringify(appState.routines));
            renderRoutines();
        };

        // 8. 노션 보강운동 32종 라이브러리 드롭다운 세팅
        function setupAddExerciseLibrary() {
            const select = document.getElementById('exercise-library-select');
            if (!select) return;

            EXERCISE_LIBRARY.forEach((ex, idx) => {
                const opt = document.createElement('option');
                opt.value = idx;
                opt.textContent = `[${ex.target}] ${ex.name} (${ex.sets} x ${ex.reps})`;
                select.appendChild(opt);
            });
        }

        // 9. 라이브러리 운동 신규 추가 처리
        function confirmAddExercise() {
            const select = document.getElementById('exercise-library-select');
            const val = select.value;
            if (val === "") return;

            const selectedEx = EXERCISE_LIBRARY[parseInt(val)];
            const maxId = appState.routines.reduce((max, item) => item.id > max ? item.id : max, -1);
            
            const newBlock = {
                id: maxId + 1,
                target: selectedEx.target,
                name: selectedEx.name,
                sets: selectedEx.sets,
                reps: selectedEx.reps,
                tips: selectedEx.tips,
                checked: false
            };

            appState.routines.push(newBlock);
            localStorage.setItem('project330_routines_today', JSON.stringify(appState.routines));
            renderRoutines();

            select.value = "";
            document.getElementById('add-routine-drawer').style.display = 'none';
        }

        // 10. API Key 설정 및 모달 관리
        function renderSettingsModal() {
            const input = document.getElementById('api-key-input');
            if (input) {
                input.value = appState.apiKey;
            }
        }

        function toggleSettingsModal(active) {
            const overlay = document.getElementById('settings-overlay');
            if (active) {
                overlay.classList.add('active');
            } else {
                overlay.classList.remove('active');
            }
        }

        // 11. 수정 후 AI 코치 평가받기 (Gemini API 실시간 AJAX 클라이언트 추론)
        async function runAIEvaluation() {
            if (!appState.apiKey) {
                alert("Gemini API Key를 먼저 설정해 주세요! 우측 상단의 ⚙️ 아이콘을 누르면 쉽게 등록할 수 있습니다.");
                toggleSettingsModal(true);
                return;
            }

            const evaluateBtn = document.getElementById('evaluate-btn');
            const loading = document.getElementById('ai-loading');
            
            evaluateBtn.style.display = 'none';
            loading.style.display = 'flex';

            const fatigue = document.getElementById('cond-fatigue').value;
            const pain = document.getElementById('cond-pain').value;
            const notes = document.getElementById('cond-notes').value;

            // 로컬 condition 파일도 시뮬레이션용으로 즉시 UI 동기화
            const formattedPlan = appState.weekPlan.map(p => `요일: ${p.day}요일, 종류: ${p.type}, 목표 거리: ${p.distance}, 강도: ${p.intensity}`).join("\n");
            
            const prompt = `
역할: 전문 마라톤 코치이자 부상 방지 재활 및 임산부/육아 러닝 전문가.
사용자의 배경 정보:
- 러닝 숙련도: 2022년부터 마라톤 풀코스 PR 3시간 46분 24초 보유자. (숙련된 서브 4 러너)
- 미래 목표: 2027년 3월 서울마라톤 풀코스 3시간 30분(Project330) 목표.
- 현실적 제약 및 특별 상황: 2026년 9월 출산 예정. 이후 육아 동반 예정으로, 강도 높은 하드 트레이닝보다는 "부상 없이 여름철을 나며 보강운동을 병행하고 장거리를 소화할 수 있는 튼튼한 하체와 코어 몸 만들기"가 핵심 목표.
- 현재 날짜: ${STATS_DATA.today_date}

사용자가 주간 훈련 계획을 다음과 같이 새롭게 수립/수정하였습니다:
${formattedPlan}

사용자의 현재 건강 컨디션:
- 피로도: ${fatigue}
- 통증 여부: ${pain}
- 메모 및 특이사항: ${notes}

위 상황을 고도로 분석하여 전문 코치로서 수정된 계획이 안전한지, 목표에 부합하는지 꼼꼼하게 평가해 주세요.
반드시 아래 JSON 형식 명칭을 지켜 오직 **순수 JSON**으로만 응답해 주세요. 백틱(markdown block)을 절대로 붙이지 마세요.

출력 JSON 형식:
{
  "coach_comment": "사용자의 피로도, 통증, 오늘 달리기 결과, 그리고 임신/출산 상황을 다정하고 따뜻하게 격려하면서도 수정된 훈련계획의 타당성을 러닝 생리학적으로 분석해주는 3~4줄의 조언",
  "next_running": "수정된 계획과 오늘의 몸 상태에 기초한 다음 목표 훈련 가이드 한 줄 요약 (예: '🏃‍♂️ Next Target: 5km 가벼운 리커버리 조깅 (평균 심박수 135-140 유지)')"
}
`;

            try {
                const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${appState.apiKey}`;
                const response = await fetch(url, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        contents: [{
                            parts: [{
                                text: prompt
                            }]
                        }],
                        generationConfig: {
                            responseMimeType: "application/json"
                        }
                    })
                });

                if (!response.ok) {
                    throw new Error(`Gemini HTTP Error (Status ${response.status})`);
                }

                const result = await response.json();
                let text = result.candidates[0].content.parts[0].text.trim();
                
                if (text.startsWith("```")) {
                    text = text.split("```")[1];
                    if (text.startsWith("json")) {
                        text = text.substring(4);
                    }
                }
                text = text.trim();

                const parsedAI = JSON.parse(text);

                localStorage.setItem('project330_coach_comment', parsedAI.coach_comment);
                localStorage.setItem('project330_next_running', parsedAI.next_running);

                renderDailyRunning();
                alert("🎉 AI 코치님의 주간 계획표 및 당일 컨디션 평가가 성공적으로 업데이트되었습니다!");

            } catch (error) {
                console.error("Gemini AI API Call Failure:", error);
                alert(`⚠️ AI 코치 호출 중 문제가 발생했습니다: ${error.message}\n(API 키를 다시 확인해 보시거나 잠시 후 다시 시도해 주세요)`);
            } finally {
                loading.style.display = 'none';
                evaluateBtn.style.display = 'inline-flex';
            }
        }

        // 12. 전체 클릭 이벤트 처리 바인딩
        function bindEvents() {
            document.getElementById('open-settings-btn').addEventListener('click', () => toggleSettingsModal(true));
            document.getElementById('close-settings-btn').addEventListener('click', () => toggleSettingsModal(false));
            
            document.getElementById('save-settings-btn').addEventListener('click', () => {
                const input = document.getElementById('api-key-input').value.trim();
                appState.apiKey = input;
                localStorage.setItem('gemini_api_key', input);
                alert("Gemini API Key 설정이 저장되었습니다!");
                toggleSettingsModal(false);
            });

            document.getElementById('open-add-routine-btn').addEventListener('click', () => {
                const drawer = document.getElementById('add-routine-drawer');
                drawer.style.display = drawer.style.display === 'block' ? 'none' : 'block';
            });

            document.getElementById('add-exercise-cancel').addEventListener('click', () => {
                document.getElementById('add-routine-drawer').style.display = 'none';
            });
            document.getElementById('add-exercise-confirm').addEventListener('click', confirmAddExercise);

            document.getElementById('evaluate-btn').addEventListener('click', runAIEvaluation);
        }
    </script>
</body>
</html>"""

    # 안전하게 자리채움 문자열 교체 (Escaping 충돌 제로)
    html_content = html_template
    html_content = html_content.replace("__NOW_STR__", now_str)
    html_content = html_content.replace("__TODAY_DATE__", today_date)
    html_content = html_content.replace("__TOTAL_MAY_MILEAGE__", str(stats["total_may_mileage"]))
    html_content = html_content.replace("__TOTAL_WEEKLY_MILEAGE__", str(stats["total_weekly_mileage"]))
    html_content = html_content.replace("__MAY_PROGRESS_PERCENT__", str(min(int(stats["total_may_mileage"] / 200 * 100), 100)))
    html_content = html_content.replace("__WEEK_PROGRESS_PERCENT__", str(min(int(stats["total_weekly_mileage"] / 50 * 100), 100)))
    html_content = html_content.replace("__MAY_CHART_URL__", stats["may_chart_url"])
    html_content = html_content.replace("__WEEK_CHART_URL__", stats["week_chart_url"])
    html_content = html_content.replace("__WEEK_PLAN_JSON__", week_plan_json)
    html_content = html_content.replace("__ROUTINES_JSON__", routines_json)
    html_content = html_content.replace("__STATS_JSON__", stats_json)
    html_content = html_content.replace("__COACH_COMMENT_JSON__", coach_comment_json)
    html_content = html_content.replace("__NEXT_RUNNING_JSON__", next_running_json)
    html_content = html_content.replace("__CONDITION_JSON__", condition_json)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("🎉 [Dashboard] index.html이 성공적으로 생성 및 갱신되었습니다!")

# 7. 메인 실행 흐름
def main():
    print(f"🎬 [Pipeline Start] {now_str} (KST)")
    
    condition = load_condition()
    routines = load_notion_routines()
    
    activities = get_strava_activities()
    stats = calculate_mileage_and_build_charts(activities)
    
    ai_content = get_ai_coaching_content(stats, condition, routines)
    
    build_html_dashboard(stats, ai_content)
    
    print("🏁 [Pipeline End] 대시보드 업데이트 완료.")

if __name__ == "__main__":
    main()