"""CI 修补：wkbin/zaomeng iosMain 可编译，用于 TrollStore IPA。"""

from pathlib import Path

ROOT = Path("upstream/zaomeng/kmp")
OPTIN = "@file:OptIn(kotlinx.cinterop.ExperimentalForeignApi::class)\n"

STREAMING = ROOT / "data/remote/src/iosMain/kotlin/top/wkbin/zaomeng/data/api/StreamingHttp.ios.kt"
DATASTORE = ROOT / "data/remote/src/iosMain/kotlin/top/wkbin/zaomeng/data/preferences/CreateDataStore.ios.kt"
BACKEND = ROOT / "server/src/commonMain/kotlin/top/wkbin/zaomeng/backend/LocalBackendController.kt"
RUN_DETAIL = (
    ROOT
    / "feature/rundetail/src/commonMain/kotlin/top/wkbin/zaomeng/feature/rundetail/RunDetailScreen.kt"
)
MODEL_SETTINGS = (
    ROOT
    / "feature/settings/src/commonMain/kotlin/top/wkbin/zaomeng/feature/settings/ModelSettingsScreen.kt"
)
MAIN_VC = ROOT / "app/shared/src/iosMain/kotlin/top/wkbin/zaomeng/app/shared/MainViewController.ios.kt"
NAV_HOST = ROOT / "app/shared/src/commonMain/kotlin/top/wkbin/zaomeng/navigation/ZaomengNavHost.kt"
LIBS_TOML = ROOT / "gradle/libs.versions.toml"
GRADLE_PROPS = ROOT / "gradle.properties"
UI_IOS = ROOT / "ui/shared/src/iosMain"

MAIN_VC_STUB = r'''package top.wkbin.zaomeng.app.shared

import androidx.compose.ui.window.ComposeUIViewController
import org.koin.core.context.startKoin
import platform.UIKit.UIViewController
import top.wkbin.zaomeng.data.preferences.ThemeMode
import top.wkbin.zaomeng.data.preferences.UI_SCALE_DEFAULT
import top.wkbin.zaomeng.di.IosAppPlatform
import top.wkbin.zaomeng.di.sharedAppModules

/** iOS 入口（CI stub）：不依赖 GlobalContext/currentPreferences。 */
fun MainViewController(): UIViewController {
    startKoin { modules(sharedAppModules(IosAppPlatform)) }
    return ComposeUIViewController {
        App(
            initialThemeMode = ThemeMode.SYSTEM,
            initialThemeSeedColorArgb = 0L,
            initialDynamicColorEnabled = false,
            initialUiScale = UI_SCALE_DEFAULT,
        )
    }
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

UI_PLATFORM_STUB = r'''package top.wkbin.zaomeng.platform

import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.graphics.ImageBitmap
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

actual fun cropAvatarBytes(bytes: ByteArray, side: Int, left: Int, top: Int): ByteArray = bytes

actual fun backHandlingToggleSupported(): Boolean = false

@Composable
actual fun rememberClipboardTextWriter(): suspend (String) -> Unit = {}

@Composable
actual fun rememberOpenExternalUrl(): (String) -> Unit = {}

@Composable
actual fun rememberToast(): (String) -> Unit = {}

@Composable
actual fun rememberNotificationPermissionRequester(onResult: (Boolean) -> Unit): () -> Unit = {
    onResult(false)
}

@Composable
actual fun PlatformBackHandler(enabled: Boolean, onBack: () -> Unit) {
}

@Composable
actual fun rememberPlatformImage(uri: String): ImageBitmap? = null

@Composable
actual fun rememberShareText(): (String) -> Unit = {}

actual fun decodeGb18030Strict(bytes: ByteArray): String? = bytes.decodeToString()

actual fun readZipFileEntries(bytes: ByteArray): List<ZipFileEntryData> = emptyList()

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
        onDispose { platformTts.stop() }
    }
    return platformTts
}
'''

UI_GRAPHICS_STUB = r'''package top.wkbin.zaomeng.ui.graphics

import androidx.compose.ui.graphics.ImageBitmap

actual fun decodeImageBitmap(bytes: ByteArray): ImageBitmap? = null
'''

UI_THEME_STUB = r'''package top.wkbin.zaomeng.ui.theme

import androidx.compose.material3.ColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

@Composable
actual fun platformColorScheme(
    darkTheme: Boolean,
    dynamicColor: Boolean,
    seedColorArgb: Long,
): ColorScheme? = null

@Composable
actual fun applySystemBars(darkTheme: Boolean, windowBackground: Color) {
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


def patch_run_detail(path: Path) -> None:
    """commonMain 不能用 JVM 的 String.format 扩展。"""
    if not path.exists():
        return
    t = path.read_text(encoding="utf-8")
    t = t.replace(
        'add("%.1f MB".format(source.byteSize / (1024.0 * 1024.0)))',
        'add("${(source.byteSize / (1024.0 * 1024.0)).toString().let { if (it.contains(".")) it.take(it.indexOf(".") + 2) else it }} MB")',
    )
    t = t.replace(
        'add("%.1f KB".format(source.byteSize / 1024.0))',
        'add("${(source.byteSize / 1024.0).toString().let { if (it.contains(".")) it.take(it.indexOf(".") + 2) else it }} KB")',
    )
    # 兜底：其它 .format( 调用改为模板
    t = t.replace('".format(', '" + (')
    path.write_text(t, encoding="utf-8")
    print("patched run_detail", path)


def patch_jvm_apis(root: Path) -> None:
    """commonMain 禁用 JVM 专有 API：String.format / androidx.compose.ui.res / @Volatile / synchronized。"""
    for p in root.rglob("commonMain/**/*.kt"):
        t = p.read_text(encoding="utf-8")
        orig = t
        t = t.replace("import androidx.compose.ui.res.painterResource", "import org.jetbrains.compose.resources.painterResource")
        t = t.replace("import androidx.compose.ui.res.stringResource", "import org.jetbrains.compose.resources.stringResource")
        t = t.replace("@Volatile\n", "")
        t = t.replace("synchronized(this) {", "run {")
        # "%.1f X".format(...) → 模板
        t = t.replace('add("%.1f MB".format(source.byteSize / (1024.0 * 1024.0)))',
                      'add("${source.byteSize / (1024.0 * 1024.0)} MB")')
        t = t.replace('add("%.1f KB".format(source.byteSize / 1024.0))',
                      'add("${source.byteSize / 1024.0} KB")')
        # 通用 "..." .format(...) 兜底（跳过含 % 的格式串，避免误伤）
        import re as _re

        def _fmt_repl(m: _re.Match[str]) -> str:
            if "%" in m.group(1):
                return m.group(0)
            return f'"{m.group(1)}" + ({m.group(2)}).toString()'

        t = _re.sub(r'"([^"]*)"\.format\(([^)]+)\)', _fmt_repl, t)
        if t != orig:
            p.write_text(t, encoding="utf-8")
            print("patched jvm-apis", p.relative_to(root))


def patch_navigationevent(root: Path) -> None:
    """绕过 navigationevent-compose 的 IR 重复符号：去依赖 + 去用法。"""
    toml = root / "gradle/libs.versions.toml"
    if toml.exists():
        t = toml.read_text(encoding="utf-8")
        # 保持 1.1.2（1.0.0 无 iOS 变体），但构建时剔除
        t = t.replace('navigationevent = "1.0.0"', 'navigationevent = "1.1.2"')
        toml.write_text(t, encoding="utf-8")

    shared = root / "app/shared/build.gradle.kts"
    if shared.exists():
        t = shared.read_text(encoding="utf-8")
        t = t.replace(
            "implementation(libs.androidx.navigationevent.compose)",
            "// implementation(libs.androidx.navigationevent.compose) // CI: IR duplicate symbol",
        )
        shared.write_text(t, encoding="utf-8")

    nav = root / "app/shared/src/commonMain/kotlin/top/wkbin/zaomeng/navigation/ZaomengNavHost.kt"
    if not nav.exists():
        return
    t = nav.read_text(encoding="utf-8")
    t = t.replace(
        "import androidx.navigationevent.compose.LocalNavigationEventDispatcherOwner\n",
        "",
    )
    t = t.replace(
        "import androidx.navigationevent.compose.rememberNavigationEventDispatcherOwner\n",
        "",
    )
    t = t.replace(
        """    val navEventOwner = rememberNavigationEventDispatcherOwner(
        enabled = builtInBackHandlingEnabled,
    )
""",
        "",
    )
    t = t.replace(
        "CompositionLocalProvider(LocalNavigationEventDispatcherOwner provides navEventOwner) {",
        "run {",
    )
    nav.write_text(t, encoding="utf-8")
    print("patched navigationevent usage")


def patch_gradle_memory(root: Path) -> None:
    """iOS 链接阶段 OOM：把 Gradle 堆调到 6G。"""
    props = root / "gradle.properties"
    if not props.exists():
        return
    t = props.read_text(encoding="utf-8")
    t = t.replace(
        "org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8",
        "org.gradle.jvmargs=-Xmx6g -XX:MaxMetaspaceSize=1g -Dfile.encoding=UTF-8",
    )
    if "kotlin.daemon.jvmargs" not in t:
        t += "\nkotlin.daemon.jvmargs=-Xmx6g\n"
    if "kotlin.native.cacheKind" not in t:
        t += "kotlin.native.cacheKind=none\n"
    props.write_text(t, encoding="utf-8")
    print("patched gradle memory")


def main() -> None:
    STREAMING.parent.mkdir(parents=True, exist_ok=True)
    STREAMING.write_text(STREAMING_BODY, encoding="utf-8")
    print("wrote streaming")

    if DATASTORE.exists():
        ensure_optin(DATASTORE)

    patch_backend(BACKEND)
    patch_run_detail(RUN_DETAIL)
    if MODEL_SETTINGS.exists():
        ensure_optin(MODEL_SETTINGS)
    if MAIN_VC.parent.exists():
        MAIN_VC.write_text(MAIN_VC_STUB, encoding="utf-8")
        print("stubbed MainViewController")
    patch_navigationevent(ROOT)
    patch_gradle_memory(ROOT)
    patch_jvm_apis(ROOT)

    # 覆盖 ui/shared iosMain：删掉 UIKit 相关实现，换成可编译 stub
    if UI_IOS.exists():
        for p in UI_IOS.rglob("*.kt"):
            p.unlink()
        pkg = UI_IOS / "kotlin/top/wkbin/zaomeng"
        (pkg / "platform").mkdir(parents=True, exist_ok=True)
        (pkg / "ui/graphics").mkdir(parents=True, exist_ok=True)
        (pkg / "ui/theme").mkdir(parents=True, exist_ok=True)
        (pkg / "platform/Stubs.ios.kt").write_text(UI_PLATFORM_STUB, encoding="utf-8")
        (pkg / "ui/graphics/ImageDecoding.ios.kt").write_text(UI_GRAPHICS_STUB, encoding="utf-8")
        (pkg / "ui/theme/PlatformTheme.ios.kt").write_text(UI_THEME_STUB, encoding="utf-8")
        print("replaced ui/shared iosMain with stubs")

    for p in ROOT.rglob("iosMain/**/*.kt"):
        ensure_optin(p)

    print("patch done")


if __name__ == "__main__":
    main()
