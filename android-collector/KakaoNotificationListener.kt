package com.example.selfdeploy

import android.app.Notification
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Log
import org.json.JSONObject
import java.io.OutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.concurrent.thread

/**
 * 카카오톡 알림을 가로채 수집 서버로 전송하는 NotificationListenerService.
 *
 * 주의: 비공식 방식이며 카카오 약관 위반 소지가 있음. 수집 전용 단말에서만 사용.
 */
class KakaoNotificationListener : NotificationListenerService() {

    companion object {
        private const val TAG = "SelfDeployCollector"
        private const val KAKAO_PACKAGE = "com.kakao.talk"

        // === 환경에 맞게 변경 ===
        private const val INGEST_URL = "https://your-server.example.com/ingest"
        private const val INGEST_TOKEN = "change-me-to-a-long-random-string"

        // 수집에서 제외할 요약/시스템 알림 문구
        private val SKIP_KEYWORDS = listOf("개의 메시지", "안 읽은 메시지", "메시지 도착")
    }

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        if (sbn.packageName != KAKAO_PACKAGE) return

        val extras = sbn.notification.extras
        val title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString().orEmpty()

        // 여러 줄 알림이면 마지막 줄(최신 메시지)을 사용, 아니면 EXTRA_TEXT
        val lines = extras.getCharSequenceArray(Notification.EXTRA_TEXT_LINES)
        val text = (lines?.lastOrNull()?.toString()
            ?: extras.getCharSequence(Notification.EXTRA_TEXT)?.toString())
            .orEmpty()

        if (title.isBlank() || text.isBlank()) return
        if (SKIP_KEYWORDS.any { text.contains(it) }) return

        // 카카오톡 단톡방 알림은 보통 title=방이름, text="발신자 : 내용" 형태
        val (sender, body) = parseSenderAndBody(text)

        send(room = title, sender = sender, text = body, postedAt = sbn.postTime)
    }

    /** "홍길동 : 메시지 내용" → (홍길동, 메시지 내용). 구분자가 없으면 발신자=방. */
    private fun parseSenderAndBody(text: String): Pair<String, String> {
        val idx = text.indexOf(" : ")
        return if (idx > 0) {
            text.substring(0, idx) to text.substring(idx + 3)
        } else {
            "" to text
        }
    }

    private fun send(room: String, sender: String, text: String, postedAt: Long) {
        val iso = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ssXXX", Locale.US).format(Date(postedAt))
        val payload = JSONObject().apply {
            put("room", room)
            put("sender", sender.ifBlank { room })
            put("text", text)
            put("ts", iso)
        }.toString()

        // TODO: 운영 시 네트워크 실패 대비 로컬 큐(Room) + 재시도 적용
        thread {
            try {
                val conn = (URL(INGEST_URL).openConnection() as HttpURLConnection).apply {
                    requestMethod = "POST"
                    setRequestProperty("Content-Type", "application/json")
                    setRequestProperty("Authorization", "Bearer $INGEST_TOKEN")
                    doOutput = true
                    connectTimeout = 5000
                    readTimeout = 5000
                }
                conn.outputStream.use { os: OutputStream ->
                    os.write(payload.toByteArray(Charsets.UTF_8))
                }
                val code = conn.responseCode
                if (code !in 200..299) Log.w(TAG, "ingest failed: HTTP $code")
                conn.disconnect()
            } catch (e: Exception) {
                Log.e(TAG, "ingest error", e)
            }
        }
    }
}
