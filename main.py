"""Phiên dịch song ngữ Anh - Việt thời gian thực cho Android (Kivy).

Nói tiếng Anh -> hiện chữ + dịch sang tiếng Việt ngay khi đang nói (partial),
kết thúc câu -> dịch chính xác, lưu lịch sử và đọc to bản dịch. Ngược lại
với tiếng Việt. Có chế độ nghe liên tục và ô gõ chữ dịch trực tiếp.
"""
import threading
import time

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, StringProperty
from kivy.storage.jsonstore import JsonStore
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput

from android_speech import SpeechInput, SpeechOutput, IS_ANDROID
from translator import Translator, TranslateError

LANG = {
    "en": {"name": "English", "tag": "en-US", "other": "vi"},
    "vi": {"name": "Tiếng Việt", "tag": "vi-VN", "other": "en"},
}
PARTIAL_INTERVAL = 0.45  # giây giữa hai lần dịch tạm khi đang nói
QUIET_ERRORS = (6, 7)     # không nghe thấy / không nhận ra -> nghe lại im lặng

KV = """
#:import dp kivy.metrics.dp
<HistoryItem>:
    size_hint_y: None
    text_size: self.width - dp(24), None
    height: self.texture_size[1] + dp(18)
    padding: dp(12), dp(9)
    halign: 'left'
    valign: 'middle'
    markup: True
    font_size: '15sp'
    on_release: app.tts.speak(self.say, self.say_lang)
    canvas.before:
        Color:
            rgba: self.bg
        RoundedRectangle:
            pos: self.x + dp(4), self.y + dp(3)
            size: self.width - dp(8), self.height - dp(6)
            radius: [dp(10)]

<BigButton@Button>:
    background_normal: ''
    background_down: ''
    font_size: '19sp'
    bold: True
    color: 1, 1, 1, 1
    base: 0.2, 0.2, 0.2, 1
    background_color: self.base if self.state == 'normal' else [c * 0.7 for c in self.base[:3]] + [1]

<SmallButton@Button>:
    background_normal: ''
    background_color: 0.22, 0.25, 0.30, 1
    font_size: '14sp'
    size_hint_x: None
    width: dp(84)

<Root>:
    orientation: 'vertical'
    padding: dp(10), dp(8)
    spacing: dp(8)
    canvas.before:
        Color:
            rgba: 0.08, 0.09, 0.11, 1
        Rectangle:
            pos: self.pos
            size: self.size

    BoxLayout:
        size_hint_y: None
        height: dp(40)
        Label:
            text: '[b]Phiên dịch Anh - Việt[/b]'
            markup: True
            font_size: '19sp'
            halign: 'left'
            text_size: self.size
            valign: 'middle'
        SmallButton:
            text: 'Xoá'
            on_release: app.clear_history()
        SmallButton:
            text: 'Cài đặt'
            on_release: app.open_settings_popup()

    Label:
        id: status
        size_hint_y: None
        height: dp(22)
        font_size: '13sp'
        color: 0.65, 0.7, 0.78, 1
        text: app.status
        text_size: self.size
        halign: 'left'

    # ---- Khu vực trực tiếp ----
    BoxLayout:
        orientation: 'vertical'
        size_hint_y: None
        height: max(dp(130), live_src.height + live_dst.height + dp(16))
        padding: dp(10), dp(6)
        canvas.before:
            Color:
                rgba: (0.13, 0.28, 0.20, 1) if app.listening else (0.13, 0.15, 0.19, 1)
            RoundedRectangle:
                pos: self.pos
                size: self.size
                radius: [dp(12)]
        Label:
            id: live_src
            text: app.live_src or ('Nhấn nút bên dưới và bắt đầu nói...' if not app.listening else 'Đang nghe...')
            color: 0.8, 0.84, 0.9, 1
            font_size: '16sp'
            size_hint_y: None
            text_size: self.width, None
            height: self.texture_size[1] + dp(6)
            halign: 'left'
        Label:
            id: live_dst
            text: app.live_dst
            bold: True
            color: 1, 0.93, 0.55, 1
            font_size: '22sp'
            size_hint_y: None
            text_size: self.width, None
            height: self.texture_size[1] + dp(6)
            halign: 'left'

    # ---- Lịch sử hội thoại ----
    ScrollView:
        id: scroll
        do_scroll_x: False
        GridLayout:
            id: history
            cols: 1
            size_hint_y: None
            height: self.minimum_height
            spacing: dp(2)

    # ---- Gõ chữ ----
    BoxLayout:
        size_hint_y: None
        height: dp(48)
        spacing: dp(6)
        SmallButton:
            text: 'EN > VI' if app.text_src == 'en' else 'VI > EN'
            on_release: app.swap_text_direction()
        TextInput:
            id: text_in
            hint_text: 'Gõ để dịch...'
            multiline: False
            font_size: '16sp'
            background_color: 0.16, 0.18, 0.22, 1
            foreground_color: 1, 1, 1, 1
            cursor_color: 1, 1, 1, 1
            hint_text_color: 0.5, 0.55, 0.6, 1
            padding: dp(10), dp(12)
            on_text: app.on_text_changed(self.text)
            on_text_validate: app.commit_text(self.text)
        SmallButton:
            text: 'Dịch'
            on_release: app.commit_text(text_in.text)

    # ---- Tuỳ chọn ----
    BoxLayout:
        size_hint_y: None
        height: dp(36)
        spacing: dp(6)
        ToggleButton:
            text: 'Nghe liên tục: ' + ('BẬT' if app.continuous else 'TẮT')
            state: 'down' if app.continuous else 'normal'
            on_release: app.set_continuous(self.state == 'down')
            font_size: '14sp'
        ToggleButton:
            text: 'Đọc bản dịch: ' + ('BẬT' if app.speak_enabled else 'TẮT')
            state: 'down' if app.speak_enabled else 'normal'
            on_release: app.set_speak(self.state == 'down')
            font_size: '14sp'

    # ---- Hai nút nói ----
    BoxLayout:
        size_hint_y: None
        height: dp(86)
        spacing: dp(10)
        BigButton:
            text: ('DỪNG' if app.listening_lang == 'en' else 'English') + '\\n[size=13sp]nói tiếng Anh[/size]'
            markup: True
            halign: 'center'
            base: (0.75, 0.2, 0.2, 1) if app.listening_lang == 'en' else (0.16, 0.42, 0.78, 1)
            on_release: app.toggle_listen('en')
        BigButton:
            text: ('DỪNG' if app.listening_lang == 'vi' else 'Tiếng Việt') + '\\n[size=13sp]nói tiếng Việt[/size]'
            markup: True
            halign: 'center'
            base: (0.75, 0.2, 0.2, 1) if app.listening_lang == 'vi' else (0.80, 0.45, 0.10, 1)
            on_release: app.toggle_listen('vi')
"""


class Root(BoxLayout):
    pass


class HistoryItem(ButtonBehavior, Label):
    """Một dòng lịch sử; chạm vào để đọc lại bản dịch."""
    bg = ListProperty([0.16, 0.18, 0.22, 1])
    say = StringProperty("")
    say_lang = StringProperty("")


class TranslatorApp(App):
    status = StringProperty("Sẵn sàng")
    live_src = StringProperty("")
    live_dst = StringProperty("")
    listening = BooleanProperty(False)
    listening_lang = StringProperty("")   # '' | 'en' | 'vi'  (phiên đang bật)
    continuous = BooleanProperty(True)
    speak_enabled = BooleanProperty(True)
    text_src = StringProperty("en")

    def build(self):
        self.title = "Phiên dịch Anh - Việt"
        Window.clearcolor = (0.08, 0.09, 0.11, 1)
        Window.softinput_mode = "below_target"
        self.store = JsonStore(f"{self.user_data_dir}/settings.json")
        cfg = self.store.get("cfg") if self.store.exists("cfg") else {}
        self.continuous = cfg.get("continuous", True)
        self.speak_enabled = cfg.get("speak", True)
        self.translator = Translator(cfg.get("api_key", ""))

        self._req_id = 0            # để bỏ kết quả dịch cũ
        self._partial_busy = False
        self._partial_pending = None
        self._last_partial = 0.0
        self._text_ev = None

        self.stt = SpeechInput(
            on_partial=self.on_partial,
            on_final=self.on_final,
            on_error=self.on_stt_error,
            on_state=self.on_stt_state,
        )
        self.tts = SpeechOutput()
        Builder.load_string(KV)
        return Root()

    def on_start(self):
        if IS_ANDROID:
            from android.permissions import request_permissions, Permission
            request_permissions([Permission.RECORD_AUDIO, Permission.INTERNET])
        mode = "Google Cloud API" if self.translator.api_key else "Google miễn phí"
        self.status = f"Sẵn sàng - dịch bằng {mode}"

    def on_pause(self):
        self.stop_listening()
        return True

    def on_stop(self):
        self.stt.destroy()
        self.tts.shutdown()

    # ------------------------------------------------------------ cài đặt
    def _save(self):
        self.store.put("cfg", continuous=self.continuous, speak=self.speak_enabled,
                       api_key=self.translator.api_key)

    def set_continuous(self, v):
        self.continuous = v
        self._save()

    def set_speak(self, v):
        self.speak_enabled = v
        if not v:
            self.tts.stop()
        self._save()

    def open_settings_popup(self):
        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10))
        box.add_widget(Label(
            text="Google Cloud Translation API key\n(để trống = dùng bản miễn phí)",
            size_hint_y=None, height=dp(48), halign="center"))
        ti = TextInput(text=self.translator.api_key, multiline=False,
                       password=True, size_hint_y=None, height=dp(44))
        box.add_widget(ti)
        row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        pop = Popup(title="Cài đặt", content=box, size_hint=(0.92, None),
                    height=dp(230))

        def save(*_):
            self.translator = Translator(ti.text)
            self._save()
            mode = "Google Cloud API" if self.translator.api_key else "Google miễn phí"
            self.status = f"Đã lưu - dịch bằng {mode}"
            pop.dismiss()

        row.add_widget(Button(text="Huỷ", on_release=lambda *_: pop.dismiss()))
        row.add_widget(Button(text="Lưu", on_release=save))
        box.add_widget(row)
        pop.open()

    # ------------------------------------------------------------ nghe nói
    def toggle_listen(self, lang):
        if self.listening_lang == lang:
            self.stop_listening()
            return
        self.tts.stop()
        self.listening_lang = lang
        self.live_src = ""
        self.live_dst = ""
        self._start(lang)

    def stop_listening(self):
        self.listening_lang = ""
        self.stt.cancel()
        self.listening = False
        self.status = "Đã dừng"

    def _start(self, lang):
        self.status = f"Đang nghe {LANG[lang]['name']}..."
        self.stt.start(LANG[lang]["tag"])

    def _restart_later(self, delay=0.25):
        """Nghe lại (chế độ liên tục) sau khi TTS đọc xong, tránh tự nghe tiếng máy."""
        def check(dt):
            lang = self.listening_lang
            if not lang or self.listening:
                return
            if self.tts.is_speaking():
                Clock.schedule_once(check, 0.25)
            else:
                self._start(lang)
        Clock.schedule_once(check, delay)

    def on_stt_state(self, listening):
        self.listening = listening

    def on_partial(self, text):
        if not self.listening_lang:
            return
        self.live_src = text
        self._partial_pending = text
        self._pump_partial()

    def _pump_partial(self):
        if not self.listening_lang:
            self._partial_pending = None
        if self._partial_busy or not self._partial_pending:
            return
        wait = PARTIAL_INTERVAL - (time.time() - self._last_partial)
        if wait > 0:
            Clock.schedule_once(lambda dt: self._pump_partial(), wait)
            return
        text, self._partial_pending = self._partial_pending, None
        src = self.listening_lang
        self._partial_busy = True
        self._last_partial = time.time()
        rid = self._req_id

        def work():
            try:
                out = self.translator.translate(text, src, LANG[src]["other"])
            except TranslateError:
                out = None
            self._partial_done(rid, out)
        threading.Thread(target=work, daemon=True).start()

    @mainthread
    def _partial_done(self, rid, out):
        self._partial_busy = False
        if rid == self._req_id and out:
            self.live_dst = out
        self._pump_partial()

    def on_final(self, text):
        lang = self.listening_lang
        if not lang:
            return
        if not text:
            if self.continuous:
                self._restart_later()
            else:
                self.stop_listening()
            return
        self._req_id += 1          # bỏ mọi kết quả dịch tạm còn đang chạy
        self._partial_pending = None
        self.live_src = text
        if not self.continuous:
            self.listening_lang = ""
        self._translate_final(text, lang, from_voice=True)

    def on_stt_error(self, code, msg):
        if code in QUIET_ERRORS and self.listening_lang and self.continuous:
            self._restart_later(0.1)
            return
        if code == 8 and self.listening_lang:   # bận -> thử lại
            self._restart_later(0.6)
            return
        self.status = msg
        self.listening_lang = ""
        self.listening = False

    # ------------------------------------------------------------ dịch
    def _translate_final(self, text, src, from_voice=False):
        dst = LANG[src]["other"]
        rid = self._req_id
        self.status = "Đang dịch..."

        def work():
            try:
                out, err = self.translator.translate(text, src, dst), None
            except TranslateError as e:
                out, err = None, str(e)
            self._final_done(rid, text, out, err, src, dst, from_voice)
        threading.Thread(target=work, daemon=True).start()

    @mainthread
    def _final_done(self, rid, text, out, err, src, dst, from_voice):
        spoke = False
        if err:
            self.status = f"Lỗi dịch: {err}"
        else:
            self.live_dst = out
            self.add_history(text, out, src)
            self.status = "Đang nghe..." if self.listening_lang else "Xong"
            spoke = self.speak_enabled and self.tts.speak(out, dst)
            if self.speak_enabled and not spoke and IS_ANDROID:
                self.status = f"Chưa có giọng đọc {LANG[dst]['name']} (xem hướng dẫn)"
        if from_voice and self.listening_lang and self.continuous:
            # TTS khởi động bất đồng bộ -> chờ lâu hơn một chút nếu vừa đọc
            self._restart_later(0.9 if spoke else 0.2)

    def add_history(self, src_text, dst_text, src):
        color = (0.13, 0.22, 0.36, 1) if src == "en" else (0.34, 0.22, 0.10, 1)
        tag = "EN" if src == "en" else "VI"
        b = HistoryItem(
            text=f"[size=13sp][color=9fb0c8]{tag}: {self._esc(src_text)}[/color][/size]\n"
                 f"[b]{self._esc(dst_text)}[/b]",
            bg=color, say=dst_text, say_lang=LANG[src]["other"])
        hist = self.root.ids.history
        hist.add_widget(b)
        Clock.schedule_once(lambda dt: setattr(self.root.ids.scroll, "scroll_y", 0), 0.05)

    @staticmethod
    def _esc(s):
        return s.replace("&", "&amp;").replace("[", "&bl;").replace("]", "&br;")

    def clear_history(self):
        self.root.ids.history.clear_widgets()
        self.live_src = self.live_dst = ""

    # ------------------------------------------------------------ gõ chữ
    def swap_text_direction(self):
        self.text_src = "vi" if self.text_src == "en" else "en"
        self.on_text_changed(self.root.ids.text_in.text)

    def on_text_changed(self, text):
        if self._text_ev:
            self._text_ev.cancel()
        if not text.strip():
            return
        self._text_ev = Clock.schedule_once(lambda dt: self._live_text(text), 0.6)

    def _live_text(self, text):
        src = self.text_src
        self._req_id += 1
        rid = self._req_id

        def work():
            try:
                out = self.translator.translate(text, src, LANG[src]["other"])
            except TranslateError as e:
                out = f"(lỗi: {e})"
            self._text_done(rid, text, out)
        threading.Thread(target=work, daemon=True).start()

    @mainthread
    def _text_done(self, rid, text, out):
        if rid == self._req_id:
            self.live_src = text
            self.live_dst = out

    def commit_text(self, text):
        text = text.strip()
        if not text:
            return
        if self._text_ev:
            self._text_ev.cancel()
        self._req_id += 1
        self.live_src = text
        self.root.ids.text_in.text = ""
        self._translate_final(text, self.text_src)


if __name__ == "__main__":
    TranslatorApp().run()
