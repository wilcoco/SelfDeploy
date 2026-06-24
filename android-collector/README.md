# 안드로이드 수집기 (NotificationListenerService)

카카오톡 단톡방 알림을 가로채 서버(`POST /ingest`)로 전송하는 **수집 전용** 앱 예제입니다.

> ⚠️ **경고**
> - 이 방식은 카카오톡 **공식 API가 아니며 이용약관 위반 소지**가 있습니다. **반드시 수집 전용 단말 + 전용(또는 부계정)으로만** 운영하세요.
> - 알림에 **표시되는 텍스트만** 수집됩니다. 긴 메시지는 잘리고, 사진/파일/이모티콘은 본문을 읽을 수 없습니다.
> - 단톡방 미리보기(알림 본문 표시)가 켜져 있어야 발신자/본문이 들어옵니다.
> - 참여자 동의 없이 운영하지 마세요. (`../docs/consent-template.md`)

## 동작 원리

1. 사용자가 `설정 > 알림 > 특수 접근 > 알림 접근`에서 이 앱에 권한을 부여합니다.
2. 카카오톡(`com.kakao.talk) 알림이 오면 `onNotificationPosted` 가 호출됩니다.
3. 알림에서 **방 이름(title)**, **발신자/본문(text)** 을 추출해 서버로 HTTPS POST 합니다.

## 핵심 코드

`KakaoNotificationListener.kt` 참고. 핵심만 요약하면:

- `title` → 단톡방 이름 (또는 "발신자 (방이름)" 형식일 수 있어 파싱 필요)
- `android.text` / `EXTRA_TEXT` → 메시지 본문
- 카카오톡은 한 알림에 여러 줄(`EXTRA_TEXT_LINES`)을 묶어 보내기도 하므로 마지막 줄을 최신 메시지로 사용

## 설정 (서버 주소·토큰)

`KakaoNotificationListener.kt` 상단 상수를 환경에 맞게 변경:

```kotlin
private const val INGEST_URL = "https://your-server.example.com/ingest"
private const val INGEST_TOKEN = "change-me-to-a-long-random-string" // 서버 .env 의 INGEST_TOKEN 과 동일
```

## AndroidManifest.xml 등록

```xml
<service
    android:name=".KakaoNotificationListener"
    android:label="SelfDeploy 수집기"
    android:permission="android.permission.BIND_NOTIFICATION_LISTENER_SERVICE"
    android:exported="false">
    <intent-filter>
        <action android:name="android.service.notification.NotificationListenerService" />
    </intent-filter>
</service>
```

## 권한 부여

설정 → 앱 → 특수 접근 권한 → **알림 접근(Notification access)** → 본 앱 ON.
(코드에서 `Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS` 인텐트로 안내 화면을 띄울 수 있습니다.)

## 운영 팁

- **유실 방지**: 네트워크 실패 시 로컬 큐(Room DB)에 쌓고 재전송하세요. (아래 예제는 단순 전송만 구현)
- **배터리/절전 예외**: 제조사 절전 기능이 서비스를 종료할 수 있으니 배터리 최적화 예외 처리 권장.
- **중복/시스템 알림 필터링**: "메시지 도착", "OO개의 안 읽은 메시지" 등 요약 알림은 건너뛰세요.
