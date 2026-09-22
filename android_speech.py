"""Nhận dạng giọng nói (SpeechRecognizer) và đọc văn bản (TextToSpeech)
của Android, gọi qua pyjnius. Trên máy tính (không phải Android) các lớp
này tự vô hiệu hoá để app vẫn chạy được ở chế độ gõ chữ.
"""
from kivy.utils import platform

IS_ANDROID = platform == "android"

ERROR_TEXT = {
    1: "Mạng quá chậm",
    2: "Lỗi mạng",
    3: "Lỗi ghi âm",
    4: "Lỗi máy chủ nhận dạng",
    5: "Lỗi phía ứng dụng",
    6: "Không nghe thấy tiếng nói",
    7: "Không nhận ra câu nói",
    8: "Bộ nhận dạng đang bận",
    9: "Chưa cấp quyền micro",
    11: "Máy chủ bị ngắt kết nối",
    12: "Ngôn ngữ chưa được hỗ trợ",
    13: "Gói ngôn ngữ chưa tải về máy",
}

if IS_ANDROID:
    from jnius import autoclass, PythonJavaClass, java_method
    from android.runnable import run_on_ui_thread

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    SpeechRecognizer = autoclass("android.speech.SpeechRecognizer")
    RecognizerIntent = autoclass("android.speech.RecognizerIntent")
    Intent = autoclass("android.content.Intent")
    TextToSpeech = autoclass("android.speech.tts.TextToSpeech")
    Locale = autoclass("java.util.Locale")

    class _Listener(PythonJavaClass):
        __javainterfaces__ = ["android/speech/RecognitionListener"]
        __javacontext__ = "app"

        def __init__(self, owner):
            super().__init__()
            self.owner = owner

        @staticmethod
        def _first(bundle):
            if bundle is None:
                return ""
            arr = bundle.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
            if arr is None or arr.size() == 0:
                return ""
            return arr.get(0) or ""

        @java_method("(Landroid/os/Bundle;)V")
        def onReadyForSpeech(self, params):
            self.owner._emit("on_state", True)

        @java_method("()V")
        def onBeginningOfSpeech(self):
            pass

        @java_method("(F)V")
        def onRmsChanged(self, rms):
            self.owner._emit("on_rms", rms)

        @java_method("([B)V")
        def onBufferReceived(self, buf):
            pass

        @java_method("()V")
        def onEndOfSpeech(self):
            pass

        @java_method("(I)V")
        def onError(self, code):
            self.owner._emit("on_state", False)
            self.owner._emit("on_error", code, ERROR_TEXT.get(code, f"Lỗi {code}"))

        @java_method("(Landroid/os/Bundle;)V")
        def onResults(self, bundle):
            self.owner._emit("on_state", False)
            self.owner._emit("on_final", self._first(bundle))

        @java_method("(Landroid/os/Bundle;)V")
        def onPartialResults(self, bundle):
            text = self._first(bundle)
            if text:
                self.owner._emit("on_partial", text)

        @java_method("(ILandroid/os/Bundle;)V")
        def onEvent(self, event_type, params):
            pass

        # Các hàm mặc định có từ Android 13/14 – khai báo để tránh lỗi proxy
        @java_method("(Landroid/os/Bundle;)V")
        def onSegmentResults(self, bundle):
            pass

        @java_method("()V")
        def onEndOfSegmentedSession(self):
            pass

        @java_method("(Landroid/os/Bundle;)V")
        def onLanguageDetection(self, bundle):
            pass

    class _TTSInit(PythonJavaClass):
        __javainterfaces__ = ["android/speech/tts/TextToSpeech$OnInitListener"]
        __javacontext__ = "app"

        def __init__(self, owner):
            super().__init__()
            self.owner = owner

        @java_method("(I)V")
        def onInit(self, status):
            self.owner.ready = status == TextToSpeech.SUCCESS


class SpeechInput:
    """Bọc SpeechRecognizer. Các callback (on_partial, on_final, on_error,
    on_state, on_rms) được gọi lại trên luồng chính của Kivy."""

    def __init__(self, **callbacks):
        self.callbacks = callbacks
        self.available = False
        self._rec = None
        self._listener = None
        if IS_ANDROID:
            self._setup()

    def _emit(self, name, *args):
        from kivy.clock import Clock
        cb = self.callbacks.get(name)
        if cb:
            Clock.schedule_once(lambda dt: cb(*args), 0)

    if IS_ANDROID:
        @run_on_ui_thread
        def _setup(self):
            act = PythonActivity.mActivity
            self.available = bool(SpeechRecognizer.isRecognitionAvailable(act))
            if not self.available:
                self._emit("on_error", -1, "Máy chưa có dịch vụ nhận dạng giọng nói")
                return
            self._rec = SpeechRecognizer.createSpeechRecognizer(act)
            self._listener = _Listener(self)
            self._rec.setRecognitionListener(self._listener)

        @run_on_ui_thread
        def start(self, lang_tag):
            if self._rec is None:
                return
            it = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            it.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                        RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            it.putExtra(RecognizerIntent.EXTRA_LANGUAGE, lang_tag)
            it.putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, lang_tag)
            it.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, True)
            it.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
            it.putExtra("android.speech.extra.DICTATION_MODE", True)
            self._rec.cancel()
            self._rec.startListening(it)

        @run_on_ui_thread
        def stop(self):
            if self._rec is not None:
                self._rec.stopListening()

        @run_on_ui_thread
        def cancel(self):
            if self._rec is not None:
                self._rec.cancel()
            self._emit("on_state", False)

        @run_on_ui_thread
        def destroy(self):
            if self._rec is not None:
                self._rec.destroy()
                self._rec = None
    else:
        def start(self, lang_tag):
            self._emit("on_error", -1, "Nhận dạng giọng nói chỉ có trên Android")

        def stop(self):
            pass

        def cancel(self):
            pass

        def destroy(self):
            pass


class SpeechOutput:
    """Bọc TextToSpeech."""

    LOCALES = {"vi": ("vi", "VN"), "en": ("en", "US")}

    def __init__(self):
        self.ready = False
        self._tts = None
        self._init_cb = None
        if IS_ANDROID:
            self._init_cb = _TTSInit(self)
            self._tts = TextToSpeech(PythonActivity.mActivity, self._init_cb)

    def speak(self, text, lang):
        if not (self._tts and self.ready and text):
            return False
        lc = self.LOCALES.get(lang, (lang, ""))
        res = self._tts.setLanguage(Locale(*lc))
        if res < 0:  # LANG_MISSING_DATA (-1) / LANG_NOT_SUPPORTED (-2)
            return False
        self._tts.speak(text, TextToSpeech.QUEUE_FLUSH, None, "utt")
        return True

    def is_speaking(self):
        return bool(self._tts and self._tts.isSpeaking())

    def stop(self):
        if self._tts:
            self._tts.stop()

    def shutdown(self):
        if self._tts:
            self._tts.shutdown()
            self._tts = None
