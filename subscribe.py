import os
import sys
import requests
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "PROJECT330_TOKEN")

if not CLIENT_ID or not CLIENT_SECRET:
    print("❌ 에러: .env 파일에 STRAVA_CLIENT_ID 또는 STRAVA_CLIENT_SECRET이 누락되었습니다.")
    sys.exit(1)

def view_subscriptions():
    """현재 등록된 웹훅 구독 목록을 조회합니다."""
    url = "https://www.strava.com/api/v3/push_subscriptions"
    params = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
    response = requests.get(url, params=params)
    print("\n🔍 현재 등록된 Strava Webhook 구독 목록:")
    print(response.json())

def create_subscription(callback_url):
    """새로운 웹훅 구독을 등록합니다."""
    url = "https://www.strava.com/api/v3/push_subscriptions"
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "callback_url": callback_url,
        "verify_token": VERIFY_TOKEN
    }
    response = requests.post(url, data=data)
    res_data = response.json()
    
    if response.status_code == 201:
        print(f"\n🎉 웹훅 구독 등록 성공!")
        print(f"Subscription ID: {res_data.get('id')}")
    else:
        print(f"\n❌ 웹훅 구독 등록 실패 (HTTP {response.status_code}):")
        print(res_data)

def delete_subscription(sub_id):
    """특정 구독 ID를 삭제합니다."""
    url = f"https://www.strava.com/api/v3/push_subscriptions/{sub_id}"
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
    response = requests.delete(url, data=data)
    if response.status_code == 204:
        print(f"\n🗑️ 구독 ID {sub_id}가 성공적으로 삭제되었습니다.")
    else:
        print(f"\n❌ 구독 삭제 실패 (HTTP {response.status_code}):")
        print(response.json())

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("💡 사용법:")
        print("  1) 목록 확인: python subscribe.py list")
        print("  2) 구독 등록: python subscribe.py create <ngrok_https_url>")
        print("  3) 구독 삭제: python subscribe.py delete <subscription_id>")
        sys.exit(0)
        
    action = sys.argv[1]
    
    if action == "list":
        view_subscriptions()
    elif action == "create":
        if len(sys.argv) < 3:
            print("❌ 에러: 웹훅으로 사용할 ngrok https 주소를 입력해주세요.")
            sys.exit(1)
        # 예: https://xxxx.ngrok-free.app/webhook
        callback_url = sys.argv[2]
        if not callback_url.startswith("https://"):
            print("⚠️ 경고: Strava 웹훅 callback_url은 반드시 https 주소여야 합니다.")
        create_subscription(callback_url)
    elif action == "delete":
        if len(sys.argv) < 3:
            print("❌ 에러: 삭제할 Subscription ID를 입력해주세요.")
            sys.exit(1)
        sub_id = sys.argv[2]
        delete_subscription(sub_id)
    else:
        print("❌ 올바르지 않은 명령입니다. (list, create, delete 중 선택)")
