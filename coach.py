import os
import json
import requests
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
    # 5월 1일부터 오늘까지의 가상 러닝 일지 (사양서 기준 마일리지 매칭)
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
    # 5월 마일리지 계산
    may_activities = []
    weekly_activities = []

    # 이번 주(월요일 시작) 범위 계산
    today_weekday_idx = now_dt.weekday() # 0: Mon, ..., 6: Sun
    start_of_week = (now_dt - timedelta(days=today_weekday_idx)).replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_week = start_of_week + timedelta(days=7)

    # 5월 1일~31일 일자별 마일리지 배열 (초기값 0.0)
    may_daily_mileage = [0.0] * 31
    # 이번 주 요일별 마일리지 (월~일, 초기값 0.0)
    weekly_daily_mileage = [0.0] * 7

    for act in activities:
        # 날짜 파싱 ("2026-05-19T20:00:00Z")
        date_str = act.get("start_date_local")[:10]
        try:
            act_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            continue
        
        dist_km = round(act.get("distance", 0) / 1000.0, 2)
        
        # 5월 활동 필터링
        if act_date.year == 2026 and act_date.month == 5:
            may_activities.append(act)
            day_idx = act_date.day - 1
            if 0 <= day_idx < 31:
                may_daily_mileage[day_idx] += dist_km
        
        # 이번 주 활동 필터링
        act_datetime = datetime.strptime(act.get("start_date_local")[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).astimezone(kst)
        if start_of_week <= act_datetime < end_of_week:
            weekly_activities.append(act)
            w_day_idx = act_datetime.weekday()
            if 0 <= w_day_idx < 7:
                weekly_daily_mileage[w_day_idx] += dist_km

    total_may_mileage = round(sum(may_daily_mileage), 1)
    total_weekly_mileage = round(sum(weekly_daily_mileage), 1)

    # 오늘 러닝 데이터 추출
    today_run = None
    for act in activities:
        if act.get("start_date_local")[:10] == today_date:
            today_run = act
            break

    # QuickChart API URL 빌드
    # 1. 5월 일별 마일리지 바 차트
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
    may_chart_url = f"https://quickchart.io/chart?c={json.dumps(may_chart_payload)}&format=svg"

    # 2. 이번 주 요일별 마일리지 바 차트
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
    week_chart_url = f"https://quickchart.io/chart?c={json.dumps(week_chart_payload)}&format=svg"

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
    
    # 오늘 달리기 정보 텍스트화
    today_run = stats["today_run"]
    if today_run:
        dist_km = round(today_run.get("distance", 0) / 1000.0, 2)
        pace_min = int((today_run.get("moving_time", 0) / 60) // dist_km)
        pace_sec = int((today_run.get("moving_time", 0) / 60) % dist_km * 60 / dist_km)
        avg_hr = today_run.get("average_heartrate", "정보 없음")
        run_info_str = f"이름: {today_run.get('name')}, 거리: {dist_km}km, 평균 페이스: {pace_min}분 {pace_sec}초/km, 평균 심박수: {avg_hr}bpm"
    else:
        run_info_str = "오늘 수행한 러닝 기록이 없습니다. (휴식일)"

    # AI 프롬프트 구성
    prompt = f"""
역할: 전문 마라톤 코치이자 부상 방지 재활 및 임산부/육아 러닝 전문가.
사용자의 배경 정보:
- 러닝 숙련도: 2022년부터 마라톤 풀코스 완주 경험 다수, 2024년 풀코스 PR 3시간 46분 24초 보유자. (숙련된 서브 4 러너)
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

위 변수들을 고도로 분석하여, 아래 4가지 항목을 마크다운이나 다른 기호 없이 오직 **순수한 JSON 형식**으로 응답해 주세요. JSON의 키(Key) 명칭은 정확히 지켜야 하며, 백틱(```)이나 json 마크다운 표시를 절대로 붙이지 말고 중괄호 `{{` 로 시작해서 `}}` 로 끝나는 순수한 문자열만 반환해 주세요.

출력 JSON 형식:
{{
  "week_plan_html": "월요일부터 일요일까지의 일별 훈련 계획표를 나타내는 HTML Table 코드. 행(Tr)은 각 요일(월~일)을 담고, 열(Td)은 요일명, 훈련 종류, 목표 거리 및 강도로 구성. 깔끔하고 모던한 테두리 및 텍스트 정렬 스타일을 가미해 주세요. (주의: 이번 주 누적 마일리지가 {stats["total_weekly_mileage"]}km이고 목표가 50km이므로 남은 요일에 맞춰 유동적으로 거리를 배분해야 함. 또한 몸의 피로도와 통증에 따라 오늘 이후의 계획이 쉬어가거나 보강운동으로 대치되도록 유동적으로 조율해야 함)",
  "next_running": "오늘의 훈련 결과와 몸 상태에 기반하여 예측한 다음 목표 훈련의 권장 명칭, 타겟 거리 및 목표 심박수 가이드를 담은 한 줄 요약 텍스트 (예: '🏃‍♂️ Next Target: 6km 가벼운 회복 조깅 (평균 심박수 135-140 유지)')",
  "coach_comment": "사용자의 피로도, 통증, 오늘 달리기 결과, 그리고 임신/출산/육아 상황을 다정하고 부드럽게 케어하면서도 러닝 생리학적으로 유익한 지식을 전달하는 따뜻한 조언 3~4줄 (무조건 친절한 반말 혹은 격려의 존댓말 중 격식 있고 따뜻한 어투 사용)",
  "routine_today_html": "오늘의 몸 상태(피로도, 통증)와 오늘의 본운동 여부를 매칭하여, notion_routines.md에 정리된 루틴(Pre-Run, Post-Run 등)에서 3~5개를 선별해 체크리스트 형태의 HTML 코드로 구성. (예: '<p style=\"margin-bottom:5px; font-weight:bold; color:#FC4C02;\">🔲 [Step 1] 운동 전 기동성 웜업</p><ul><li>90/90 스트레칭...</li></ul>' 형식으로 각 체크박스 형태와 목록 태그로 구성. 사용자의 통증 부위가 있다면 그 부위 보강 루틴을 적극적으로 큐레이션해야 함)"
}}
"""
    # Gemini API 호출
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
        # 마크다운 백틱 가드 제거 (혹시 몰라 처리)
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
    # 현재 피로도나 통증 상태에 따라 약간의 분기 처리
    if condition["통증"] != "없음":
        comment = f"아 통증이 있으시군요. {condition['통증']} 부위는 무리해서 뛰지 마시고 오늘은 완전 휴식하거나 가벼운 마사지와 함께 폼롤러로 근막을 풀어주는 보강의 날로 삼아 주세요. 장거리 소화 몸 만들기는 조급하지 않게 부상을 관리하는 것부터 시작됩니다."
        next_run = "💤 Next Target: 완전 휴식 또는 하체 무부하 스트레칭"
        routine = """
        <p style="margin-bottom:5px; font-weight:bold; color:#FC4C02;">🔲 [Step 1] 통증 부위 집중 이완 스트레칭</p>
        <ul>
            <li>아킬레스건/종아리 부드럽게 폼롤러 마사지 (5분)</li>
            <li>발목 가동성 아킬레스건 스트레칭 (좌우 10회, 3세트)</li>
        </ul>
        <p style="margin-bottom:5px; font-weight:bold; color:#FC4C02;">🔲 [Step 2] 코어 중립 웜업</p>
        <ul>
            <li>데드버그 (10회 x 3세트)</li>
            <li>버드독 (좌우 10회 x 3세트)</li>
        </ul>
        """
    else:
        comment = "현재 피로도와 컨디션이 매우 양호합니다! 무더운 여름이 다가오기 전에 주 5일 러닝 일정을 잘 소화하시되, 심박수 존 2~3 영역(135-145bpm) 내에서 조깅 마일리지를 차근차근 누적하는 것이 최고의 보약입니다. 러닝 전 웜업 기동성 스트레칭은 부상 방지의 핵심이니 잊지 마세요."
        next_run = "🏃‍♂️ Next Target: 6~8km 편안한 존2 조깅 (타겟 심박수 138-144bpm)"
        routine = """
        <p style="margin-bottom:5px; font-weight:bold; color:#FC4C02;">🔲 [Step 1] 러닝 전 고관절 및 발목 기동성 웜업</p>
        <ul>
            <li>90/90 스트레칭 (좌우 5회, 10초 유지)</li>
            <li>힙 체어 서클 (좌우 15회)</li>
            <li>토 요가 / 발바닥 내재근 깨우기 (10회, 3세트)</li>
        </ul>
        <p style="margin-bottom:5px; font-weight:bold; color:#FC4C02;">🔲 [Step 2] 러닝 후 부상방지 보강 코어</p>
        <ul>
            <li>데드버그 (10회 x 3세트)</li>
            <li>사이드 플랭크 + 클램쉘 중둔근 보강 (좌우 12회, 3세트)</li>
            <li>싱글 레그 데드리프트 (맨몸 좌우 10회, 3세트)</li>
        </ul>
        """
    
    # 더미 HTML 주간 계획 테이블
    week_table = """
    <table style="width:100%; border-collapse:collapse; text-align:center; font-size:13px; color:#e0e0e0;">
        <thead>
            <tr style="border-bottom:1px solid #444; color:#FC4C02;">
                <th style="padding:8px;">요일</th>
                <th style="padding:8px;">훈련 타입</th>
                <th style="padding:8px;">거리</th>
                <th style="padding:8px;">강도</th>
            </tr>
        </thead>
        <tbody>
            <tr style="border-bottom:1px solid #2a2a2a;">
                <td style="padding:8px; font-weight:bold;">월</td><td>완전 휴식</td><td>-</td><td>💤 OFF</td>
            </tr>
            <tr style="border-bottom:1px solid #2a2a2a;">
                <td style="padding:8px; font-weight:bold;">화</td><td>이지 조깅</td><td>6.58 km</td><td>🟢 가볍게</td>
            </tr>
            <tr style="border-bottom:1px solid #2a2a2a;">
                <td style="padding:8px; font-weight:bold;">수</td><td>빌드업 조깅</td><td>8.00 km</td><td>🟡 중간</td>
            </tr>
            <tr style="border-bottom:1px solid #2a2a2a;">
                <td style="padding:8px; font-weight:bold;">목</td><td>보강 운동</td><td>-</td><td>🟠 코어 집중</td>
            </tr>
            <tr style="border-bottom:1px solid #2a2a2a;">
                <td style="padding:8px; font-weight:bold;">금</td><td>지속주 런</td><td>10.00 km</td><td>🟡 중간</td>
            </tr>
            <tr style="border-bottom:1px solid #2a2a2a;">
                <td style="padding:8px; font-weight:bold;">토</td><td>조깅 + 질주</td><td>5.00 km</td><td>🟢 가볍게</td>
            </tr>
            <tr style="border-bottom:1px solid #2a2a2a;">
                <td style="padding:8px; font-weight:bold;">일</td><td>주말 장거리</td><td>15.00 km</td><td>🟠 약간 높음</td>
            </tr>
        </tbody>
    </table>
    """
    
    return {
        "week_plan_html": week_table,
        "next_running": next_run,
        "coach_comment": comment,
        "routine_today_html": routine
    }

# 6. HTML 생성 및 프리미엄 Glassmorphism 스타일 적용
def build_html_dashboard(stats, ai):
    """최종 분석 데이터와 AI 콘텐츠를 조합하여 아주 아름다운 프리미엄 Glassmorphism 웹 대시보드(index.html)를 렌더링합니다."""
    
    # 오늘 달리기 세부 정보 블록 생성
    today_run = stats["today_run"]
    if today_run:
        dist_km = round(today_run.get("distance", 0) / 1000.0, 2)
        moving_min = int(today_run.get("moving_time", 0) // 60)
        moving_sec = int(today_run.get("moving_time", 0) % 60)
        pace_min = int(moving_min // dist_km) if dist_km > 0 else 0
        pace_sec = int((moving_min % dist_km) * 60 / dist_km) if dist_km > 0 else 0
        avg_hr = today_run.get("average_heartrate", "-")
        
        running_detail_html = f"""
        <div class="stat-grid">
            <div class="stat-card">
                <div class="stat-title">거리</div>
                <div class="stat-value">{dist_km} <span class="stat-unit">km</span></div>
            </div>
            <div class="stat-card">
                <div class="stat-title">평균 페이스</div>
                <div class="stat-value">{pace_min}'{pace_sec:02d}" <span class="stat-unit">/km</span></div>
            </div>
            <div class="stat-card">
                <div class="stat-title">평균 심박수</div>
                <div class="stat-value">{avg_hr} <span class="stat-unit">bpm</span></div>
            </div>
        </div>
        """
    else:
        running_detail_html = """
        <div class="rest-card">
            <span class="rest-icon">💤</span>
            <div class="rest-title">Today is a Rest Day!</div>
            <div class="rest-desc">근섬유의 재건과 피로 회복도 훈련의 연장선입니다. 보강운동에 신경 써 주세요.</div>
        </div>
        """

    # 마크다운용 README.md 작성
    readme_text = f"""# 🏃‍♂️ Project 330: AI Running Coach Dashboard
> **Last Sync (KST):** {now_str}

## 📈 Monthly Mileage (May)
{stats["total_may_mileage"]} / 200 km

## ⏱️ Weekly Mileage
{stats["total_weekly_mileage"]} / 50 km

## 📊 Daily Running ({today_date})
{"수행 완료" if today_run else "휴식 또는 보강의 날"}
- {ai["next_running"]}

### 📋 Coach's Comment
> {ai["coach_comment"]}
"""
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(readme_text)

    # 대시보드 HTML/CSS/JS 작성
    html_content = f"""<!DOCTYPE html>
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
        :root {{
            --primary: #FC4C02;
            --primary-glow: rgba(252, 76, 2, 0.35);
            --bg: #0b0c10;
            --card-bg: rgba(30, 30, 35, 0.45);
            --card-border: rgba(255, 255, 255, 0.08);
            --text: #e5e7eb;
            --text-muted: #9ca3af;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
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
        }}

        .container {{
            width: 100%;
            max-width: 500px;
            background: rgba(20, 20, 25, 0.7);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--card-border);
            border-radius: 24px;
            padding: 24px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.6), inset 0 1px 1px rgba(255,255,255,0.1);
        }}

        /* Header */
        header {{
            text-align: center;
            margin-bottom: 25px;
        }}

        .brand {{
            font-family: 'Outfit', sans-serif;
            font-size: 28px;
            font-weight: 800;
            color: #fff;
            letter-spacing: -0.5px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }}

        .brand span {{
            color: var(--primary);
            text-shadow: 0 0 15px var(--primary-glow);
        }}

        .sync-time {{
            font-size: 11px;
            color: var(--text-muted);
            margin-top: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 4px;
        }}
        
        .sync-pulse {{
            width: 6px;
            height: 6px;
            background-color: #10b981;
            border-radius: 50%;
            display: inline-block;
            box-shadow: 0 0 8px #10b981;
            animation: pulse 2s infinite;
        }}

        @keyframes pulse {{
            0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }}
            70% {{ transform: scale(1); box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }}
            100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }}
        }}

        /* Section Global */
        section {{
            margin-bottom: 28px;
        }}

        h2 {{
            font-family: 'Outfit', sans-serif;
            font-size: 18px;
            font-weight: 600;
            color: #fff;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 6px;
        }}

        /* Progress Card */
        .progress-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 16px;
            margin-bottom: 16px;
            position: relative;
            overflow: hidden;
        }}

        .progress-header {{
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            margin-bottom: 8px;
        }}

        .progress-title {{
            font-size: 13px;
            color: var(--text-muted);
            font-weight: 500;
        }}

        .progress-value {{
            font-family: 'Outfit', sans-serif;
            font-size: 20px;
            font-weight: 800;
            color: #fff;
        }}

        .progress-value span {{
            color: var(--primary);
        }}

        .progress-target {{
            font-size: 12px;
            color: var(--text-muted);
        }}

        .progress-bar-container {{
            width: 100%;
            height: 8px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 999px;
            overflow: hidden;
            margin-top: 4px;
        }}

        .progress-bar {{
            height: 100%;
            background: linear-gradient(90deg, #ff7e40, var(--primary));
            border-radius: 999px;
            box-shadow: 0 0 10px rgba(252, 76, 2, 0.5);
            transition: width 1s ease-out;
        }}

        .chart-box {{
            text-align: center;
            margin-top: 12px;
            background: rgba(0, 0, 0, 0.2);
            padding: 10px;
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.03);
        }}

        .chart-box img {{
            max-width: 100%;
            height: auto;
        }}

        /* Daily Running Cards */
        .stat-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
        }}

        .stat-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 14px;
            padding: 12px;
            text-align: center;
        }}

        .stat-title {{
            font-size: 10px;
            color: var(--text-muted);
            margin-bottom: 4px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .stat-value {{
            font-family: 'Outfit', sans-serif;
            font-size: 18px;
            font-weight: 800;
            color: #fff;
        }}

        .stat-unit {{
            font-size: 10px;
            color: var(--text-muted);
            font-weight: 400;
        }}

        .rest-card {{
            background: rgba(252, 76, 2, 0.05);
            border: 1px dashed rgba(252, 76, 2, 0.25);
            border-radius: 16px;
            padding: 18px;
            text-align: center;
        }}

        .rest-icon {{
            font-size: 24px;
            display: block;
            margin-bottom: 6px;
        }}

        .rest-title {{
            font-family: 'Outfit', sans-serif;
            font-size: 15px;
            font-weight: 600;
            color: #fff;
        }}

        .rest-desc {{
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 4px;
        }}

        /* Week Plan Table */
        .week-plan-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 14px;
            overflow-x: auto;
        }}

        /* Coach's Comment Block */
        .coach-comment-box {{
            background: rgba(252, 76, 2, 0.07);
            border-left: 4px solid var(--primary);
            border-radius: 4px 14px 14px 4px;
            padding: 14px;
            font-style: normal;
            font-size: 13.5px;
            color: #f3f4f6;
            margin: 15px 0;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.15);
        }}
        
        .comment-header {{
            font-family: 'Outfit', sans-serif;
            font-weight: 600;
            color: var(--primary);
            font-size: 13px;
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            gap: 4px;
        }}

        /* Next Running Recommend Box */
        .next-recommend-box {{
            background: linear-gradient(135deg, rgba(252, 76, 2, 0.15) 0%, rgba(20, 20, 25, 0.5) 100%);
            border: 1px solid rgba(252, 76, 2, 0.25);
            border-radius: 14px;
            padding: 12px 14px;
            font-size: 13px;
            font-weight: 500;
            color: #fff;
            box-shadow: 0 4px 10px var(--primary-glow);
        }}

        /* Interactive Routine checklist */
        .routine-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 16px;
        }}

        .routine-card ul {{
            list-style: none;
            margin-top: 6px;
            margin-bottom: 12px;
        }}

        .routine-card li {{
            display: flex;
            align-items: flex-start;
            gap: 10px;
            margin-bottom: 10px;
            font-size: 13px;
            color: #d1d5db;
            cursor: pointer;
            user-select: none;
        }}

        .routine-card li input[type="checkbox"] {{
            appearance: none;
            -webkit-appearance: none;
            width: 17px;
            height: 17px;
            border: 2px solid var(--text-muted);
            border-radius: 4px;
            outline: none;
            background-color: transparent;
            cursor: pointer;
            display: grid;
            place-content: center;
            margin-top: 1.5px;
            flex-shrink: 0;
            transition: all 0.2s ease;
        }}

        .routine-card li input[type="checkbox"]::before {{
            content: "✓";
            font-size: 11px;
            font-weight: bold;
            color: #fff;
            transform: scale(0);
            transition: transform 0.15s ease-in-out;
        }}

        .routine-card li input[type="checkbox"]:checked {{
            background-color: var(--primary);
            border-color: var(--primary);
            box-shadow: 0 0 8px var(--primary-glow);
        }}

        .routine-card li input[type="checkbox"]:checked::before {{
            transform: scale(1);
        }}

        .routine-card li.completed span {{
            text-decoration: line-through;
            color: var(--text-muted);
        }}

        /* Footer */
        footer {{
            text-align: center;
            font-size: 10px;
            color: var(--text-muted);
            margin-top: 24px;
            border-top: 1px solid rgba(255,255,255,0.05);
            padding-top: 14px;
        }}

        footer a {{
            color: var(--primary);
            text-decoration: none;
        }}

        /* Scroll Custom */
        ::-webkit-scrollbar {{
            width: 6px;
        }}
        ::-webkit-scrollbar-track {{
            background: transparent;
        }}
        ::-webkit-scrollbar-thumb {{
            background: rgba(255, 255, 255, 0.1);
            border-radius: 99px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header>
            <div class="brand">🏃‍♂️ Project <span>330</span></div>
            <div class="sync-time">
                <span class="sync-pulse"></span>
                <span>Last Sync: {now_str} (KST)</span>
            </div>
        </header>

        <!-- Mileage Progress -->
        <section>
            <h2>📈 Monthly Mileage (May)</h2>
            <div class="progress-card">
                <div class="progress-header">
                    <span class="progress-title">목표 달성률</span>
                    <span class="progress-value"><span>{stats["total_may_mileage"]}</span> / 200 km</span>
                </div>
                <div class="progress-bar-container">
                    <div class="progress-bar" style="width: {min(int(stats["total_may_mileage"] / 200 * 100), 100)}%;"></div>
                </div>
                <div class="chart-box">
                    <img src="{stats["may_chart_url"]}" alt="May Mileage Chart" />
                </div>
            </div>

            <h2>⏱️ Weekly Mileage</h2>
            <div class="progress-card">
                <div class="progress-header">
                    <span class="progress-title">목표 달성률</span>
                    <span class="progress-value"><span>{stats["total_weekly_mileage"]}</span> / 50 km</span>
                </div>
                <div class="progress-bar-container">
                    <div class="progress-bar" style="width: {min(int(stats["total_weekly_mileage"] / 50 * 100), 100)}%;"></div>
                </div>
                <div class="chart-box">
                    <img src="{stats["week_chart_url"]}" alt="Weekly Mileage Chart" />
                </div>
            </div>
        </section>

        <!-- Week Plan (Dynamic Gemini calculated) -->
        <section>
            <h2>📅 Week Plan (주간 계획표)</h2>
            <div class="week-plan-card">
                {ai["week_plan_html"]}
            </div>
        </section>

        <!-- Daily Running stats -->
        <section>
            <h2>🏃‍♂️ Daily Running ({today_date})</h2>
            {running_detail_html}
            
            <div class="coach-comment-box">
                <div class="comment-header">📋 AI COACH'S COMMENT</div>
                {ai["coach_comment"]}
            </div>
            
            <div class="next-recommend-box">
                {ai["next_running"]}
            </div>
        </section>

        <!-- Today's Routine checklist -->
        <section>
            <h2>🛠️ Routine For Today</h2>
            <div class="routine-card" id="routine-section">
                {ai["routine_today_html"]}
            </div>
        </section>

        <!-- Footer -->
        <footer>
            <p>Automated with Strava API & Gemini 1.5 & QuickChart</p>
            <p style="margin-top: 4px;">Designed by Antigravity for <a href="https://github.com/Jay330-KR/Jaewon-s-Running-Coach" target="_blank">Project330</a></p>
        </footer>
    </div>

    <!-- Interactive To-Do list state script -->
    <script>
        document.addEventListener('DOMContentLoaded', () => {{
            const routineContainer = document.getElementById('routine-section');
            if (!routineContainer) return;

            // 1. 모든 li 요소를 체크리스트 형태로 바인딩
            const items = routineContainer.querySelectorAll('ul li');
            
            items.forEach((item, index) => {{
                // 내부 텍스트 확보
                const text = item.innerHTML;
                const storageKey = `project330_todo_${{index}}_${{today_date}}`;
                const isChecked = localStorage.getItem(storageKey) === 'true';

                // HTML 구조 변경: 체크박스 강제 주입
                item.innerHTML = `<input type="checkbox" id="check_${{index}}" ${{isChecked ? 'checked' : ''}}> <span>${{text}}</span>`;
                
                if (isChecked) {{
                    item.classList.add('completed');
                }}

                // 클릭 이벤트 바인딩
                const checkbox = item.querySelector('input[type="checkbox"]');
                
                const toggleCheck = (e) => {{
                    // 만약 체크박스 자체를 누른 게 아니라면 토글 처리
                    if (e.target !== checkbox) {{
                        checkbox.checked = !checkbox.checked;
                    }}
                    
                    if (checkbox.checked) {{
                        item.classList.add('completed');
                        localStorage.setItem(storageKey, 'true');
                    }} else {{
                        item.classList.remove('completed');
                        localStorage.setItem(storageKey, 'false');
                    }}
                }};

                item.addEventListener('click', toggleCheck);
            }});
        }});
    </script>
</body>
</html>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("🎉 [Dashboard] index.html이 성공적으로 생성 및 갱신되었습니다!")

# 7. 메인 실행 흐름
def main():
    print(f"🎬 [Pipeline Start] {now_str} (KST)")
    
    # 데이터 로드
    condition = load_condition()
    routines = load_notion_routines()
    
    # 스트라바 활동 가져오기 및 분석
    activities = get_strava_activities()
    stats = calculate_mileage_and_build_charts(activities)
    
    # Gemini AI 코칭 결과 생성
    ai_content = get_ai_coaching_content(stats, condition, routines)
    
    # 최종 대시보드 빌드
    build_html_dashboard(stats, ai_content)
    
    print("🏁 [Pipeline End] 대시보드 업데이트 완료.")

if __name__ == "__main__":
    main()