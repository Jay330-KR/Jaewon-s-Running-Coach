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
    """antigravity_master_workout_list_v2.md 또는 notion_routines.md 파일의 내용을 텍스트로 그대로 읽어옵니다."""
    routines_path = "antigravity_master_workout_list_v2.md"
    if not os.path.exists(routines_path):
        routines_path = "notion_routines.md"
        
    if not os.path.exists(routines_path):
        return "사용 가능한 노션 보강운동 루틴 데이터가 없습니다."
    try:
        with open(routines_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"⚠️ [Notion Routines] 로드 중 오류 발생: {e}")
        return "노션 운동 루틴 라이브러리를 불러올 수 없습니다."

def parse_notion_routines_markdown():
    """antigravity_master_workout_list_v2.md 또는 notion_routines.md 파일의 마크다운 표를 파싱하여 JavaScript EXERCISE_LIBRARY 형식의 리스트를 생성합니다."""
    path = "antigravity_master_workout_list_v2.md"
    if not os.path.exists(path):
        path = "notion_routines.md"
        
    if not os.path.exists(path):
        return []
    
    exercises = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        table_started = False
        for line in lines:
            line_str = line.strip()
            if not line_str.startswith("|"):
                continue
            
            parts = [p.strip() for p in line_str.split("|")]
            if len(parts) >= 3 and ("타겟" in parts[1] and "이름" in parts[2]):
                table_started = True
                continue
            if "---" in line_str:
                table_started = True
                continue
                
            if table_started:
                if len(parts) >= 6:
                    target = parts[1]
                    name = parts[2]
                    reps = parts[3]
                    sets = parts[4]
                    tips = parts[5]
                    
                    if not target or not name:
                        continue
                        
                    # Category heuristics mapping:
                    # Base: Stretching, Foam rolling, mobility etc.
                    # Pre-Run: Dynamic warm-ups (Bridges, Sweep, Elephant walk, pigeons etc.)
                    # Workout: Strength-based routines (Plank, Deadbug, Squats, Lunges, Deadlifts etc.)
                    category = "Workout"
                    
                    lower_name = name.lower()
                    lower_tips = tips.lower()
                    lower_target = target.lower()
                    
                    if "stretch" in lower_name or "roller" in lower_name or "mobility" in lower_name or "yoga" in lower_name or "circle" in lower_name or "drill" in lower_name or "setting" in lower_name:
                        if "sweep" in lower_name or "lift" in lower_name or "walk" in lower_name or "kickback" in lower_name or "tap" in lower_name:
                            category = "Pre-Run"
                        else:
                            category = "Base"
                    elif "bridge" in lower_name or "sweep" in lower_name or "walk" in lower_name or "lift" in lower_name or "tap" in lower_name or "kickback" in lower_name:
                        category = "Pre-Run"
                        if "single" in lower_name or "clamshell" in lower_name or "deadbug" in lower_name:
                            category = "Workout"
                    else:
                        category = "Workout"
                        
                    # Hardcoded override patch for original mapping accuracy:
                    if "Landing" in name or "Bounce" in name or "Hopping" in name:
                        if "Double Leg" in name:
                            category = "Pre-Run"
                        else:
                            category = "Workout"
                    elif "Foam Roller" in name or "90/90" in name or "Ankle" in name or "Hamstring Stretch" in name or "Yoga" in name or "Chair" in name or "Drill" in name or "Quad Setting" in name:
                        category = "Base"
                    elif "Bridge" in name or "Sweep" in name or "Elephant Walk" in name or "Pigeon" in name or "Kickback" in name or "Quick Tap" in name or "Dynamic Tap" in name or "Double Leg" in name or "Double Tap" in name:
                        if "Single" in name:
                            category = "Workout"
                        else:
                            category = "Pre-Run"
                            
                    exercises.append({
                        "category": category,
                        "target": target,
                        "name": name,
                        "reps": reps,
                        "sets": sets,
                        "tips": tips
                    })
    except Exception as e:
        print(f"⚠️ [MD Parse] {path} 파싱 실패: {e}")
        
    return exercises

def load_saved_week_plan():
    path = "data/week_plan.json"
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) == 7:
                    print("💾 [DB Load] data/week_plan.json 로드 성공")
                    return data
        except Exception as e:
            print(f"⚠️ [DB Load] data/week_plan.json 로드 중 예외: {e}")
    return None

def load_saved_routines():
    path = "data/routines_today.json"
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    print("💾 [DB Load] data/routines_today.json 로드 성공")
                    return data
        except Exception as e:
            print(f"⚠️ [DB Load] data/routines_today.json 로드 중 예외: {e}")
    return None

def load_saved_coach_comment():
    path = "data/coach_comment.json"
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, str):
                    print("💾 [DB Load] data/coach_comment.json 로드 성공")
                    return data
        except Exception as e:
            print(f"⚠️ [DB Load] data/coach_comment.json 로드 중 예외: {e}")
    return None

def load_saved_next_running():
    path = "data/next_running.json"
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, str):
                    print("💾 [DB Load] data/next_running.json 로드 성공")
                    return data
        except Exception as e:
            print(f"⚠️ [DB Load] data/next_running.json 로드 중 예외: {e}")
    return None

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
    yesterday_date = (now_dt - timedelta(days=1)).strftime("%Y-%m-%d")
    yesterday_run = None
    for act in activities:
        act_date_str = act.get("start_date_local")[:10]
        if act_date_str == today_date:
            today_run = act
        elif act_date_str == yesterday_date:
            yesterday_run = act

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
            }
        }
    }
    may_chart_url = f"https://quickchart.io/chart?c={urllib.parse.quote(json.dumps(may_chart_payload))}&format=png"

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
            }
        }
    }
    week_chart_url = f"https://quickchart.io/chart?c={urllib.parse.quote(json.dumps(week_chart_payload))}&format=png"

    return {
        "total_may_mileage": total_may_mileage,
        "total_weekly_mileage": total_weekly_mileage,
        "may_chart_url": may_chart_url,
        "week_chart_url": week_chart_url,
        "today_run": today_run,
        "yesterday_run": yesterday_run,
        "may_activities": may_activities
    }

# 5. Gemini AI 통합 추론 파이프라인 (보강/스트레칭 3 Tier 및 피드백 루프 지원)
def get_ai_coaching_content(stats, condition, routines):
    """Gemini API를 호출하여 동적인 Week Plan, Next Running, 코칭 코멘트, 오늘의 보강운동 루틴을 큐레이션합니다."""
    
    # 로컬 DB에 이미 보존된 커스텀 상태가 있으면 우선적으로 활용하여 기존 상태 유지
    saved_week_plan = load_saved_week_plan()
    saved_routines = load_saved_routines()
    saved_coach_comment = load_saved_coach_comment()
    saved_next_running = load_saved_next_running()

    if saved_week_plan and saved_routines:
        print("💾 [Pipeline] 사용자의 영구 저장된 커스텀 대시보드 상태를 감지했습니다. 추가 API 호출 없이 기존 상태를 로드합니다.")
        return {
            "week_plan": saved_week_plan,
            "routines": saved_routines,
            "coach_comment": saved_coach_comment or "주간 러닝 일정을 수정한 뒤, 하단의 'AI 코치 평가받기' 버튼을 눌러 피드백을 받아 보세요!",
            "next_running": saved_next_running or "추천 목표가 없습니다. 일정을 편집하고 AI 평가를 진행해 주세요."
        }

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
      "duration": "목표 시간(분) (예: '45', '-' 등)",
      "pace": "목표 페이스 (예: '6\\'00\"', '-' 등)",
      "hr": "목표 심박수 (예: '135', '-' 등)"
    }},
    {{
      "day": "화",
      "type": "훈련 종류",
      "duration": "목표 시간(분)",
      "pace": "목표 페이스",
      "hr": "목표 심박수"
    }},
    {{
      "day": "수",
      "type": "훈련 종류",
      "duration": "목표 시간(분)",
      "pace": "목표 페이스",
      "hr": "목표 심박수"
    }},
    {{
      "day": "목",
      "type": "훈련 종류",
      "duration": "목표 시간(분)",
      "pace": "목표 페이스",
      "hr": "목표 심박수"
    }},
    {{
      "day": "금",
      "type": "훈련 종류",
      "duration": "목표 시간(분)",
      "pace": "목표 페이스",
      "hr": "목표 심박수"
    }},
    {{
      "day": "토",
      "type": "훈련 종류",
      "duration": "목표 시간(분)",
      "pace": "목표 페이스",
      "hr": "목표 심박수"
    }},
    {{
      "day": "일",
      "type": "훈련 종류",
      "duration": "목표 시간(분)",
      "pace": "목표 페이스",
      "hr": "목표 심박수"
    }}
  ],
  "next_running": "오늘의 훈련 결과와 몸 상태에 기반하여 예측한 다음 목표 훈련의 권장 명칭, 타겟 거리 및 목표 심박수 가이드를 담은 한 줄 요약 텍스트 (예: '🏃‍♂️ Next Target: 6km 가벼운 회복 조깅 (평균 심박수 135-140 유지)')",
  "coach_comment": "사용자의 피로도, 통증, 오늘 달리기 결과, 그리고 임신/출산/육아 상황을 다정하고 부드럽게 케어하면서도 러닝 생리학적으로 유익한 지식을 전달하는 따뜻한 조언 3~4줄 (무조건 친절한 반말 혹은 격려의 존댓말 중 격식 있고 따뜻한 어투 사용)",
  "routines": [
    {{
      "category": "운동 분류 ('Base', 'Workout', 'Pre-Run' 중 정확히 하나를 기입. Base는 폼롤러/스트레칭 등 기본 이완, Workout은 근력/기능성 운동, Pre-Run은 러닝 전 웜업/기동성/예열 운동)",
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
    # 23일(토요일) 오후 운동에 집중한 맞춤 훈련 제안 구성
    comment = "토요일 오후 훈련은 내일 일요일의 15km 장거리 지속주(LSD)를 대비하여 몸의 기동성을 예열하고 가벼운 혈류 공급을 유도하는 '다리 텐션 깨우기' 조깅입니다. 피로도가 '하'로 쾌조인 만큼 무리해서 속도를 내지 않고 심박수 135-140의 안전 구역 내에서 달린 뒤, 100m 질주 3회로 런 자세를 조율하면 내일 롱런이 한결 가벼워집니다. 웜업 스트레칭을 철저히 동반해 주세요!"
    next_run = "🏃‍♂️ Next Target (일요일): 15km LSD 장거리 조깅 (심박수 138-145 타겟)"
    
    routines = [
        {"category": "Base", "name": "Foam Roller Set & Stretching", "target": "하체 전반", "reps": "1~2분 (부위별)", "sets": "1세트", "tips": "폼롤러 / 종아리, 중둔근, 대퇴사두 등 후방 사슬 이완 중심"},
        {"category": "Base", "name": "90/90 Stretch", "target": "고관절", "reps": "좌우 각 5회", "sets": "1세트", "tips": "10초 유지 / 고관절 가동성 확보 및 골반 정렬"},
        {"category": "Base", "name": "Ankle Mobility Exercise", "target": "발목", "reps": "12회", "sets": "3세트", "tips": "발목의 전반적인 가동성 확보"},
        {"category": "Pre-Run", "name": "Standing Hamstring Sweep", "target": "후방 사슬", "reps": "좌우 각 15회", "sets": "1세트", "tips": "러닝 전 후방 사슬의 예열 및 동적 신장 확보"},
        {"category": "Pre-Run", "name": "Pigeon Lift (S-Lunge)", "target": "둔근 / 하체", "reps": "좌우 각 10회", "sets": "3세트", "tips": "힌지 포지션 잡고 엉덩이 힘으로 상체 리프트"},
        {"category": "Workout", "name": "Deadbug", "target": "코어", "reps": "10회", "sets": "3세트", "tips": "허리를 바닥에 바짝 밀착하여 골반 전방경사 방지 코어 활성화"},
        {"category": "Workout", "name": "Side Plank + Clamshell", "target": "둔근 (중둔근)", "reps": "좌우 각 12회", "sets": "3세트", "tips": "골반을 확실히 고정하고 엉덩이 측면 중둔근 수축 집중"}
    ]
    
    week_plan = [
        {"day": "월", "type": "완전 휴식", "duration": "-", "pace": "-", "hr": "-"},
        {"day": "화", "type": "이지 조깅", "duration": "45", "pace": "6'00\"", "hr": "135"},
        {"day": "수", "type": "빌드업 조깅", "duration": "50", "pace": "5'45\"", "hr": "142"},
        {"day": "목", "type": "보강 운동", "duration": "-", "pace": "-", "hr": "-"},
        {"day": "금", "type": "지속주 런", "duration": "60", "pace": "5'15\"", "hr": "148"},
        {"day": "토", "type": "조깅 + 질주", "duration": "35", "pace": "5'50\"", "hr": "138"},
        {"day": "일", "type": "주말 장거리", "duration": "90", "pace": "6'15\"", "hr": "140"}
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
    
    # notion_routines.md 동적 파싱 및 직렬화
    parsed_library = parse_notion_routines_markdown()
    exercise_library_json = json.dumps(parsed_library, ensure_ascii=False)
    
    today_weekday_idx = now_dt.weekday()
    start_of_week = (now_dt - timedelta(days=today_weekday_idx)).date()
    end_of_week = start_of_week + timedelta(days=6)
    week_range_str = f"({start_of_week.strftime('%-m.%-d')} ~ {end_of_week.strftime('%-m.%-d')})"

    stats_json = json.dumps({
        "total_may_mileage": stats["total_may_mileage"],
        "total_weekly_mileage": stats["total_weekly_mileage"],
        "today_run": stats["today_run"],
        "yesterday_run": stats["yesterday_run"],
        "may_activities": stats.get("may_activities", []),
        "today_date": today_date,
        "today_weekday_idx": now_dt.weekday(), # 0: Mon, ..., 6: Sun
        "may_chart_url": stats["may_chart_url"],
        "week_chart_url": stats["week_chart_url"],
        "strava_client_id": STRAVA_CLIENT_ID or "",
        "strava_client_secret": STRAVA_CLIENT_SECRET or "",
        "strava_refresh_token": STRAVA_REFRESH_TOKEN or ""
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

        /* Settings & Sync Floating Area */
        .top-actions {
            position: absolute;
            right: 0;
            top: 4px;
            display: flex;
            gap: 8px;
            z-index: 100;
        }
        .settings-btn {
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
        @keyframes rotate {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
        .settings-btn.rotating {
            animation: rotate 1.5s infinite linear;
            pointer-events: none;
            opacity: 0.7;
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
        }

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

        /* AI Run Loop Styling (New) */
        .loop-card {
            background: linear-gradient(135deg, rgba(252, 76, 2, 0.1) 0%, rgba(30, 30, 35, 0.6) 100%);
            border: 1px solid rgba(252, 76, 2, 0.2);
            border-radius: 18px;
            padding: 18px;
            box-shadow: 0 10px 30px rgba(252, 76, 2, 0.08);
            margin-bottom: 20px;
        }

        .loop-step {
            margin-bottom: 14px;
            border-left: 2px solid rgba(255, 255, 255, 0.1);
            padding-left: 12px;
        }
        .loop-step.active {
            border-left-color: var(--primary);
        }

        .loop-step-title {
            font-size: 11px;
            text-transform: uppercase;
            font-weight: 700;
            color: var(--primary);
            letter-spacing: 0.5px;
            margin-bottom: 2px;
        }

        .loop-step-body {
            font-size: 13.5px;
            color: #fff;
            font-weight: 600;
        }
        
        .loop-step-desc {
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 2px;
            line-height: 1.4;
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
            font-size: 13.5px;
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

        /* Upcoming & Previous Recommend Boxes */
        .upcoming-recommend-box {
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

        .previous-recommend-box {
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.03) 0%, rgba(20, 20, 25, 0.4) 100%);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 14px;
            padding: 12px 14px;
            font-size: 13px;
            font-weight: 500;
            color: var(--text-muted);
            margin-top: 12px;
            margin-bottom: 8px;
        }
        
        .upcoming-header, .previous-header {
            font-family: 'Outfit', sans-serif;
            font-weight: 700;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 4px;
        }
        .upcoming-header { color: var(--primary); }
        .previous-header { color: #aaa; }
        
        .upcoming-body, .previous-body {
            font-size: 13.5px;
            font-weight: 600;
            color: #fff;
        }
        .previous-body { color: #ddd; }
        
        .upcoming-detail, .previous-detail {
            font-size: 11.5px;
            color: var(--text-muted);
            margin-top: 2px;
            line-height: 1.4;
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

        /* 3-Tier Routine Sub-Headers */
        .tier-header {
            font-size: 12px;
            text-transform: uppercase;
            font-weight: 800;
            letter-spacing: 0.5px;
            margin-top: 15px;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        
        .tier-header-base { color: #10b981; }
        .tier-header-workout { color: #3b82f6; }
        .tier-header-prerun { color: #fb7185; }

        .routine-container-list {
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-bottom: 12px;
        }

        .routine-block {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 10px 12px;
            position: relative;
            transition: all 0.2s ease;
            display: flex;
            align-items: flex-start;
            gap: 10px;
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
            margin-top: 3px;
            flex-shrink: 0;
        }

        .routine-check input[type="checkbox"] {
            appearance: none;
            -webkit-appearance: none;
            width: 18px;
            height: 18px;
            border: 2px solid var(--text-muted);
            border-radius: 5px;
            outline: none;
            background-color: transparent;
            cursor: pointer;
            display: grid;
            place-content: center;
            transition: all 0.2s ease;
        }

        .routine-check input[type="checkbox"]::before {
            content: "✓";
            font-size: 11px;
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
            margin-bottom: 2px;
        }

        .routine-badge {
            font-size: 8px;
            font-weight: bold;
            padding: 1px 4px;
            border-radius: 3px;
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
            font-size: 13px;
            font-weight: 600;
            color: #fff;
            display: block;
        }

        .routine-tips {
            font-size: 11px;
            color: var(--text-muted);
            margin-top: 3px;
            line-height: 1.35;
            display: block;
        }

        .routine-controls {
            display: flex;
            flex-direction: row;
            gap: 4px;
            margin-left: 6px;
            flex-shrink: 0;
            opacity: 0.2;
            transition: opacity 0.2s ease;
            align-self: center;
        }

        .routine-block:hover .routine-controls {
            opacity: 1;
        }

        .ctrl-btn {
            background: transparent;
            border: none;
            color: var(--text-muted);
            cursor: pointer;
            font-size: 9px;
            display: flex;
            align-items: center;
            justify-content: center;
            width: 16px;
            height: 16px;
            border-radius: 3px;
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

        /* Loading Spinner & Skeleton */
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

        @keyframes skeleton-pulse {
            0% { opacity: 0.6; }
            50% { opacity: 0.3; }
            100% { opacity: 0.6; }
        }
        .skeleton-loading {
            animation: skeleton-pulse 1.5s infinite ease-in-out;
            color: transparent !important;
            background: linear-gradient(90deg, rgba(255,255,255,0.03) 25%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.03) 75%) !important;
            background-size: 200% 100% !important;
            border-radius: 8px;
            min-height: 48px;
        }

        /* Inline Exercise Library Drawer */
        .add-routine-drawer-inline {
            margin-top: 4px;
            background: rgba(0, 0, 0, 0.2);
            border: 1px dashed rgba(255,255,255,0.05);
            border-radius: 10px;
            padding: 8px;
            animation: slideDown 0.2s ease-out;
        }

        @keyframes slideDown {
            from { opacity: 0; transform: translateY(-5px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .add-routine-drawer-inline select {
            background: #1e1e24;
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: #fff;
            border-radius: 5px;
            padding: 5px;
            font-size: 11px;
            outline: none;
            width: 100%;
            cursor: pointer;
            margin-bottom: 6px;
        }

        /* Monthly Heart Rate Zone Tracking Styles */
        .zone-tracking-card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 16px;
            margin-bottom: 20px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.2);
        }
        .zone-bar-row {
            margin-bottom: 12px;
        }
        .zone-bar-row:last-child {
            margin-bottom: 0;
        }
        .zone-label-group {
            display: flex;
            justify-content: space-between;
            font-size: 11px;
            margin-bottom: 4px;
        }
        .zone-name {
            font-weight: bold;
        }
        .zone-percentage {
            color: var(--text-muted);
        }
        .zone-progress-bg {
            height: 8px;
            background: rgba(255,255,255,0.05);
            border-radius: 99px;
            overflow: hidden;
            position: relative;
        }
        .zone-progress-fill {
            height: 100%;
            border-radius: 99px;
            transition: width 1s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .zone-color-5 { background: linear-gradient(90deg, #ef4444, #b91c1c); }
        .zone-color-4 { background: linear-gradient(90deg, #f97316, #c2410c); }
        .zone-color-3 { background: linear-gradient(90deg, #eab308, #a16207); }
        .zone-color-2 { background: linear-gradient(90deg, #10b981, #047857); }
        .zone-color-1 { background: linear-gradient(90deg, #3b82f6, #1d4ed8); }

        /* Monthly Calendar DB Styles */
        .calendar-card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 16px;
            margin-bottom: 20px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.2);
        }
        .calendar-header-days {
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            gap: 4px;
            text-align: center;
            font-size: 10px;
            font-weight: bold;
            color: var(--primary);
            margin-bottom: 8px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            padding-bottom: 4px;
        }
        .calendar-grid {
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            gap: 6px;
        }
        .calendar-day {
            aspect-ratio: 1;
            background: rgba(255,255,255,0.02);
            border: 1px solid rgba(255,255,255,0.04);
            border-radius: 8px;
            padding: 4px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
            transition: all 0.2s ease;
            position: relative;
        }
        .calendar-day:hover {
            background: rgba(252, 76, 2, 0.15);
            border-color: var(--primary);
            transform: translateY(-2px);
        }
        .calendar-day.empty {
            visibility: hidden;
            cursor: default;
        }
        .calendar-day.today {
            border: 1.5px solid var(--primary);
            box-shadow: 0 0 10px var(--primary-glow);
            background: rgba(252, 76, 2, 0.08);
        }
        .calendar-day.has-run {
            background: rgba(16, 185, 129, 0.08);
            border-color: rgba(16, 185, 129, 0.3);
        }
        .calendar-day.has-run:hover {
            background: rgba(16, 185, 129, 0.2);
            border-color: #10b981;
        }
        .day-number {
            font-size: 9px;
            font-weight: bold;
            color: var(--text-muted);
            align-self: flex-start;
        }
        .calendar-day.today .day-number {
            color: var(--primary);
        }
        .day-icon {
            font-size: 10px;
            margin: 1px 0;
        }
        .day-dist {
            font-size: 8px;
            font-weight: bold;
            color: #10b981;
            transform: scale(0.9);
        }
        .calendar-details-card {
            background: rgba(30, 30, 35, 0.7);
            border: 1px solid var(--primary);
            border-radius: 16px;
            padding: 16px;
            margin-top: -12px;
            margin-bottom: 20px;
            box-shadow: 0 8px 32px rgba(252,76,2,0.15);
            animation: slideDown 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        @keyframes slideDown {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .details-title {
            font-size: 13px;
            font-weight: bold;
            color: var(--primary);
            border-bottom: 1px solid rgba(255,255,255,0.08);
            padding-bottom: 6px;
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
        }
        .details-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
            font-size: 11px;
            margin-bottom: 10px;
        }
        .details-item {
            background: rgba(255,255,255,0.03);
            padding: 6px 10px;
            border-radius: 6px;
            border: 1px solid rgba(255,255,255,0.04);
        }
        .details-label {
            color: var(--text-muted);
            font-size: 9px;
        }
        .details-val {
            font-weight: bold;
        }
        .details-feedback {
            font-size: 11px;
            background: rgba(252,76,2,0.05);
            padding: 10px;
            border-radius: 8px;
            border-left: 3px solid var(--primary);
            line-height: 1.5;
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
        <!-- Settings & Sync Buttons -->
        <div class="top-actions">
            <button class="settings-btn" id="sync-refresh-btn" title="Strava 실적 동기화 및 대시보드 리프레시">🔄</button>
            <button class="settings-btn" id="open-settings-btn" title="AI 및 Strava 연동 설정">⚙️</button>
        </div>

        <!-- Header -->
        <header>
            <div class="brand">🏃‍♂️ Project <span>330</span></div>
            <div class="sync-time">
                <span class="sync-pulse"></span>
                <span>Last Sync: __NOW_STR__ (KST)</span>
            </div>
        </header>

        <!-- Section 1 & 2: Mileage Progress -->
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

        <!-- Section 3: Monthly Heart Rate Zone Tracking (월간 존 트래킹) -->
        <section>
            <h2>💓 Monthly Heart Rate Zone Tracking (월간 심박 존 분배)</h2>
            <div class="zone-tracking-card" id="zone-tracking-card-container">
                <!-- JS로 동적 렌더링 -->
            </div>
        </section>

        <!-- Section 4: Monthly DB (월간 훈련 캘린더) -->
        <section>
            <h2>📅 Monthly DB (월간 훈련 캘린더)</h2>
            <div class="calendar-card">
                <div class="calendar-header-days">
                    <div>월</div><div>화</div><div>수</div><div>목</div><div>금</div><div>토</div><div>일</div>
                </div>
                <div class="calendar-grid" id="calendar-grid-container">
                    <!-- JS로 달력 일자 렌더링 -->
                </div>
            </div>
            <!-- 달력 상세 정보 패널 -->
            <div id="calendar-details-panel" class="calendar-details-card" style="display: none;">
                <!-- JS로 선택일 상세 데이터 렌더링 -->
            </div>
        </section>

        <!-- Section 5: Week Plan (주간 러닝 계획) -->
        <section>
            <h2>📅 Week Plan (주간 러닝 계획) <span style="font-size:12px; font-weight:normal; color:var(--text-muted); margin-left:6px;">__WEEK_RANGE_STR__</span></h2>
            <div class="week-plan-card">
                <table class="week-table" id="week-plan-table">
                    <thead>
                        <tr style="border-bottom:1px solid #444; color: var(--primary);">
                            <th style="width: 15%;">요일</th>
                            <th style="width: 25%;">타입</th>
                            <th style="width: 20%;">시간(분)</th>
                            <th style="width: 20%;">페이스</th>
                            <th style="width: 20%;">심박</th>
                        </tr>
                    </thead>
                    <tbody id="week-plan-tbody">
                        <!-- JS로 렌더링 -->
                    </tbody>
                </table>
            </div>
        </section>

        <!-- Section 6: 데일리 러닝 피드백 (Daily feedback, stats, comments, prev/upcoming & Condition Editor) -->
        <section>
            <h2>🏃‍♂️ Daily Running Feedback (<span id="today-date-header">__TODAY_DATE__</span>)</h2>
            
            <!-- AI Coaching Loop Card -->
            <div class="loop-card" style="margin-bottom: 15px;">
                <div class="loop-step active">
                    <div class="loop-step-title">1단계: 오늘 오후 권장 훈련 (AI Recommend)</div>
                    <div class="loop-step-body" id="loop-recommend-title">로딩 중...</div>
                    <div class="loop-step-desc" id="loop-recommend-desc">주간 계획표를 기반으로 한 코치 추천 훈련입니다.</div>
                </div>
                <div class="loop-step" id="loop-step-strava">
                    <div class="loop-step-title">2단계: 오늘 러닝 실적 연동 (Strava Run Sync)</div>
                    <div class="loop-step-body" id="loop-strava-title">연동 대기 중</div>
                    <div class="loop-step-desc" id="loop-strava-desc">러닝 실적이 자동으로 연동되면 녹색 활성 상태로 변경됩니다.</div>
                </div>
                <div class="loop-step" id="loop-step-analysis">
                    <div class="loop-step-title">3단계: AI 피드백 & 다음 러닝 목표 (AI Analysis)</div>
                    <div class="loop-step-body" id="loop-next-recommend-title">대기 중</div>
                    <div class="loop-step-desc" id="loop-next-recommend-desc">달리기 기록 연동 완료 후 AI가 내일을 위한 최적의 훈련을 갱신합니다.</div>
                </div>
            </div>

            <!-- Daily Running Stats Container -->
            <div id="daily-running-container" style="margin-bottom: 15px;">
                <!-- JS로 렌더링 -->
            </div>

            <!-- AI Coach Comment Box -->
            <div class="coach-comment-box" style="margin-bottom: 15px;">
                <div class="comment-header">📋 AI COACH'S COMMENT</div>
                <div id="coach-comment-content">
                    <!-- JS로 바인딩 -->
                </div>
            </div>

            <!-- Previous Running (어제 실적 및 계획 대비 분석) -->
            <div class="previous-recommend-box" id="previous-running-content" style="display: none; margin-bottom: 15px;">
                <!-- JS로 바인딩 -->
            </div>

            <!-- Upcoming Running (내일 예정 훈련) -->
            <div class="upcoming-recommend-box" id="next-running-content" style="margin-bottom: 15px;">
                <!-- JS로 바인딩 -->
            </div>

            <!-- Condition Editor Inside Section 6 -->
            <div class="condition-editor-card">
                <div style="font-size: 11px; font-weight: bold; color: var(--primary); margin-bottom: 8px;">🧠 몸 상태 정보 갱신</div>
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
                <div style="display: flex; gap: 8px;">
                    <button class="btn" id="evaluate-btn" style="flex: 3; margin-top: 0;">
                        <span>✨ 수정 후 AI 코치 평가받기</span>
                    </button>
                    <button class="btn btn-secondary" id="reset-coaching-btn" style="flex: 1; margin-top: 0;" title="초기 코치 제안으로 되돌리기">
                        <span>🔄 초기화</span>
                    </button>
                </div>
                <div class="spinner-container" id="ai-loading">
                    <div class="spinner"></div>
                    <div class="spinner-text">AI 코치가 몸 상태를 고려하여 일정을 재구성하고 있습니다...</div>
                </div>
            </div>
        </section>

        <!-- Section 7: Routine For Today (보강운동 세트) -->
        <section>
            <h2>🧘‍♂️ Routine For Today (보강운동 세트)</h2>
            <div class="progress-card" style="padding: 12px; margin-bottom: 20px;">
                <!-- 1. Base Tier -->
                <div class="tier-header tier-header-base">
                    <span>🟢 Base (기본 이완 & 안정화)</span>
                    <button class="ctrl-btn" onclick="toggleAddDrawer('Base')" style="font-size:11px; width:auto; height:auto; color:#10b981; font-weight:bold;">➕ 추가</button>
                </div>
                <div class="add-routine-drawer-inline" id="add-drawer-Base" style="display:none;">
                    <select id="select-Base"></select>
                    <div style="display:flex; gap:6px;">
                        <button class="btn" onclick="addExerciseInline('Base')" style="margin-top:0; padding:4px; font-size:10px; flex:1;">추가 확정</button>
                        <button class="btn btn-secondary" onclick="toggleAddDrawer('Base')" style="margin-top:0; padding:4px; font-size:10px; flex:1;">취소</button>
                    </div>
                </div>
                <div id="routine-list-Base" class="routine-container-list"></div>

                <!-- 2. Workout Tier -->
                <div class="tier-header tier-header-workout">
                    <span>⚡ Workout (근력 & 기능성 훈련)</span>
                    <button class="ctrl-btn" onclick="toggleAddDrawer('Workout')" style="font-size:11px; width:auto; height:auto; color:#3b82f6; font-weight:bold;">➕ 추가</button>
                </div>
                <div class="add-routine-drawer-inline" id="add-drawer-Workout" style="display:none;">
                    <select id="select-Workout"></select>
                    <div style="display:flex; gap:6px;">
                        <button class="btn" onclick="addExerciseInline('Workout')" style="margin-top:0; padding:4px; font-size:10px; flex:1;">추가 확정</button>
                        <button class="btn btn-secondary" onclick="toggleAddDrawer('Workout')" style="margin-top:0; padding:4px; font-size:10px; flex:1;">취소</button>
                    </div>
                </div>
                <div id="routine-list-Workout" class="routine-container-list"></div>

                <!-- 3. Pre-Run Tier -->
                <div class="tier-header tier-header-prerun">
                    <span>🏃‍♂️ Pre-Run (러닝 직전 예열 & 활성화)</span>
                    <button class="ctrl-btn" onclick="toggleAddDrawer('Pre-Run')" style="font-size:11px; width:auto; height:auto; color:#fb7185; font-weight:bold;">➕ 추가</button>
                </div>
                <div class="add-routine-drawer-inline" id="add-drawer-Pre-Run" style="display:none;">
                    <select id="select-Pre-Run"></select>
                    <div style="display:flex; gap:6px;">
                        <button class="btn" onclick="addExerciseInline('Pre-Run')" style="margin-top:0; padding:4px; font-size:10px; flex:1;">추가 확정</button>
                        <button class="btn btn-secondary" onclick="toggleAddDrawer('Pre-Run')" style="margin-top:0; padding:4px; font-size:10px; flex:1;">취소</button>
                    </div>
                </div>
                <div id="routine-list-Pre-Run" class="routine-container-list"></div>
            </div>
        </section>

        <!-- Footer -->
        <footer>
            <p>Automated with Strava API & Gemini 2.0 & QuickChart</p>
            <p style="margin-top: 4px;">Designed by Antigravity for <a href="https://github.com/Jay330-KR/Jaewon-s-Running-Coach" target="_blank">Project330</a></p>
        </footer>
    </div>

    <!-- API Key & Strava Settings Modal -->
    <div class="overlay" id="settings-overlay">
        <div class="modal" style="max-width: 450px;">
            <div class="modal-header">
                <span>🔑 연동 및 API 설정 (Settings)</span>
                <button class="modal-close" id="close-settings-btn">&times;</button>
            </div>
            <div class="modal-body" style="display: flex; flex-direction: column; gap: 10px;">
                <p style="font-size: 12px; line-height: 1.4; color: #ddd; margin-bottom: 5px;">
                    대시보드와 AI 코칭 및 Strava 연동을 위한 설정입니다. 저장 시 로컬 서버의 <code>.env</code> 파일에 영구 기록됩니다.
                </p>
                
                <div>
                    <label style="font-size: 11px; color: var(--text-muted); font-weight: bold; margin-bottom: 2px; display: block;">GEMINI API KEY</label>
                    <input type="password" id="api-key-input" placeholder="AIzaSy..." style="width: 100%;" />
                </div>
                
                <div style="border-top: 1px solid rgba(255,255,255,0.08); padding-top: 8px; margin-top: 4px;">
                    <label style="font-size: 11px; color: var(--primary); font-weight: bold; margin-bottom: 2px; display: block;">STRAVA CLIENT ID</label>
                    <input type="text" id="strava-client-id-input" placeholder="248357" style="width: 100%;" />
                </div>
                
                <div>
                    <label style="font-size: 11px; color: var(--primary); font-weight: bold; margin-bottom: 2px; display: block;">STRAVA CLIENT SECRET</label>
                    <input type="password" id="strava-client-secret-input" placeholder="c56f555bb41..." style="width: 100%;" />
                </div>
                
                <div>
                    <label style="font-size: 11px; color: var(--primary); font-weight: bold; margin-bottom: 2px; display: block;">STRAVA REFRESH TOKEN</label>
                    <input type="password" id="strava-refresh-token-input" placeholder="토큰 입력..." style="width: 100%;" />
                    <span style="font-size: 10px; color: var(--text-muted); display: block; margin-top: 2px;">
                        💡 비어있을 경우 데모 데이터로 구동됩니다. 토큰 발급은 <code>get_strava_tokens.py</code>를 실행하세요.
                    </span>
                </div>
                
                <button class="btn" id="save-settings-btn" style="margin-top: 10px;">설정 저장</button>
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

        // 32종의 노션 보강운동 라이브러리 전체 데이터 (category가 완벽히 매핑됨)
        const DYNAMIC_EXERCISE_LIBRARY = __EXERCISE_LIBRARY_JSON__;
        const BACKUP_EXERCISE_LIBRARY = [
            { "category": "Base", "target": "하체 전반", "name": "Foam Roller Set & Stretching", "reps": "1~2분 (부위별)", "sets": "1세트", "tips": "폼롤러 / 종아리, 중둔근, 대퇴사두 등 이완 중심" },
            { "category": "Workout", "target": "코어", "name": "Deadbug", "reps": "10회", "sets": "3세트", "tips": "허리를 바닥에 강하게 밀착하여 코어 재건 / 어깨 석회 통증 주의" },
            { "category": "Workout", "target": "둔근 (중둔근)", "name": "Side Plank + Clamshell", "reps": "좌우 각 12회", "sets": "3세트", "tips": "골반 고정, 엉덩이 옆쪽 중둔근 자극 확인" },
            { "category": "Workout", "target": "둔근", "name": "Single Leg Hip Bridge", "reps": "각 10회", "sets": "3세트", "tips": "든 다리 골반이 처지지 않게 수평 유지" },
            { "category": "Workout", "target": "종아리 / 발목", "name": "Eccentric Calf Raise", "reps": "15회", "sets": "3세트", "tips": "5초 동안 소리 없이 천천히 뒤꿈치 내리기" },
            { "category": "Base", "target": "고관절", "name": "90/90 Stretch", "reps": "좌우 각 5회", "sets": "1세트", "tips": "10초 유지 / 고관절 가동성 확보 및 골반 정렬" },
            { "category": "Base", "target": "발목", "name": "Ankle Mobility Exercise", "reps": "12회", "sets": "3세트", "tips": "발목의 전반적인 가동성 확보" },
            { "category": "Base", "target": "햄스트링", "name": "Hamstring Stretch", "reps": "각 1분", "sets": "2세트", "tips": "반동 없이 길게 늘려 후방 사슬 이완" },
            { "category": "Pre-Run", "target": "둔근", "name": "Hip Bridge", "reps": "12회", "sets": "3세트", "tips": "골반 수평 유지 및 둔근 시동 (신경계 활성화)" },
            { "category": "Workout", "target": "후방 사슬", "name": "Romanian Deadlift", "reps": "10~15회", "sets": "3세트", "tips": "저중량으로 힙힌지 감각 각인 (무릎 고정, 엉덩이 멀리)" },
            { "category": "Workout", "target": "하체 / 편측성", "name": "Split Squat", "reps": "각 8회", "sets": "3세트", "tips": "무릎이 안으로 굽지 않게 외회전 토크 유지" },
            { "category": "Workout", "target": "하체 / 둔근", "name": "Backward Lunge", "reps": "각 8회", "sets": "3세트", "tips": "덤벨 활용 편측성 훈련" },
            { "category": "Workout", "target": "하체 전반", "name": "Goblet Squat", "reps": "12회", "sets": "3세트", "tips": "무릎을 바깥으로 밀어내며 엉덩이 강한 자극" },
            { "category": "Workout", "target": "하체 전반", "name": "Weighted Squat", "reps": "12회", "sets": "5세트", "tips": "점진적 과부하 트레이닝" },
            { "category": "Base", "target": "발바닥 / 아치", "name": "Toe Yoga", "reps": "좌우 각 10회", "sets": "3세트", "tips": "발바닥 고유수용감각 촉진 및 아치 활성화" },
            { "category": "Pre-Run", "target": "둔근 / 하체", "name": "Pigeon Lift (S-Lunge)", "reps": "좌우 각 10회", "sets": "3세트", "tips": "힌지 포지션 잡고 엉덩이 힘으로 상체 리프트" },
            { "category": "Pre-Run", "target": "햄스트링", "name": "Elephant Walk", "reps": "10~20회", "sets": "2세트", "tips": "햄스트링 가벼운 동적 가동성 확보" },
            { "category": "Base", "target": "고관절", "name": "Hip Chair Circle", "reps": "좌우 각 15회", "sets": "1세트", "tips": "의자 활용 / 고관절 소켓을 부드럽게 열어주기" },
            { "category": "Pre-Run", "target": "후방 사슬", "name": "Standing Hamstring Sweep", "reps": "좌우 각 15회", "sets": "1세트", "tips": "메인 운동 전 후방 사슬 예열" },
            { "category": "Workout", "target": "하체 / 내전근", "name": "Cossack Squat Hold", "reps": "좌우 각 3회", "sets": "1세트", "tips": "10초 정지 / 내전근 능동 활성화" },
            { "category": "Pre-Run", "target": "둔근", "name": "Kickback", "reps": "좌우 각 10회", "sets": "3세트", "tips": "둔근 활성 및 러닝 보행 동작 연동" },
            { "category": "Base", "target": "무릎 / 발목", "name": "Tibial Rotation Drill", "reps": "15회", "sets": "3세트", "tips": "무릎 고정하고 정강이뼈만 회전 훈련" },
            { "category": "Base", "target": "대퇴사두", "name": "Foam Roller Quad Setting", "reps": "12회", "sets": "3세트", "tips": "오금으로 짓누르며 허벅지 내측광근 수축" },
            { "category": "Workout", "target": "대퇴사두", "name": "Internal Rotation Extension", "reps": "12회", "sets": "3세트", "tips": "내회전 상태로 편측 저항 버티며 내리기" },
            { "category": "Workout", "target": "무릎 결합조직", "name": "Lean Forward Isometric Hold", "reps": "20초", "sets": "3세트", "tips": "뒤꿈치 든 채 정적 버티기" },
            { "category": "Workout", "target": "하체 협응력", "name": "Bosu Ball Tap & Hold", "reps": "10회", "sets": "3세트", "tips": "불안정한 지면 딛고 발바닥 미세 제어" },
            { "category": "Workout", "target": "둔근 / 하체", "name": "Band Diagonal Kickback", "reps": "좌우 각 12회", "sets": "3세트", "tips": "루프 밴드로 엉덩이 측면 및 뒤 활성" },
            { "category": "Workout", "target": "하체 / 고관절", "name": "Band Monster Walk", "reps": "사방 10걸음", "sets": "3세트", "tips": "밴드 착용 상태로 사방 걷기" },
            { "category": "Workout", "target": "장요근 / 고관절", "name": "Band Hip Flexor Lift", "reps": "좌우 각 12회", "sets": "3세트", "tips": "고관절 및 장요근 굴곡력 강화" },
            { "category": "Workout", "target": "플라이오메트릭", "name": "Skate Drill & Landing", "reps": "좌우 각 8회", "sets": "3세트", "tips": "양발 랜딩 후 한발 도약 측면 점프" },
            { "category": "Workout", "target": "전신 / 코어", "name": "Forward Lean Walk with Waterbag", "reps": "15걸음", "sets": "3세트", "tips": "워터백 부하 저항 극복 전진" },
            { "category": "Pre-Run", "target": "발목 / 민첩성", "name": "Plate Quick Tap", "reps": "좌우 각 15회", "sets": "3세트", "tips": "원판 빠르게 찍고 복귀 발목 탄성 제어" }
        ];
        const EXERCISE_LIBRARY = DYNAMIC_EXERCISE_LIBRARY && DYNAMIC_EXERCISE_LIBRARY.length > 0 ? DYNAMIC_EXERCISE_LIBRARY : BACKUP_EXERCISE_LIBRARY;

        // 2. 어플리케이션 상태(State) 관리 객체
        let appState = {
            weekPlan: [],
            routines: [],
            apiKey: ""
        };

        const getBackendUrl = (path) => {
            // 깃허브 원격 호스팅 페이지에서도 로컬에서 돌아가는 8000 포트 서버와 통신하도록 주소 고정
            return `http://localhost:8000${path}`;
        };

        async function saveStateToBackend() {
            const fatigue = document.getElementById('cond-fatigue').value;
            const pain = document.getElementById('cond-pain').value;
            const notes = document.getElementById('cond-notes').value;

            const payload = {
                week_plan: appState.weekPlan,
                routines: appState.routines,
                condition: {
                    fatigue: fatigue,
                    pain: pain,
                    notes: notes
                },
                coach_comment: localStorage.getItem('project330_coach_comment') || INITIAL_COACH_COMMENT,
                next_running: localStorage.getItem('project330_next_running') || INITIAL_NEXT_RUNNING
            };

            try {
                const response = await fetch(getBackendUrl('/api/save'), {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(payload)
                });
                if (!response.ok) {
                    console.warn("Failed to auto-save to backend server.");
                } else {
                    console.log("State auto-saved to backend server successfully.");
                }
            } catch(e) {
                console.warn("Error auto-saving state to backend:", e);
            }
        }

        // 3. 초기화 실행
        document.addEventListener('DOMContentLoaded', () => {
            checkWeeklyReset();
            initAppState();
            renderSettingsModal();
            renderWeekPlanTable();
            renderZoneTracking();
            renderCalendarDB();
            renderDailyRunning();
            renderRoutines();
            setupAddExerciseLibrary();
            bindEvents();
        });

        // Sunday 11:00 PM KST reset checker
        function checkWeeklyReset() {
            try {
                const now = new Date();
                const utc = now.getTime() + (now.getTimezoneOffset() * 60000);
                const kstNow = new Date(utc + (3600000 * 9));
                
                const currentDay = kstNow.getDay(); 
                const daysToSunday = currentDay === 0 ? 0 : 7 - currentDay;
                
                const sundayReset = new Date(kstNow);
                sundayReset.setDate(kstNow.getDate() + daysToSunday);
                sundayReset.setHours(23, 0, 0, 0); 
                
                const weekId = sundayReset.toISOString().slice(0, 10);
                
                if (kstNow.getTime() >= sundayReset.getTime()) {
                    const lastReset = localStorage.getItem('project330_last_reset_week');
                    if (lastReset !== weekId) {
                        console.log("Weekly plan KST reset triggered at Sunday 11 PM KST.");
                        localStorage.setItem('project330_last_reset_week', weekId);
                        
                        localStorage.removeItem('project330_week_plan');
                        localStorage.removeItem('project330_routines_today');
                        localStorage.removeItem('project330_coach_comment');
                        localStorage.removeItem('project330_next_running');
                        
                        fetch('/api/reset')
                            .then(() => {
                                console.log("Backend weekly plan cache reset successful.");
                                location.reload();
                            })
                            .catch(e => {
                                console.warn("Error resetting backend:", e);
                                location.reload();
                            });
                    }
                }
            } catch (e) {
                console.warn("Error running weekly reset check:", e);
            }
        }

        // 상태 초기화 (localStorage 우선 로드, 안전 파싱 가드 내장)
        function initAppState() {
            appState.apiKey = localStorage.getItem('gemini_api_key') || "";
            if (!appState.apiKey && window.LOCAL_GEMINI_API_KEY) {
                appState.apiKey = window.LOCAL_GEMINI_API_KEY;
                localStorage.setItem('gemini_api_key', appState.apiKey);
            }

            // 주간 계획 캐시 파싱 검증 (legacy 스트링 무력화 가드)
            const cachedWeekPlan = localStorage.getItem('project330_week_plan');
            if (cachedWeekPlan && cachedWeekPlan.startsWith('[')) {
                try {
                    appState.weekPlan = JSON.parse(cachedWeekPlan);
                } catch(e) {
                    appState.weekPlan = INITIAL_WEEK_PLAN;
                }
            } else {
                appState.weekPlan = INITIAL_WEEK_PLAN;
                localStorage.setItem('project330_week_plan', JSON.stringify(appState.weekPlan));
            }

            // 보강운동 루틴 파싱 검증 (legacy 스트링 무력화 가드)
            const cachedRoutines = localStorage.getItem('project330_routines_today');
            if (cachedRoutines && cachedRoutines.startsWith('[')) {
                try {
                    appState.routines = JSON.parse(cachedRoutines);
                } catch(e) {
                    appState.routines = INITIAL_ROUTINES.map((item, idx) => ({ ...item, id: idx, checked: false }));
                }
            } else {
                appState.routines = INITIAL_ROUTINES.map((item, idx) => ({ ...item, id: idx, checked: false }));
                localStorage.setItem('project330_routines_today', JSON.stringify(appState.routines));
            }

            // 몸 상태 UI 세팅
            document.getElementById('cond-fatigue').value = CONDITION_DATA.피로도 || "하";
            document.getElementById('cond-pain').value = CONDITION_DATA.통증 || "없음";
            document.getElementById('cond-notes').value = CONDITION_DATA.기타 || "";
        }

        // 4. Weekly Plan 테이블 렌더러
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
                        <input type="text" value="${plan.type || '-'}" class="week-edit-input" data-idx="${index}" data-field="type" />
                    </td>
                    <td>
                        <input type="text" value="${plan.duration || '-'}" class="week-edit-input" data-idx="${index}" data-field="duration" style="width: 90%; text-align: center;" />
                    </td>
                    <td>
                        <input type="text" value="${plan.pace || '-'}" class="week-edit-input" data-idx="${index}" data-field="pace" style="width: 90%; text-align: center;" />
                    </td>
                    <td>
                        <input type="text" value="${plan.hr || '-'}" class="week-edit-input" data-idx="${index}" data-field="hr" style="width: 90%; text-align: center;" />
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
                    saveStateToBackend();
                    runAIEvaluation(true);
                });
            });
        }

        // 4.1 Monthly Cardiac HR Zone Tracking 렌더러
        function renderZoneTracking() {
            const container = document.getElementById('zone-tracking-card-container');
            if (!container) return;

            let zones = { z1: 0, z2: 0, z3: 0, z4: 0, z5: 0 };
            const activities = STATS_DATA.may_activities || [];

            if (activities.length === 0) {
                zones = { z1: 20, z2: 120, z3: 90, z4: 45, z5: 15 };
            } else {
                activities.forEach(act => {
                    const durationMin = (act.moving_time || act.elapsed_time || 0) / 60;
                    const avgHR = act.average_heartrate;

                    if (avgHR) {
                        if (avgHR >= 165) {
                            zones.z5 += durationMin;
                        } else if (avgHR >= 150) {
                            zones.z4 += durationMin;
                        } else if (avgHR >= 140) {
                            zones.z3 += durationMin;
                        } else if (avgHR >= 130) {
                            zones.z2 += durationMin;
                        } else {
                            zones.z1 += durationMin;
                        }
                    } else {
                        const name = (act.name || "").toLowerCase();
                        if (name.includes("lsd") || name.includes("long") || name.includes("장거리")) {
                            zones.z2 += durationMin * 0.7;
                            zones.z3 += durationMin * 0.3;
                        } else if (name.includes("interval") || name.includes("speed") || name.includes("인터벌")) {
                            zones.z4 += durationMin * 0.4;
                            zones.z5 += durationMin * 0.6;
                        } else if (name.includes("tempo") || name.includes("build") || name.includes("지속주")) {
                            zones.z3 += durationMin * 0.6;
                            zones.z4 += durationMin * 0.4;
                        } else {
                            zones.z2 += durationMin * 0.8;
                            zones.z1 += durationMin * 0.2;
                        }
                    }
                });
            }

            const totalMin = zones.z1 + zones.z2 + zones.z3 + zones.z4 + zones.z5;
            const pct = (val) => totalMin > 0 ? Math.round((val / totalMin) * 100) : 0;

            container.innerHTML = `
                <div class="zone-bar-row">
                    <div class="zone-label-group">
                        <span class="zone-name" style="color: #ef4444;">Zone 5 (무산소 / 고강도 인터벌)</span>
                        <span class="zone-percentage">${pct(zones.z5)}% (${Math.round(zones.z5)}분)</span>
                    </div>
                    <div class="zone-progress-bg">
                        <div class="zone-progress-fill zone-color-5" style="width: ${pct(zones.z5)}%;"></div>
                    </div>
                </div>
                <div class="zone-bar-row">
                    <div class="zone-label-group">
                        <span class="zone-name" style="color: #f97316;">Zone 4 (젖산역치 / 페이스주)</span>
                        <span class="zone-percentage">${pct(zones.z4)}% (${Math.round(zones.z4)}분)</span>
                    </div>
                    <div class="zone-progress-bg">
                        <div class="zone-progress-fill zone-color-4" style="width: ${pct(zones.z4)}%;"></div>
                    </div>
                </div>
                <div class="zone-bar-row">
                    <div class="zone-label-group">
                        <span class="zone-name" style="color: #eab308;">Zone 3 (유산소 템포 / 빌드업)</span>
                        <span class="zone-percentage">${pct(zones.z3)}% (${Math.round(zones.z3)}분)</span>
                    </div>
                    <div class="zone-progress-bg">
                        <div class="zone-progress-fill zone-color-3" style="width: ${pct(zones.z3)}%;"></div>
                    </div>
                </div>
                <div class="zone-bar-row">
                    <div class="zone-label-group">
                        <span class="zone-name" style="color: #10b981;">Zone 2 (기초 유산소 / 이지 조깅)</span>
                        <span class="zone-percentage">${pct(zones.z2)}% (${Math.round(zones.z2)}분)</span>
                    </div>
                    <div class="zone-progress-bg">
                        <div class="zone-progress-fill zone-color-2" style="width: ${pct(zones.z2)}%;"></div>
                    </div>
                </div>
                <div class="zone-bar-row">
                    <div class="zone-label-group">
                        <span class="zone-name" style="color: #3b82f6;">Zone 1 (회복 러닝 / 웜업)</span>
                        <span class="zone-percentage">${pct(zones.z1)}% (${Math.round(zones.z1)}분)</span>
                    </div>
                    <div class="zone-progress-bg">
                        <div class="zone-progress-fill zone-color-1" style="width: ${pct(zones.z1)}%;"></div>
                    </div>
                </div>
            `;
        }

        // 4.2 Monthly DB 달력 렌더러
        function renderCalendarDB() {
            const grid = document.getElementById('calendar-grid-container');
            if (!grid) return;

            grid.innerHTML = "";
            const activities = STATS_DATA.may_activities || [];
            
            for (let i = 0; i < 4; i++) {
                const emptyCell = document.createElement('div');
                emptyCell.className = "calendar-day empty";
                grid.appendChild(emptyCell);
            }

            for (let day = 1; day <= 31; day++) {
                const dateStr = `2026-05-${day.toString().padStart(2, '0')}`;
                const cell = document.createElement('div');
                cell.className = "calendar-day";
                
                if (dateStr === STATS_DATA.today_date) {
                    cell.classList.add('today');
                }

                const dailyRuns = activities.filter(act => act.start_date_local && act.start_date_local.startsWith(dateStr));
                
                let dayContent = `<span class="day-number">${day}</span>`;
                let runData = null;

                if (dailyRuns.length > 0) {
                    runData = dailyRuns[0];
                    cell.classList.add('has-run');
                    const distKm = (runData.distance / 1000).toFixed(1);
                    dayContent += `
                        <span class="day-icon">🏃‍♂️</span>
                        <span class="day-dist">${distKm}k</span>
                    `;
                }

                cell.innerHTML = dayContent;
                cell.addEventListener('click', () => showCalendarDetails(day, dateStr, runData));
                grid.appendChild(cell);
            }
        }

        function showCalendarDetails(dayNum, dateStr, run) {
            const panel = document.getElementById('calendar-details-panel');
            if (!panel) return;

            panel.style.display = "block";
            panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

            const formattedDate = `2026년 5월 ${dayNum}일`;
            
            if (run) {
                const distKm = (run.distance / 1000).toFixed(2);
                const durationMin = Math.round(run.moving_time / 60);
                const paceMin = Math.floor(durationMin / distKm);
                const paceSec = Math.round(((durationMin / distKm) - paceMin) * 60);
                const avgHR = run.average_heartrate ? `${Math.round(run.average_heartrate)} bpm` : "정보 없음";
                const maxHR = run.max_heartrate ? `${Math.round(run.max_heartrate)} bpm` : "정보 없음";
                
                let customFeedback = "";
                if (run.average_heartrate && run.average_heartrate >= 155) {
                    customFeedback = "심박수가 다소 고강도 존에 오래 머물렀습니다. 다음 날은 보강 운동이나 완전 휴식을 통해 아킬레스건과 슬개건 등 관절 결합 조직을 이완시켜 주는 것을 강력하게 권장합니다.";
                } else {
                    customFeedback = "아주 훌륭한 심장 유산소 능동 제어 하에 잘 소화된 훈련입니다. 이 페이스와 균일한 스트로크를 유지하시면 2027년 3시간 30분 마라톤 도달을 위한 탄탄한 기초가 완성됩니다.";
                }

                panel.innerHTML = `
                    <div class="details-title">
                        <span>🏆 ${formattedDate} 운동 실적</span>
                        <span style="font-size:10px; color:var(--text-muted);">${run.name}</span>
                    </div>
                    <div class="details-grid">
                        <div class="details-item">
                            <div class="details-label">러닝 거리</div>
                            <div class="details-val" style="color:var(--primary); font-size:14px;">${distKm} km</div>
                        </div>
                        <div class="details-item">
                            <div class="details-label">달린 시간</div>
                            <div class="details-val">${durationMin}분</div>
                        </div>
                        <div class="details-item">
                            <div class="details-label">평균 페이스</div>
                            <div class="details-val">${paceMin}'${paceSec.toString().padStart(2, '0')}" /km</div>
                        </div>
                        <div class="details-item">
                            <div class="details-label">평균/최대 심박</div>
                            <div class="details-val">${avgHR} / ${maxHR}</div>
                        </div>
                    </div>
                    <div class="details-feedback">
                        <strong>💡 AI 분석 피드백:</strong><br/>
                        ${customFeedback}
                    </div>
                `;
            } else {
                panel.innerHTML = `
                    <div class="details-title">
                        <span>📅 ${formattedDate} 일정</span>
                        <span style="font-size:10px; color:var(--text-muted);">러닝 기록 없음</span>
                    </div>
                    <div style="font-size:11px; color:var(--text-muted); text-align:center; padding: 20px 0;">
                        이 날은 완료된 Strava 러닝 로그가 없습니다.<br/>
                        충분한 완전 휴식 및 하체 가동성 보강운동 세트를 권장하는 일정입니다. 🧘‍♂️
                    </div>
                `;
            }
        }

        // 5. Daily Running & AI Feedback Loop 렌더러
        function renderDailyRunning() {
            const container = document.getElementById('daily-running-container');
            const commentBox = document.getElementById('coach-comment-content');
            const previousRecommendBox = document.getElementById('previous-running-content');
            const nextRecommendBox = document.getElementById('next-running-content');
            if (!container) return;

            const coachComment = localStorage.getItem('project330_coach_comment') || INITIAL_COACH_COMMENT;
            const nextRecommend = localStorage.getItem('project330_next_running') || INITIAL_NEXT_RUNNING;

            commentBox.innerHTML = coachComment;

            // AI Feedback Loop 상태 주입
            const todayIdx = STATS_DATA.today_weekday_idx;
            const todayPlan = appState.weekPlan[todayIdx] || { type: "완전 휴식", distance: "-", intensity: "💤 OFF" };
            
            // Step 1: AI의 추천 훈련 채워넣기
            document.getElementById('loop-recommend-title').innerHTML = `🏃‍♂️ 오늘 예정: ${todayPlan.type} (${todayPlan.distance})`;

            // 1) Previous Running 렌더링
            const yesterdayIdx = (todayIdx - 1 + 7) % 7;
            const yesterdayPlan = appState.weekPlan[yesterdayIdx] || { type: "완전 휴식", distance: "-", intensity: "💤 OFF" };
            
            const yesterdayDate = new Date(STATS_DATA.today_date);
            yesterdayDate.setDate(yesterdayDate.getDate() - 1);
            const yesterdayStr = `${yesterdayDate.getMonth() + 1}월 ${yesterdayDate.getDate()}일`;
            
            const yesterdayRun = STATS_DATA.yesterday_run;
            if (previousRecommendBox) {
                if (yesterdayRun) {
                    const distKm = (yesterdayRun.distance / 1000.0).toFixed(2);
                    const totalSec = yesterdayRun.moving_time;
                    let paceStr = "-";
                    if (parseFloat(distKm) > 0) {
                        const secPerKm = totalSec / parseFloat(distKm);
                        const paceMin = Math.floor(secPerKm / 60);
                        const paceSec = Math.round(secPerKm % 60);
                        paceStr = `${paceMin}'${paceSec.toString().padStart(2, '0')}"`;
                    }
                    const avgHr = yesterdayRun.average_heartrate || "-";
                    
                    previousRecommendBox.innerHTML = `
                        <div class="previous-header">⏮️ Previous Running (어제 ${yesterdayStr} 실적)</div>
                        <div class="previous-body" style="color: #4ade80;">
                            🏃‍♂️ 실제: ${yesterdayRun.name} - ${distKm}km (${paceStr}/km, 심박수: ${avgHr}bpm) 완수 완료! ✅
                        </div>
                        <div class="previous-detail">
                            어제 계획: ${yesterdayPlan.type} (${yesterdayPlan.distance}) | 강도: ${yesterdayPlan.intensity}
                        </div>
                    `;
                    previousRecommendBox.style.display = 'block';
                } else {
                    if (yesterdayPlan.intensity.includes("OFF") || yesterdayPlan.type.includes("휴식")) {
                        previousRecommendBox.innerHTML = `
                            <div class="previous-header">⏮️ Previous Running (어제 ${yesterdayStr} 실적)</div>
                            <div class="previous-body" style="color: #ddd;">
                                💤 계획대로 휴식 완료!
                            </div>
                            <div class="previous-detail">
                                어제 계획: 완전 휴식 및 피로 회복
                            </div>
                        `;
                        previousRecommendBox.style.display = 'block';
                    } else {
                        previousRecommendBox.innerHTML = `
                            <div class="previous-header">⏮️ Previous Running (어제 ${yesterdayStr} 실적)</div>
                            <div class="previous-body" style="color: var(--text-muted);">
                                ⚠️ 실적 기록 없음 (계획 미완수 또는 스트라바 연동 대기)
                            </div>
                            <div class="previous-detail">
                                어제 계획: ${yesterdayPlan.type} (${yesterdayPlan.distance}) | 강도: ${yesterdayPlan.intensity}
                            </div>
                        `;
                        previousRecommendBox.style.display = 'block';
                    }
                }
            }

            // 2) Upcoming Running 렌더링 (내일 예정)
            const tomorrowIdx = (todayIdx + 1) % 7;
            const tomorrowPlan = appState.weekPlan[tomorrowIdx] || { type: "완전 휴식", distance: "-", intensity: "💤 OFF", detail: "완전 휴식 및 피로 회복" };
            
            const tomorrowDate = new Date(STATS_DATA.today_date);
            tomorrowDate.setDate(tomorrowDate.getDate() + 1);
            const tomorrowStr = `${tomorrowDate.getMonth() + 1}월 ${tomorrowDate.getDate()}일`;

            if (nextRecommendBox) {
                nextRecommendBox.innerHTML = `
                    <div class="upcoming-header">⏭️ Upcoming Running (내일 ${tomorrowStr} 예정 훈련)</div>
                    <div class="upcoming-body" style="color: var(--primary);">
                        🏃‍♂️ ${tomorrowPlan.type} (${tomorrowPlan.distance}) - 강도: ${tomorrowPlan.intensity}
                    </div>
                    <div class="upcoming-detail">
                        세부 목표: ${tomorrowPlan.detail || "세부 설명 없음"}<br/>
                        <span style="font-weight: 500; color: #fff; margin-top: 4px; display: inline-block;">💡 코치 코멘트: ${nextRecommend}</span>
                    </div>
                `;
            }

            const todayRun = STATS_DATA.today_run;
            if (todayRun) {
                // Strava 연동 활성화 상태 렌더
                document.getElementById('loop-step-strava').classList.add('active');
                document.getElementById('loop-step-strava').querySelector('.loop-step-title').innerHTML = "2단계: 오늘 러닝 실적 연동 완료! (Strava Run Synced) ✅";
                const distKm = (todayRun.distance / 1000.0).toFixed(2);
                document.getElementById('loop-strava-title').innerHTML = `⚡ ${distKm}km 달리기 완료!`;
                document.getElementById('loop-strava-desc').innerHTML = `이름: ${todayRun.name} / 심박수: ${todayRun.average_heartrate || "-"}bpm`;

                // Step 3 활성화
                document.getElementById('loop-step-analysis').classList.add('active');
                document.getElementById('loop-next-recommend-title').innerHTML = nextRecommend;
                document.getElementById('loop-next-recommend-desc').innerHTML = "AI 코치가 오늘 훈련의 심박수와 거리를 분석하여 도출한 다음 훈련 가이드입니다.";

                // Daily Running 세부 정보 카드 출력
                const distKmVal = (todayRun.distance / 1000.0).toFixed(2);
                const totalSec = todayRun.moving_time;
                let paceMin = 0;
                let paceSec = 0;
                if (parseFloat(distKmVal) > 0) {
                    const secPerKm = totalSec / parseFloat(distKmVal);
                    paceMin = Math.floor(secPerKm / 60);
                    paceSec = Math.round(secPerKm % 60);
                }
                const avgHr = todayRun.average_heartrate || "-";

                container.innerHTML = `
                    <div class="stat-grid">
                        <div class="stat-card">
                            <div class="stat-title">실제 거리</div>
                            <div class="stat-value">${distKmVal} <span class="stat-unit">km</span></div>
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
            } else {
                // Strava 비연동 상태 렌더
                document.getElementById('loop-step-strava').classList.remove('active');
                document.getElementById('loop-step-strava').querySelector('.loop-step-title').innerHTML = "2단계: 오늘 러닝 실적 연동 (Strava Run Sync)";
                document.getElementById('loop-strava-title').innerHTML = "연동 대기 중";
                document.getElementById('loop-strava-desc').innerHTML = "러닝 실적이 자동으로 연동되면 녹색 활성 상태로 변경됩니다.";

                document.getElementById('loop-step-analysis').classList.remove('active');
                document.getElementById('loop-next-recommend-title').innerHTML = "훈련 결과 대기 중";
                document.getElementById('loop-next-recommend-desc').innerHTML = "달리기 기록 연동 완료 후 AI가 내일을 위한 최적의 훈련을 갱신합니다.";

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
                            <div class="rest-title" style="color: var(--primary);">오늘 오후 예정된 본운동: ${todayPlan.type} (${todayPlan.distance})</div>
                            <div class="rest-desc" style="color: #fff; font-weight:500; margin-top: 6px;">아직 오늘 달린 러닝 기록이 스트라바에 연동되지 않았습니다.</div>
                            <div class="rest-desc" style="font-size: 11px; margin-top: 2px;">운동을 마친 후 자동으로 동기화되거나, 아래 3-Tier 보강 루틴을 먼저 실천해 보세요!</div>
                        </div>
                    `;
                }
            }
        }

        // 6. 3-Tier 보강/스트레칭 블록 렌더러
        function renderRoutines() {
            const tiers = ["Base", "Workout", "Pre-Run"];
            
            tiers.forEach(tier => {
                const listContainer = document.getElementById(`routine-list-${tier}`);
                if (!listContainer) return;

                listContainer.innerHTML = "";
                const filtered = appState.routines.filter(item => item.category === tier);

                if (filtered.length === 0) {
                    listContainer.innerHTML = `<p style="text-align: center; color: var(--text-muted); font-size:11px; padding: 10px;">선택된 ${tier} 운동 블록이 없습니다. 오른쪽의 추가 버튼을 이용하세요.</p>`;
                    return;
                }

                filtered.forEach((item, index) => {
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
                            <span class="routine-name">${item.name}</span>
                            <span class="routine-tips">${item.tips}</span>
                        </div>
                        
                        <div class="routine-controls">
                            <button class="ctrl-btn" onclick="moveRoutine(${item.id}, -1)" title="위로 이동">▲</button>
                            <button class="ctrl-btn" onclick="moveRoutine(${item.id}, 1)" title="아래로 이동">▼</button>
                            <button class="ctrl-btn" onclick="editRoutineInline(${item.id})" title="편집">✏️</button>
                            <button class="ctrl-btn btn-delete" onclick="deleteRoutine(${item.id})" title="제거">×</button>
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
                        saveStateToBackend();
                    });

                    listContainer.appendChild(block);
                });
            });
        }

        // 루틴 블록 순서 조정 (해당 티어 범위 내에서 작동)
        window.moveRoutine = function(id, direction) {
            const item = appState.routines.find(r => r.id === id);
            if (!item) return;
            
            const tier = item.category;
            const filtered = appState.routines.filter(r => r.category === tier);
            const index = filtered.findIndex(r => r.id === id);
            const targetIndex = index + direction;
            if (targetIndex < 0 || targetIndex >= filtered.length) return;
            
            const id1 = filtered[index].id;
            const id2 = filtered[targetIndex].id;
            
            const idx1 = appState.routines.findIndex(r => r.id === id1);
            const idx2 = appState.routines.findIndex(r => r.id === id2);
            
            // 위치 변경
            const temp = appState.routines[idx1];
            appState.routines[idx1] = appState.routines[idx2];
            appState.routines[idx2] = temp;

            localStorage.setItem('project330_routines_today', JSON.stringify(appState.routines));
            renderRoutines();
            saveStateToBackend();
        };

        // 루틴 블록 삭제 (X 클릭 시)
        window.deleteRoutine = function(id) {
            appState.routines = appState.routines.filter(item => item.id !== id);
            localStorage.setItem('project330_routines_today', JSON.stringify(appState.routines));
            renderRoutines();
            saveStateToBackend();
        };

        // 루틴 블록 편집
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
            saveStateToBackend();
        };

        // 7. 각 티어별 인라인 운동 리스트 팝업 구성
        function setupAddExerciseLibrary() {
            const tiers = ["Base", "Workout", "Pre-Run"];
            
            tiers.forEach(tier => {
                const select = document.getElementById(`select-${tier}`);
                if (!select) return;
                
                select.innerHTML = `<option value="">-- ${tier} 라이브러리 운동 선택 --</option>`;
                
                EXERCISE_LIBRARY.filter(ex => ex.category === tier).forEach((ex, idx) => {
                    const opt = document.createElement('option');
                    // EXERCISE_LIBRARY 에서의 절대 인덱스 활용
                    const globalIdx = EXERCISE_LIBRARY.findIndex(x => x.name === ex.name);
                    opt.value = globalIdx;
                    opt.textContent = `[${ex.target}] ${ex.name} (${ex.sets} x ${ex.reps})`;
                    select.appendChild(opt);
                });
            });
        }

        // 인라인 추가 드로어 토글
        window.toggleAddDrawer = function(tier) {
            const drawer = document.getElementById(`add-drawer-${tier}`);
            if (!drawer) return;
            drawer.style.display = drawer.style.display === 'block' ? 'none' : 'block';
        };

        // 3-Tier 특정 그룹에 신규 운동 추가 수행
        window.addExerciseInline = function(tier) {
            const select = document.getElementById(`select-${tier}`);
            const val = select.value;
            if (val === "") return;

            const selectedEx = EXERCISE_LIBRARY[parseInt(val)];
            const maxId = appState.routines.reduce((max, item) => item.id > max ? item.id : max, -1);
            
            const newBlock = {
                id: maxId + 1,
                category: tier,
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
            toggleAddDrawer(tier);
            saveStateToBackend();
        };

        // 8. 초기 코치 추천 데이터 상태로 완전히 되돌리기 (Escape hatch)
        async function resetToOriginalCoachRecommendation() {
            if (confirm("정말로 모든 사용자 설정(주간 계획표 수정, 보강운동 체크/추가 상태)을 지우고 AI 코치의 최초 추천 훈련과 보강운동 루틴으로 되돌리시겠습니까?")) {
                localStorage.removeItem('project330_week_plan');
                localStorage.removeItem('project330_routines_today');
                localStorage.removeItem('project330_coach_comment');
                localStorage.removeItem('project330_next_running');
                
                try {
                    const response = await fetch(getBackendUrl('/api/reset'), {
                        method: 'POST'
                    });
                    if (response.ok) {
                        alert("🔄 로컬 및 서버 캐시 초기화 완료! 페이지가 새로고침되어 AI의 최초 코칭 처방이 재갱신됩니다.");
                        setTimeout(() => {
                            location.reload();
                        }, 1500);
                        return;
                    }
                } catch(e) {
                    console.warn("Error calling backend reset:", e);
                }
                
                initAppState();
                renderWeekPlanTable();
                renderDailyRunning();
                renderRoutines();
                alert("🔄 로컬 저장소 캐시가 초기화되었습니다.");
            }
        }

        // 9. API Key 설정 및 모달 관리
        function renderSettingsModal() {
            const input = document.getElementById('api-key-input');
            if (input) {
                input.value = appState.apiKey;
            }
            
            const clientIdInput = document.getElementById('strava-client-id-input');
            const clientSecretInput = document.getElementById('strava-client-secret-input');
            const refreshTokenInput = document.getElementById('strava-refresh-token-input');
            
            if (clientIdInput && STATS_DATA.strava_client_id) {
                clientIdInput.value = STATS_DATA.strava_client_id;
            }
            if (clientSecretInput && STATS_DATA.strava_client_secret) {
                clientSecretInput.value = STATS_DATA.strava_client_secret;
            }
            if (refreshTokenInput && STATS_DATA.strava_refresh_token) {
                refreshTokenInput.value = STATS_DATA.strava_refresh_token;
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

        // 10. 수정 후 AI 코치 평가받기 (Gemini API 실시간 AJAX 클라이언트 추론 - 몸상태별 주간계획표 자동 재분배 탑재)
        async function runAIEvaluation(isSilent = false) {
            if (!appState.apiKey) {
                if (!isSilent) {
                    alert("Gemini API Key를 먼저 설정해 주세요! 우측 상단의 ⚙️ 아이콘을 누르면 쉽게 등록할 수 있습니다.");
                    toggleSettingsModal(true);
                }
                return;
            }

            const evaluateBtn = document.getElementById('evaluate-btn');
            const loading = document.getElementById('ai-loading');
            const commentBox = document.getElementById('coach-comment-content');
            
            if (!isSilent) {
                evaluateBtn.style.display = 'none';
                loading.style.display = 'flex';
            } else {
                commentBox.innerHTML = '<div class="skeleton-loading">AI 코치가 새로운 일정을 반영하여 피드백을 재분석 중입니다...</div>';
            }

            const fatigue = document.getElementById('cond-fatigue').value;
            const pain = document.getElementById('cond-pain').value;
            const notes = document.getElementById('cond-notes').value;

            const formattedPlan = appState.weekPlan.map(p => `요일: ${p.day}요일, 종류: ${p.type}, 목표 거리: ${p.distance}, 강도: ${p.intensity}`).join("\\n");
            
            const prompt = `
역할: 전문 마라톤 코치이자 부상 방지 재활 및 임산부/육아 러닝 전문가.
사용자의 배경 정보:
- 미래 목표: 2027년 3월 서울마라톤 풀코스 3시간 30분(Project330) 목표.
- 현실적 제약 및 특별 상황: 2026년 9월 출산 예정. 이후 육아 동반 예정으로, 강도 높은 하드 트레이닝보다는 "부상 없이 여름철을 나며 보강운동을 병행하고 장거리를 소화할 수 있는 튼튼한 하체와 코어 몸 만들기"가 핵심 목표.
- 현재 날짜: ${STATS_DATA.today_date}

사용자가 주간 훈련 계획을 다음과 같이 새롭게 수립/수정하였습니다:
${formattedPlan}

사용자의 현재 건강 컨디션:
- 피로도: ${fatigue}
- 통증 여부: ${pain}
- 메모 및 특이사항: ${notes}

[중요 지시 사항]:
사용자의 피로도가 '상'이거나 통증 부위가 '없음'이 아닌 경우(예: 무릎, 아킬레스건 통증), 전문 코치로서 수정된 계획이 안전한지 철저하게 검토하세요. 부상 악화를 방지하기 위해 오늘 이후의 주간 계획 항목(특히 일요일 장거리 훈련)에 대하여 타당한 조정을 가하여 자동으로 재스케줄링된 주간 계획표 배열(week_plan)을 함께 응답해 주세요. (예: 아킬레스건 통증 시, 일요일 15km 장거리를 5km 이지 러닝 또는 완전 휴식/보강운동으로 낮추어 week_plan 값을 리턴할 것)

반드시 아래 JSON 형식 명칭을 지켜 오직 **순수 JSON**으로만 응답해 주세요. 백틱(markdown block)을 절대로 붙이지 마세요.

출력 JSON 형식:
{
  "coach_comment": "사용자의 피로도, 통증, 오늘 달리기 결과, 그리고 임신/출산 상황을 다정하고 따뜻하게 격려하면서도 수정/조정된 훈련계획의 타당성을 러닝 생리학적으로 분석해주는 3~4줄의 조언",
  "next_running": "수정된 계획과 오늘의 몸 상태에 기초한 다음 목표 훈련 가이드 한 줄 요약 (예: '🏃‍♂️ Next Target: 5km 가벼운 리커버리 조깅 (평균 심박수 135-140 유지)')",
  "week_plan": [
    {
      "day": "월",
      "type": "훈련 종류 (예: 빌드업 조깅, 이지 조깅, 보강 운동, 완전 휴식)",
      "duration": "목표 시간(분) (예: '45', '-' 등)",
      "pace": "목표 페이스 (예: '6\\'00\"', '-' 등)",
      "hr": "목표 심박수 (예: '135', '-' 등)"
    },
    ... (월요일부터 일요일까지 몸 상태에 맞춰 완전히 재분배된 7일간의 계획표 객체 리스트 순서대로)
  ]
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

                // 로컬 상태 동기화 및 바인딩
                localStorage.setItem('project330_coach_comment', parsedAI.coach_comment);
                localStorage.setItem('project330_next_running', parsedAI.next_running);
                
                if (parsedAI.week_plan && Array.isArray(parsedAI.week_plan)) {
                    appState.weekPlan = parsedAI.week_plan;
                    localStorage.setItem('project330_week_plan', JSON.stringify(appState.weekPlan));
                }

                // UI 리렌더링
                renderWeekPlanTable();
                renderDailyRunning();
                renderZoneTracking();
                renderCalendarDB();

                // 서버 사이드 DB 영구저장 호출
                await saveStateToBackend();

                if (!isSilent) {
                    alert("🎉 AI 코치님이 몸 상태에 맞게 전체 주간 계획표를 안전하게 조정하고 오늘의 처방을 갱신하였습니다!");
                }

            } catch (error) {
                console.error("Gemini AI API Call Failure:", error);
                if (!isSilent) {
                    alert(`⚠️ AI 코치 호출 중 문제가 발생했습니다: ${error.message}\n(API 키를 다시 확인해 보시거나 잠시 후 다시 시도해 주세요)`);
                } else {
                    const prevComment = localStorage.getItem('project330_coach_comment') || INITIAL_COACH_COMMENT;
                    commentBox.innerHTML = prevComment;
                }
            } finally {
                if (!isSilent) {
                    loading.style.display = 'none';
                    evaluateBtn.style.display = 'inline-flex';
                }
            }
        }

        // 11. 전체 클릭 이벤트 처리 바인딩
        function bindEvents() {
            document.getElementById('open-settings-btn').addEventListener('click', () => toggleSettingsModal(true));
            document.getElementById('close-settings-btn').addEventListener('click', () => toggleSettingsModal(false));
            
            document.getElementById('save-settings-btn').addEventListener('click', async () => {
                const geminiKey = document.getElementById('api-key-input').value.trim();
                const clientId = document.getElementById('strava-client-id-input').value.trim();
                const clientSecret = document.getElementById('strava-client-secret-input').value.trim();
                const refreshToken = document.getElementById('strava-refresh-token-input').value.trim();

                appState.apiKey = geminiKey;
                localStorage.setItem('gemini_api_key', geminiKey);

                const payload = {
                    gemini_api_key: geminiKey,
                    strava_client_id: clientId,
                    strava_client_secret: clientSecret,
                    strava_refresh_token: refreshToken
                };

                try {
                    const response = await fetch(getBackendUrl('/api/save_settings'), {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify(payload)
                    });
                    
                    if (response.ok) {
                        alert("🎉 연동 설정이 성공적으로 저장되었습니다! 갱신된 데이터를 반영하기 위해 대시보드가 리빌드됩니다.");
                        toggleSettingsModal(false);
                        location.reload();
                    } else {
                        alert("⚠️ 서버에 설정을 보존하는 도중 오류가 발생했습니다.");
                    }
                } catch(e) {
                    console.error("Error saving settings:", e);
                    alert("⚠️ 로컬 백엔드 서버가 구동 중이지 않아, 브라우저 로컬 저장소에만 임시 보존되었습니다. (서버 가동 권장)");
                    toggleSettingsModal(false);
                }
            });

            // 🔄 동기화 버튼 클릭 이벤트
            const syncBtn = document.getElementById('sync-refresh-btn');
            if (syncBtn) {
                syncBtn.addEventListener('click', async () => {
                    syncBtn.classList.add('rotating');
                    
                    const commentBox = document.getElementById('coach-comment-content');
                    commentBox.innerHTML = '<div class="skeleton-loading">Strava 최신 활동 로그를 동기화하고 대시보드를 새로 빌드하는 중입니다...</div>';

                    try {
                        const response = await fetch(getBackendUrl('/api/sync'), {
                            method: 'POST'
                        });
                        
                        if (response.ok) {
                            alert("🎉 Strava 활동 로그 동기화 및 대시보드 재생성이 완료되었습니다!");
                            location.reload();
                        } else {
                            const resData = await response.json();
                            alert(`⚠️ 동기화 실패: ${resData.message || '서버 오류가 발생했습니다.'}\n(설정(⚙️) 메뉴에서 Strava API 연동 토큰이 올바른지 확인해 주세요)`);
                            location.reload();
                        }
                    } catch(e) {
                        console.error("Sync error:", e);
                        alert("⚠️ 로컬 동기화 서버와 통신할 수 없습니다. (서버가 실행 중인지 확인해 주세요)");
                        location.reload();
                    } finally {
                        syncBtn.classList.remove('rotating');
                    }
                });
            }

            document.getElementById('evaluate-btn').addEventListener('click', () => runAIEvaluation(false));
            document.getElementById('reset-coaching-btn').addEventListener('click', resetToOriginalCoachRecommendation);

            // 실시간 컨디션 피드백 연동
            document.getElementById('cond-fatigue').addEventListener('change', () => {
                saveStateToBackend();
                runAIEvaluation(true);
            });
            document.getElementById('cond-pain').addEventListener('change', () => {
                saveStateToBackend();
                runAIEvaluation(true);
            });
            document.getElementById('cond-notes').addEventListener('change', () => {
                saveStateToBackend();
                runAIEvaluation(true);
            });
        }
    </script>
</body>
</html>"""

    # 안전하게 자리채움 문자열 교체 (Escaping 충돌 제로)
    html_content = html_template
    html_content = html_content.replace("__WEEK_RANGE_STR__", week_range_str)
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
    html_content = html_content.replace("__EXERCISE_LIBRARY_JSON__", exercise_library_json)

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