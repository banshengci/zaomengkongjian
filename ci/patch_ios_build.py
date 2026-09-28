"""CI 修补：wkbin/zaomeng iosMain 在命令行可编译，用于 TrollStore IPA。"""

from pathlib import Path

ROOT = Path("upstream/zaomeng/kmp")
OPTIN = "@file:OptIn(kotlinx.cinterop.ExperimentalForeignApi::class)\n"

STREAMING = ROOT / "data/remote/src/iosMain/kotlin/top/wkbin/zaomeng/data/api/StreamingHttp.ios.kt"
DATASTORE = ROOT / "data/remote/src/iosMain/kotlin/top/wkbin/zaomeng/data/preferences/CreateDataStore.ios.kt"
BACKEND = ROOT / "server/src/commonMain/kotlin/top/wkbin/zaomeng/backend/LocalBackendController.kt"
UI_SHARED_BUILD = ROOT / "ui/shared/build.gradle.kts"
TTS = ROOT / "ui/shared/src/iosMain/kotlin/top/wkbin/zaomeng/platform/PlatformTts.ios.kt"

TTS_STUB = r'''package top.wkbin.zaomeng.platform

import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** CI stub: avoid AVSpeech delegate overload clash on Kotlin/Native. */
internal class IosPlatformTts : PlatformTts {
    private val _isSpeaking = MutableStateFlow(false)
    override val isSpeaking: StateFlow<Boolean> = _isSpeaking.asStateFlow()
    private val _currentSpeakingId = MutableStateFlow<String?>(null)
    override val currentSpeakingId: StateFlow<String?> = _currentSpeakingId.asStateFlow()

    override fun speak(
        id: String,
        text: String,
        pitch: Float,
        speed: Float,
        voiceName: String,
    ) {
        _isSpeaking.value = false
        _currentSpeakingId.value = null
    }

    override fun stop() {
        _isSpeaking.value = false
        _currentSpeakingId.value = null
    }

    override fun shutdown() {
        stop()
    }
}

@Composable
actual fun rememberPlatformTts(): PlatformTts {
    val platformTts = remember { IosPlatformTts() }
    DisposableEffect(Unit) {
        onDispose {
            platformTts.stop()
        }
    }
    return platformTts
}
'''

STREAMING_BODY = r'''package top.wkbin.zaomeng.data.api

import io.ktor.client.HttpClient
import io.ktor.client.engine.darwin.Darwin
import io.ktor.client.plugins.HttpTimeout
import io.ktor.client.request.header
import io.ktor.client.request.preparePost
import io.ktor.client.request.setBody
import io.ktor.client.statement.bodyAsChannel
import io.ktor.http.ContentType
import io.ktor.http.HttpHeaders
import io.ktor.http.isSuccess
import io.ktor.utils.io.ByteReadChannel
import io.ktor.utils.io.readAvailable
import kotlinx.coroutines.runBlocking
import okio.Buffer
import okio.BufferedSource
import okio.Source
import okio.Timeout
import okio.buffer

private val darwinStreamingClient: HttpClient by lazy {
    HttpClient(Darwin) {
        expectSuccess = false
        install(HttpTimeout) {
            connectTimeoutMillis = 3_000
            requestTimeoutMillis = 0
            socketTimeoutMillis = 5 * 60 * 1000
        }
    }
}

actual fun openStreamingResponse(url: String, jsonBody: String, token: String): BufferedSource {
    val response = runBlocking {
        darwinStreamingClient.preparePost(url) {
            header(HttpHeaders.ContentType, ContentType.Application.Json.toString())
            setBody(jsonBody)
            header(HttpHeaders.Authorization, "Bearer $token")
        }.execute()
    }
    check(response.status.isSuccess()) { "Streaming request failed: ${response.status}" }
    val channel = runBlocking { response.bodyAsChannel() }
    return ByteReadChannelSource(channel).buffer()
}

private class ByteReadChannelSource(
    private val channel: ByteReadChannel,
) : Source {
    override fun read(sink: Buffer, byteCount: Long): Long {
        if (channel.isClosedForRead) return -1L
        val size = minOf(byteCount, 8192L).toInt()
        val bytes = ByteArray(size)
        val read = runBlocking { channel.readAvailable(bytes, 0, size) }
        if (read < 0) return -1L
        if (read == 0) return if (channel.isClosedForRead) -1L else 0L
        sink.write(bytes, 0, read)
        return read.toLong()
    }

    override fun timeout(): Timeout = Timeout.NONE

    override fun close() {
        channel.cancel(null)
    }
}
'''


def ensure_optin(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "ExperimentalForeignApi" in text:
        return
    if text.startswith("package "):
        idx = text.find("package ")
        text = text[:idx] + OPTIN + text[idx:]
    else:
        text = OPTIN + text
    path.write_text(text, encoding="utf-8")


def patch_backend(path: Path) -> None:
    if not path.exists():
        return
    t = path.read_text(encoding="utf-8")
    t = t.replace("@Volatile\n", "")
    t = t.replace(
        """        if (started) return
        synchronized(this) {
            if (started) return
            started = true
        }
""",
        """        if (started) return
        started = true
""",
    )
    t = t.replace("synchronized(this) {", "run {")
    path.write_text(t, encoding="utf-8")


def patch_text_decoding(path: Path) -> None:
    if not path.exists():
        return
    t = path.read_text(encoding="utf-8")
    if "usePinned" not in t.split("actual")[0]:
        t = t.replace(
            "import platform.Foundation.create",
            "import kotlinx.cinterop.addressOf\nimport kotlinx.cinterop.usePinned\nimport platform.Foundation.create",
        )
    path.write_text(t, encoding="utf-8")


def patch_image_loader(path: Path) -> None:
    if not path.exists():
        return
    t = path.read_text(encoding="utf-8")
    t = t.replace("readByteArray()", "readByteArray")
    t = t.replace(".read {", ".readByteArray()")
    path.write_text(t, encoding="utf-8")


def patch_gradle_optin(path: Path) -> None:
    if not path.exists():
        return
    t = path.read_text(encoding="utf-8")
    if "ExperimentalForeignApi" in t:
        return
    t += """

// CI patch: allow cinterop APIs without per-file OptIn noise
tasks.withType(org.jetbrains.kotlin.gradle.tasks.KotlinCompile::class.java).configureEach {
    compilerOptions.optIn.add("kotlinx.cinterop.ExperimentalForeignApi")
}
"""
    path.write_text(t, encoding="utf-8")


def main() -> None:
    STREAMING.parent.mkdir(parents=True, exist_ok=True)
    STREAMING.write_text(STREAMING_BODY, encoding="utf-8")
    print("wrote", STREAMING)

    if DATASTORE.exists():
        ensure_optin(DATASTORE)

    patch_backend(BACKEND)

    ui_ios = ROOT / "ui/shared/src/iosMain"
    if ui_ios.exists():
        for p in ui_ios.rglob("*.kt"):
            ensure_optin(p)
        patch_text_decoding(ui_ios / "kotlin/top/wkbin/zaomeng/platform/TextDecoding.ios.kt")
        patch_image_loader(ui_ios / "kotlin/top/wkbin/zaomeng/platform/PlatformImageLoader.ios.kt")

    # 所有 iosMain 都加 opt-in
    for p in ROOT.rglob("iosMain/**/*.kt"):
        ensure_optin(p)

    if TTS.exists():
        TTS.write_text(TTS_STUB, encoding="utf-8")
        print("stubbed TTS", TTS)

    patch_gradle_optin(UI_SHARED_BUILD)
    print("patch done")


if __name__ == "__main__":
    main()
