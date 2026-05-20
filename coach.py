import os
import requests
import base64
import urllib.parse
import calendar
from datetime import datetime, timedelta
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")

def get_new_access_token():
    url = "https://www.strava.com/oauth/token"
    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
        "grant_type": "refresh_token"
    }
    response = requests.post(url, data=payload).json()
    return response.get("access_token")

def get_activities(access_token, per_page=50):
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"per_page": per_page}
    return requests.get(url, headers=headers, params=params).json()

def calculate_pace(distance_meter, duration_seconds):
    if distance_meter == 0:
        return 0, 0
    distance_km = distance_meter / 1000
    total_minutes = (duration_seconds / 60) / distance_km
    minutes = int(total_minutes)
    seconds = int((total_minutes - minutes) * 60)
    return minutes, seconds

def get_this_week_monday():
    today = datetime.now()
    days_since_monday = today.weekday()
    monday = today - timedelta(days=days_since_monday)
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)

def make_orange_progress_bar(current, target, length=15):
    if target == 0:
        return ""
    percentage = min(int((current / target) * 100), 100)
    filled_length = int(length * percentage // 100)
    bar = "🟠" * filled_length + "🟤" * (length - filled_length)
    return f"{bar} **{current:.1f}** / {target} km ({percentage}%)"

def generate_month_chart_url(labels, data):
    chart_config = {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [{
                "data": data,
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
    config_string = str(chart_config).replace("True", "true").replace("False", "false")
    return f"https://quickchart.io/chart?c={urllib.parse.quote(config_string)}&format=svg"

def generate_week_chart_url(labels, distances, durations, heartrates):
    display_labels = []
    for i in range(7):
        if distances[i] > 0:
            hr_part = f"/{int(heartrates[i])}" if heartrates[i] > 0 else ""
            lbl = f"[{distances[i]:.1f}k/{int(durations[i])}m{hr_part}]"
        else:
            lbl = ""
        display_labels.append(lbl)

    chart_config = {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [{
                "data": distances,
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
            "plugins": {
                "datalabels": {
                    "formatter": f"function(value, context) {{ const labels = {str(display_labels)}; return labels[context.dataIndex]; }}"
                }
            }
        }
    }
    config_string = str(chart_config).replace("True", "true").replace("False", "false")
    encoded_config = urllib.parse.quote(config_string)
    return f"https://quickchart.io/chart?c={encoded_config}&format=svg"

def get_intensity_and_eval(heartrate, distance_km):
    if distance_km == 0:
        intensity = "None (Rest Day)"
        evaluation = "오늘은 온전한 휴식을 취하며 근육을 재건하고 코어 보강 운동에 집중하는 날입니다. 부상 방지를 위해 휴식도 훈련의 일부입니다."
        next_run = "🏃‍♂️ **Next Target:** 5~7km 가벼운 빌드업 조깅 (목표 심박수: 140대)"
    elif heartrate == 0:
        intensity = "Unknown (No HRM Data)"
        evaluation = "러닝 기록은 정상 수집되었으나 심박 데이터가 없습니다. 페이스 컨트롤과 정확한 강도 분석을 위해 다음에는 가민 워치 정밀 착용을 권장합니다."
        next_run = "🏃‍♂️ **Next Target:** 상태에 따라 40분 리커버리 조깅 또는 코어 루틴 수행"
    elif heartrate < 145:
        intensity = "Low (Recovery)"
        evaluation = "심박수가 안정적으로 제어된 완벽한 리커버리 러닝이었습니다. 관절에 무리 없이 유산소 베이스를 넓히는 데 아주 좋은 페이스입니다. 훌륭합니다!"
        next_run = "🏃‍♂️ **Next Target:** 8~10km 에어로빅 지구력 러닝 (페이스 5분 중반대 목표)"
    elif heartrate < 165:
        intensity = "Moderate (Tempo / Aerobic)"
        evaluation = "마라톤 준비를 위한 가장 심장 효율이 좋은 구간(Zone 3)에서 잘 소화하셨습니다. 후반부 페이스 밀림이 없다면 현재 심폐 능력이 아주 잘 발달하고 있다는 증거입니다."
        next_run = "🏃‍♂️ **Next Target:** 완전 휴식 또는 내일은 5km 내외의 가벼운 리커버리 런 추천"
    else:
        intensity = "High (Threshold / Interval)"
        evaluation = "심폐 기능 고점에 부딪히는 강한 자극의 훈련이었습니다. 아킬레스건과 무릎 주변 결합조직이 많은 충격을 받았을 상태이므로, 오늘 처방되는 신장성 카프레이즈를 반드시 성실하게 수행해야 합니다."
        next_run = "💤 **Next Target:** 무조건 강제 휴식 또는 가벼운 스트레칭만 제한적 수행"
        
    return intensity, evaluation, next_run

def recommend_routine(distance_km, pace_minutes):
    warmup = [
        "90/90 Stretching (5 reps L/R, hold 10s) -> Unlock Hip Mobility",
        "Hip Chair Circles (15 reps L/R) -> Lubricate Hip Sockets",
        "Toe Yoga / Foot Core (10 reps x 3 sets) -> Activate Plantar Arch"
    ]
    post_run = []
    
    if distance_km == 0:
        workout_type = "Core & Lower Body Reconstruction Routine"
        post_run = [
            "Deadbug (10 reps x 3 sets) -> Core bracing, keep lower back flat",
            "Side Plank + Clamshell (12 reps x 3 sets) -> Target Gluteus Medius",
            "Romanian Deadlift 12kg (12 reps x 3 sets) -> Focus on clean Hip-Hinge",
            "Split Squat 4kg (8 reps L/R x 3 sets) -> Maintain Knee external rotation torque"
        ]
    elif distance_km >= 7.0 or pace_minutes < 5:
        workout_type = "High-Load Recovery & Tissue Protection Routine"
        post_run = [
            "Hamstring Static Stretch (1 min L/R x 2 sets) -> Static elongation without bouncing",
            "Eccentric Calf Raise (15 reps x 3 sets) -> 5-sec lowering phase to protect Achilles tendon",
            "Foam Roller Quad Setting / Q-Set (12 reps x 3 sets) -> Isometric VMO contraction"
        ]
    else:
        workout_type = "Knee Stability & VMO Activation Routine"
        post_run = [
            "Tibial Internal/External Rotation Drill (15 reps x 3 sets) -> Recover shinbone rotation mobility",
            "Foam Roller Quad Setting / Q-Set (12 reps x 3 sets) -> Press knee down onto roller to target VMO",
            "Lean Forward Isometric Hold (20s x 3 sets) -> Elevate heels and lean forward to strengthen connective tissues"
        ]
    return warmup, post_run, workout_type

def push_to_github(markdown_content):
    user_url = "https://api.github.com/user"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    user_res = requests.get(user_url, headers=headers).json()
    username = user_res.get("login")
    
    if not username:
        return False
        
    repo_url = f"https://api.github.com/repos/{username}/{GITHUB_REPO}/contents/README.md"
    get_res = requests.get(repo_url, headers=headers)
    sha = get_res.json().get("sha") if get_res.status_code == 200 else None
    
    message = f"Project 330 Logic Bug Fix - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    content_bytes = markdown_content.encode("utf-8")
    base64_content = base64.b64encode(content_bytes).decode("utf-8")
    
    data = {"message": message, "content": base64_content}
    if sha:
        data["sha"] = sha
        
    put_res = requests.put(repo_url, headers=headers, json=data)
    return put_res.status_code in [200, 201]

def generate_markdown(run_name, dist_km, pace_str, hr_avg, calories, intensity, evaluation, next_run, this_week_distance, this_month_distance, workout_type, warmup, post_run, week_chart_url, month_chart_url):
    today_str = datetime.now().strftime('%Y-%m-%d')
    WEEK_TARGET = 50 
    MONTH_TARGET = 200
    
    week_bar = make_orange_progress_bar(this_week_distance, WEEK_TARGET)
    month_bar = make_orange_progress_bar(this_month_distance, MONTH_TARGET)
    
    md = f"""# 🏃‍♂️ Project 330
> **Last Sync:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 📈 Monthly Mileage (May)
{month_bar}

![May Daily Chart]({month_chart_url})

## ⏱️ Weekly Mileage
{week_bar}

![Weekly Chart]({week_chart_url})

---

## 📊 Daily Running ({today_str})
* **Name:** {run_name}
* **Distance:** {f"{dist_km:.2f} km" if dist_km > 0 else "💤 Rest Day"}
* **Pace(avg.):** {f"{pace_str} /km" if dist_km > 0 else "-"}
* **Avg Heart Rate:** {f"{int(hr_avg)} bpm" if hr_avg > 0 else "-"}
* **Calories:** {f"{int(calories)} kcal" if calories > 0 else "-"}
* **Intensity:** **{intensity}**

### 📋 Coach’s Comment
> {evaluation}

### 🔮 Next Running
{next_run}

---

## 🛠 Routine For Today
### 🎯 Objective: {workout_type}

### 🔲 [Step 1] Pre-Run Mobility Warmup (Required)
"""
    for wm in warmup:
        md += f"- [ ] {wm}\n"
        
    md += f"\n### 🔲 [Step 2] Post-Run Strength & Recovery Routine\n"
    for pr in post_run:
        md += f"- [ ] {pr}\n"
        
    md += f"\n\n---%0A*This dashboard is fully automated via Strava API & QuickChart API. Built for Sub-3:30 goals at the 2027 Seoul Marathon without injuries.*"
    return md

if __name__ == "__main__":
    print("⏳ Running Project 330 Core Logic Repair...")
    token = get_new_access_token()
    if token:
        raw_activities = get_activities(token, per_page=50)
        
        now = datetime.now()
        this_week_monday = get_this_week_monday()
        may_first = datetime(2026, 5, 1, 0, 0, 0)
        
        today_activity = raw_activities[0]
        act_date_str = today_activity.get('start_date_local')[:10]
        is_today_run = (today_activity.get('type') == 'Run' and act_date_str == now.strftime('%Y-%m-%d'))

        if not is_today_run:
            dist_km, pace_min, pace_sec = 0.0, 0, 0
            run_name = "No Run Today"
            pace_str = "-"
            hr_avg = 0.0
            calories = 0.0
        else:
            dist_km = today_activity.get('distance') / 1000
            move_sec = today_activity.get('moving_time')
            pace_min, pace_sec = calculate_pace(today_activity.get('distance'), move_sec)
            run_name = today_activity.get('name')
            pace_str = f"{pace_min}:{pace_sec:02d}"
            hr_avg = today_activity.get('average_heartrate', 0.0)
            calories = today_activity.get('calories', 0.0)

        intensity, evaluation, next_run = get_intensity_and_eval(hr_avg, dist_km)

        # 주간 및 월간 데이터 배열 세팅
        week_days_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        week_distances = [0.0] * 7
        week_durations = [0.0] * 7
        week_heartrates = [0.0] * 7
        this_week_distance = 0.0
        
        _, last_day_of_may = calendar.monthrange(2026, 5)
        month_labels = [f"{i}" for i in range(1, last_day_of_may + 1)]
        month_data = [0.0] * last_day_of_may
        this_month_distance = 0.0

        # 스트라바 전체 리스트 역순 루프를 돌며 누적 데이터의 완벽한 정합성 보장
        for act in reversed(raw_activities):
            if act.get('type') == 'Run':
                # 문자열 날짜를 완전한 datetime 객체로 변환하여 시간대 에러 원천 차단
                act_date = datetime.strptime(act.get('start_date_local'), "%Y-%m-%dT%H:%M:%SZ")
                dist = act.get('distance') / 1000
                duration_min = act.get('moving_time', 0) / 60
                hr = act.get('average_heartrate', 0.0)
                
                # 이번 주 월요일 00시 이후 데이터 정밀 필터링 및 요일별 인덱스 매칭
                if act_date >= this_week_monday:
                    idx = act_date.weekday()
                    # 해당 요일에 처음 더하는 거라면 덮어쓰고, 기존 값이 있다면 누적 합산하도록 고도화
                    week_distances[idx] = round(week_distances[idx] + dist, 2)
                    week_durations[idx] = round(week_durations[idx] + duration_min, 1)
                    if hr > 0:
                        week_heartrates[idx] = hr

                # 5월 마일리지 정밀 필터링
                if act_date >= may_first and act_date.month == 5:
                    day_index = act_date.day - 1
                    if day_index < last_day_of_may:
                        month_data[day_index] = round(month_data[day_index] + dist, 2)

        # 최종 누적 합산값 추출
        this_week_distance = sum(week_distances)
        this_month_distance = sum(month_data)

        # 고대비 차트 컴파일
        week_chart_url = generate_week_chart_url(week_days_labels, week_distances, week_durations, week_heartrates)
        month_chart_url = generate_month_chart_url(month_labels, month_data)

        warmup, post_run, workout_type = recommend_routine(dist_km, pace_min)
        
        success = push_to_github(generate_markdown(
            run_name, dist_km, pace_str, hr_avg, calories, intensity, evaluation, next_run,
            this_week_distance, this_month_distance, workout_type, warmup, post_run, week_chart_url, month_chart_url
        ))
        
        if success:
            print("🎉 Project 330 bug fixed and updated successfully!")
        else:
            print("❌ Update failed.")
    else:
        print("Token generation failed.")
