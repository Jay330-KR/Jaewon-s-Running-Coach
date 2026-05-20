import os
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
    print("🔄 [Webhook] Starting coach.py execution in background...")
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
            print("🎉 [Webhook] coach.py completed successfully!")
            print(result.stdout)
        else:
            print("❌ [Webhook] coach.py failed with error:")
            print(result.stderr)
            
    except Exception as e:
        print(f"❌ [Webhook] Failed to run coach.py: {str(e)}")

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

if __name__ == '__main__':
    print("🚀 Project 330 Webhook Server starting on http://localhost:8000")
    # 로컬 포트 8000으로 서버 가동
    app.run(host='0.0.0.0', port=8000)
