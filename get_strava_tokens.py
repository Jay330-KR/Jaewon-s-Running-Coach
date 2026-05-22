import os
import requests
from dotenv import load_dotenv

# .env 로드 (있는 경우)
load_dotenv()

def get_tokens():
    print("==================================================")
    print("🏃‍♂️ Project330 - Strava OAuth2 Token Generator 🏃‍♂️")
    print("==================================================")

    # 1. 환경 변수 또는 직접 입력으로 Client ID, Secret 받기
    client_id = os.getenv("STRAVA_CLIENT_ID") or input("1. Strava CLIENT ID를 입력하세요: ").strip()
    client_secret = os.getenv("STRAVA_CLIENT_SECRET") or input("2. Strava CLIENT SECRET을 입력하세요: ").strip()

    if not client_id or not client_secret:
        print("❌ 오류: Client ID와 Client Secret이 필요합니다.")
        return

    # 2. 인증 URL 생성
    # scope는 활동 데이터를 가져오기 위해 'activity:read_all'이 필요합니다.
    redirect_uri = "http://localhost"
    auth_url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=read,activity:read_all"
    )

    print("\n👉 아래 링크를 복사하여 웹 브라우저 주소창에 붙여넣고 로그인 및 승인을 완료해 주세요:")
    print("-" * 80)
    print(auth_url)
    print("-" * 80)

    print("\n💡 승인을 완료하면 브라우저 주소창이 다음과 같이 변경됩니다:")
    print("   http://localhost/?state=&code=xxxxxxxxxxxx&scope=read,activity:read_all")
    print("   이 주소창에서 'code=' 뒤에 있는 영어+숫자 조합(xxxxxxxxxxxx)을 복사해 주세요.")

    # 3. Code 입력 받기
    code = input("\n3. 복사한 'code' 값을 여기에 입력해 주세요: ").strip()

    if not code:
        print("❌ 오류: 유효한 code가 입력되지 않았습니다.")
        return

    # 4. Access Token & Refresh Token 교환
    print("\n🔄 Strava API와 통신하여 토큰을 발급받는 중...")
    token_url = "https://www.strava.com/oauth/token"
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code"
    }

    try:
        response = requests.post(token_url, data=payload)
        res_data = response.json()

        if response.status_code == 200:
            access_token = res_data.get("access_token")
            refresh_token = res_data.get("refresh_token")
            athlete = res_data.get("athlete", {})
            firstname = athlete.get("firstname", "러너")

            print("\n🎉 토큰 발급 성공!")
            print(f"반갑습니다, {firstname}님!")
            print("-" * 50)
            print(f"▶ STRAVA_REFRESH_TOKEN: {refresh_token}")
            print(f"▶ STRAVA_ACCESS_TOKEN (임시): {access_token}")
            print("-" * 50)
            print("\n💡 [다음 단계] 이 Refresh Token 값을 프로젝트 폴더의 '.env' 파일에 저장해 주세요.")
            
            # 자동으로 .env 파일 생성/업데이트 시도
            env_path = ".env"
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(f"STRAVA_CLIENT_ID={client_id}\n")
                f.write(f"STRAVA_CLIENT_SECRET={client_secret}\n")
                f.write(f"STRAVA_REFRESH_TOKEN={refresh_token}\n")
                f.write("WEBHOOK_VERIFY_TOKEN=PROJECT330_TOKEN\n")
            print("💾 로컬 디렉토리에 .env 파일이 성공적으로 작성되었습니다!")

        else:
            print("\n❌ 토큰 발급 실패:")
            print(res_data)
    except Exception as e:
        print(f"\n❌ 에러 발생: {str(e)}")

if __name__ == "__main__":
    get_tokens()
