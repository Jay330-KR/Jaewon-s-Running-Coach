import os
import json
import subprocess
import threading
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

app = Flask(__name__)

# 임의로 설정하는 검증 토큰 (Strava 구독 등록 시 동일하게 전달해야 함)
VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "PROJECT330_TOKEN")

def run_coach_script():
    """
    coach.py 스크립트를 독립 프로세스로 실행하여 
    Strava API 응답 지연(2초 제한)으로 인한 웹훅 재전송을 방지합니다.
    """
    print("🔄 [Webhook/API] Starting coach.py execution in background...")
    try:
        # coach.py가 있는 디렉토리 경로 확보
        script_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(script_dir, "coach.py")
        
        # subprocess를 활용해 coach.py 실행
        result = subprocess.run(
            ["python", script_path], 
            cwd=script_dir, 
            capture_output=True, 
            text=True
        )
        
        if result.returncode == 0:
            print("🎉 [Webhook/API] coach.py completed successfully!")
            print(result.stdout)
        else:
            print("❌ [Webhook/API] coach.py failed with error:")
            print(result.stderr)
            
    except Exception as e:
        print(f"❌ [Webhook/API] Failed to run coach.py: {str(e)}")

@app.after_request
def add_cors_headers(response):
    """로컬 브라우저가 다른 도메인/프로토콜(file:// 등)에서 이 API 서버에 호출할 수 있도록 CORS 허용"""
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS, PUT, DELETE'
    return response

@app.route('/api/save', methods=['POST', 'OPTIONS'])
def save_state():
    """
    대시보드 UI 브라우저로부터 주간 계획표, 보강 블록, 피로도 및 통증 상태를 전달받아
    로컬 파일시스템(condition.txt, data/week_plan.json 등)에 저장하고 index.html을 재컴파일합니다.
    """
    if request.method == 'OPTIONS':
        return '', 200

    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "전달된 JSON 데이터가 없습니다."}), 400

        week_plan = data.get("week_plan")
        routines = data.get("routines")
        condition = data.get("condition")
        coach_comment = data.get("coach_comment")
        next_running = data.get("next_running")

        # 1. condition.txt 저장 (피로도, 통증, 메모)
        if condition:
            fatigue = condition.get("fatigue", "하")
            pain = condition.get("pain", "없음")
            notes = condition.get("notes", "")

            condition_path = "condition.txt"
            with open(condition_path, "w", encoding="utf-8") as f:
                f.write(f"피로도: {fatigue}\n")
                f.write(f"통증: {pain}\n")
                f.write(f"기타 메모: {notes}\n")
            print("💾 [API] condition.txt 파일이 성공적으로 보존되었습니다.")

        # 2. data/ 폴더 아래 개별 JSON 파일 저장
        cache_dir = "data"
        os.makedirs(cache_dir, exist_ok=True)

        if week_plan:
            week_plan_path = os.path.join(cache_dir, "week_plan.json")
            with open(week_plan_path, "w", encoding="utf-8") as f:
                json.dump(week_plan, f, ensure_ascii=False, indent=2)
            print("💾 [API] data/week_plan.json 파일이 성공적으로 영구 저장되었습니다.")

        if routines:
            routines_path = os.path.join(cache_dir, "routines_today.json")
            with open(routines_path, "w", encoding="utf-8") as f:
                json.dump(routines, f, ensure_ascii=False, indent=2)
            print("💾 [API] data/routines_today.json 파일이 성공적으로 영구 저장되었습니다.")

        if coach_comment:
            coach_comment_path = os.path.join(cache_dir, "coach_comment.json")
            with open(coach_comment_path, "w", encoding="utf-8") as f:
                json.dump(coach_comment, f, ensure_ascii=False, indent=2)
            print("💾 [API] data/coach_comment.json 파일이 성공적으로 영구 저장되었습니다.")

        if next_running:
            next_running_path = os.path.join(cache_dir, "next_running.json")
            with open(next_running_path, "w", encoding="utf-8") as f:
                json.dump(next_running, f, ensure_ascii=False, indent=2)
            print("💾 [API] data/next_running.json 파일이 성공적으로 영구 저장되었습니다.")

        # 3. 비동기로 coach.py 컴파일러를 기동하여 index.html을 재구성
        threading.Thread(target=run_coach_script).start()

        return jsonify({
            "status": "success", 
            "message": "로컬 데이터베이스 저장 완료 및 대시보드 재생성 트리거 성공!"
        }), 200

    except Exception as e:
        print(f"❌ [API] 저장 처리 중 예외 발생: {str(e)}")
        return jsonify({"status": "error", "message": f"서버 저장 실패: {str(e)}"}), 500

@app.route('/api/reset', methods=['POST', 'OPTIONS'])
def reset_state():
    """
    사용자가 초기화를 원할 때 로컬에 영구 저장된 커스텀 상태 파일들을 삭제하고
    대시보드를 최초 추천 구조로 재생성합니다.
    """
    if request.method == 'OPTIONS':
        return '', 200

    try:
        cache_dir = "data"
        week_plan_path = os.path.join(cache_dir, "week_plan.json")
        routines_path = os.path.join(cache_dir, "routines_today.json")
        coach_comment_path = os.path.join(cache_dir, "coach_comment.json")
        next_running_path = os.path.join(cache_dir, "next_running.json")

        deleted_files = []
        if os.path.exists(week_plan_path):
            os.remove(week_plan_path)
            deleted_files.append("week_plan.json")
        if os.path.exists(routines_path):
            os.remove(routines_path)
            deleted_files.append("routines_today.json")
        if os.path.exists(coach_comment_path):
            os.remove(coach_comment_path)
            deleted_files.append("coach_comment.json")
        if os.path.exists(next_running_path):
            os.remove(next_running_path)
            deleted_files.append("next_running.json")

        print(f"🗑️ [API] 커스텀 상태 파일 삭제 완료: {deleted_files}")

        # 비동기로 coach.py 컴파일러를 기동하여 최초 추천 훈련 및 루틴 복구
        threading.Thread(target=run_coach_script).start()

        return jsonify({
            "status": "success", 
            "message": "로컬 영구 커스텀 데이터가 성공적으로 초기화되었습니다!"
        }), 200

    except Exception as e:
        print(f"❌ [API] 초기화 처리 중 예외 발생: {str(e)}")
        return jsonify({"status": "error", "message": f"서버 초기화 실패: {str(e)}"}), 500

@app.route('/webhook', methods=['GET'])
def webhook_verify():
    """
    Strava 웹훅 신규 구독 등록 시 검증(Verification) 절차 처리
    """
    hub_mode = request.args.get('hub.mode')
    hub_challenge = request.args.get('hub.challenge')
    hub_verify_token = request.args.get('hub.verify_token')
    
    if hub_mode == 'subscribe' and hub_challenge:
        if hub_verify_token == VERIFY_TOKEN:
            print("✅ [Webhook] Subscription verified successfully!")
            return jsonify({"hub.challenge": hub_challenge}), 200
        else:
            print("❌ [Webhook] Subscription verification failed: Token mismatch.")
            return "Forbidden", 403
            
    return "Bad Request", 400

@app.route('/webhook', methods=['POST'])
def webhook_event():
    """
    가민/스트라바에 운동이 저장되었을 때 호출되는 이벤트 수신 API
    """
    data = request.json
    print(f"📥 [Webhook] Received event: {data}")
    
    object_type = data.get('object_type') # 'activity', 'athlete' 등
    aspect_type = data.get('aspect_type') # 'create', 'update', 'delete' 등
    
    # 새로운 러닝 운동이 생성('create')되었을 때만 업데이트 실행
    if object_type == 'activity' and aspect_type == 'create':
        print("🏃‍♂️ [Webhook] New activity created! Triggering dashboard update...")
        # 2초 내에 응답해야 하므로, 스크립트 실행은 백그라운드 스레드에서 즉시 처리
        threading.Thread(target=run_coach_script).start()
        
    return jsonify({"status": "event_processed"}), 200

@app.route('/api/save_settings', methods=['POST', 'OPTIONS'])
def save_settings():
    if request.method == 'OPTIONS':
        return '', 200

    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "데이터가 없습니다."}), 400

        client_id = data.get("strava_client_id", "").strip()
        client_secret = data.get("strava_client_secret", "").strip()
        refresh_token = data.get("strava_refresh_token", "").strip()
        gemini_api_key = data.get("gemini_api_key", "").strip()

        env_path = ".env"
        env_dict = {}
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in lines:
                if "=" in line:
                    k, v = line.split("=", 1)
                    env_dict[k.strip()] = v.strip()

        # Update values
        if client_id:
            env_dict["STRAVA_CLIENT_ID"] = client_id
        if client_secret:
            env_dict["STRAVA_CLIENT_SECRET"] = client_secret
        if refresh_token:
            env_dict["STRAVA_REFRESH_TOKEN"] = refresh_token
        if gemini_api_key:
            env_dict["GEMINI_API_KEY"] = gemini_api_key

        # Write back
        with open(env_path, "w", encoding="utf-8") as f:
            for k, v in env_dict.items():
                f.write(f"{k}={v}\n")

        print("💾 [API] .env 파일이 성공적으로 갱신되었습니다.")

        # Recompile coach dashboard in background
        threading.Thread(target=run_coach_script).start()

        return jsonify({
            "status": "success",
            "message": "Strava 및 Gemini 연동 설정이 로컬 .env 파일에 성공적으로 저장되었으며, 대시보드 리빌드가 트리거되었습니다!"
        }), 200

    except Exception as e:
        print(f"❌ [API] 설정 저장 중 예외 발생: {str(e)}")
        return jsonify({"status": "error", "message": f"설정 저장 실패: {str(e)}"}), 500

@app.route('/api/sync', methods=['POST', 'OPTIONS'])
def sync_data():
    if request.method == 'OPTIONS':
        return '', 200

    try:
        # 1. strava_cache.json 삭제 (새로운 스트라바 데이터를 강제 다운로드하기 위함)
        cache_path = os.path.join("data", "strava_cache.json")
        if os.path.exists(cache_path):
            os.remove(cache_path)
            print("🗑️ [API] 강제 동기화를 위해 기존 strava_cache.json 캐시를 삭제했습니다.")

        # 2. 동기적으로 coach.py를 실행하여 스트라바로부터 최신 데이터를 당겨오고 index.html 빌드
        script_dir = os.path.dirname(os.path.abspath(__file__))
        result = subprocess.run(
            ["python3", "coach.py"],
            cwd=script_dir,
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print("🎉 [API] coach.py 동기화 빌드가 완료되었습니다.")
            return jsonify({
                "status": "success",
                "message": "Strava 활동 데이터 동기화 및 대시보드 리빌드가 완료되었습니다!"
            }), 200
        else:
            print("❌ [API] coach.py 동기화 빌드 중 오류:")
            print(result.stderr)
            return jsonify({
                "status": "error",
                "message": f"동기화 컴파일러 오류: {result.stderr}"
            }), 500

    except Exception as e:
        print(f"❌ [API] 동기화 중 예외 발생: {str(e)}")
        return jsonify({"status": "error", "message": f"서버 동기화 실패: {str(e)}"}), 500

if __name__ == '__main__':
    print("🚀 Project 330 Webhook & DB Server starting on http://localhost:8000")
    # 로컬 포트 8000으로 서버 가동
    app.run(host='0.0.0.0', port=8000)
