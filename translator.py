"""Dịch Anh <-> Việt, có nhiều nguồn dịch và tự chuyển nguồn khi bị chặn.

Thứ tự ưu tiên:
  1. Google Cloud Translation API  (khi có API key - ổn định nhất)
  2. Google Translate bản miễn phí  (không chính thức, hay bị HTTP 429)
  3. MyMemory                       (miễn phí, có hạn mức theo ngày)

Nguồn nào lỗi 429 (gọi quá nhiều) sẽ bị nghỉ một lúc, app tự dùng nguồn khác.
Trên Android, chương trình đọc file cacert.pem đi kèm app vì Python không
dùng được kho chứng chỉ của hệ thống.
"""
import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

OFFICIAL_URL = "https://translation.googleapis.com/language/translate/v2"
FREE_URL = "https://translate.googleapis.com/translate_a/single"
MYMEMORY_URL = "https://api.mymemory.translated.net/get"
TIMEOUT = 10
COOLDOWN = 180          # giây nghỉ của một nguồn sau khi bị chặn


def _ca_file():
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cacert.pem")
    if os.path.exists(here):
        return here
    try:
        import certifi
        p = certifi.where()
        if os.path.exists(p):
            return p
    except Exception:
        pass
    return None


def _make_ctx():
    ca = _ca_file()
    try:
        ctx = ssl.create_default_context(cafile=ca) if ca else ssl.create_default_context()
        if ctx.cert_store_stats().get("x509_ca", 0) == 0:
            return None
        return ctx
    except Exception:
        return None


_CTX = _make_ctx()
_CTX_OFF = ssl._create_unverified_context()


class TranslateError(Exception):
    pass


class RateLimited(TranslateError):
    pass


class Translator:
    def __init__(self, api_key: str = "", email: str = ""):
        self.api_key = (api_key or "").strip()
        self.email = (email or "").strip()
        self.insecure = _CTX is None
        self.last_source = ""
        self._cache = {}
        self._cooldown = {}          # ten nguon -> thoi diem het nghi

    # ------------------------------------------------------------------
    def sources(self):
        out = []
        if self.api_key:
            out.append(("Google API", self._official))
        out.append(("Google", self._free))
        out.append(("MyMemory", self._mymemory))
        return out

    def translate(self, text: str, src: str, dst: str) -> str:
        text = (text or "").strip()
        if not text:
            return ""
        key = (text, src, dst)
        if key in self._cache:
            return self._cache[key]

        now = time.time()
        errors = []
        available = [(n, f) for n, f in self.sources() if self._cooldown.get(n, 0) < now]
        if not available:                       # tất cả đang nghỉ -> thử lại nguồn đầu
            available = self.sources()[:1]
            self._cooldown.clear()

        for name, func in available:
            try:
                out = func(text, src, dst)
                self.last_source = name
                if len(self._cache) > 500:
                    self._cache.clear()
                self._cache[key] = out
                return out
            except RateLimited as e:
                self._cooldown[name] = time.time() + COOLDOWN
                errors.append(f"{name}: bị chặn tạm thời (429)")
            except TranslateError as e:
                errors.append(f"{name}: {e}")
            except Exception as e:
                errors.append(f"{name}: {type(e).__name__}: {e}")
        raise TranslateError(" | ".join(errors))

    # --- Google Cloud Translation API v2 ---------------------------------
    def _official(self, text, src, dst):
        body = urllib.parse.urlencode(
            {"q": text, "source": src, "target": dst, "format": "text",
             "key": self.api_key}
        ).encode("utf-8")
        req = urllib.request.Request(OFFICIAL_URL, data=body, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        data = self._open(req)
        try:
            if "error" in data:
                raise TranslateError(data["error"].get("message", "API error"))
            return self._unescape(data["data"]["translations"][0]["translatedText"])
        except (KeyError, IndexError, TypeError) as e:
            raise TranslateError(f"phản hồi không hợp lệ ({e})")

    # --- Google bản miễn phí ---------------------------------------------
    def _free(self, text, src, dst):
        qs = urllib.parse.urlencode(
            {"client": "gtx", "sl": src, "tl": dst, "dt": "t", "q": text}
        )
        req = urllib.request.Request(f"{FREE_URL}?{qs}")
        req.add_header("User-Agent", "Mozilla/5.0")
        data = self._open(req)
        try:
            return "".join(seg[0] for seg in data[0] if seg and seg[0])
        except (IndexError, TypeError) as e:
            raise TranslateError(f"phản hồi không hợp lệ ({e})")

    # --- MyMemory ---------------------------------------------------------
    def _mymemory(self, text, src, dst):
        params = {"q": text, "langpair": f"{src}|{dst}"}
        if self.email:
            params["de"] = self.email
        req = urllib.request.Request(f"{MYMEMORY_URL}?{urllib.parse.urlencode(params)}")
        req.add_header("User-Agent", "Mozilla/5.0")
        data = self._open(req)
        try:
            status = int(data.get("responseStatus", 200))
            out = (data.get("responseData") or {}).get("translatedText") or ""
            if status == 429 or "MYMEMORY WARNING" in out.upper():
                raise RateLimited("hết hạn mức trong ngày")
            if status >= 400:
                raise TranslateError(data.get("responseDetails") or f"lỗi {status}")
            return self._unescape(out)
        except (AttributeError, TypeError, ValueError) as e:
            raise TranslateError(f"phản hồi không hợp lệ ({e})")

    # --- HTTP -------------------------------------------------------------
    def _open(self, req):
        try:
            return self._fetch(req, _CTX_OFF if self.insecure else _CTX)
        except ssl.SSLError:
            pass
        except urllib.error.URLError as e:
            if not isinstance(e.reason, ssl.SSLError):
                raise TranslateError(f"không kết nối được ({e.reason})")
        self.insecure = True            # lỗi chứng chỉ -> thử lại không xác thực
        try:
            return self._fetch(req, _CTX_OFF)
        except urllib.error.URLError as e:
            raise TranslateError(f"không kết nối được ({e.reason})")

    @staticmethod
    def _fetch(req, ctx):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                raise RateLimited(str(e.code))
            try:
                msg = json.loads(e.read().decode("utf-8"))["error"]["message"]
            except Exception:
                msg = e.reason
            raise TranslateError(f"HTTP {e.code}: {msg}")
        except (ValueError, TimeoutError, OSError) as e:
            if isinstance(e, (ssl.SSLError, urllib.error.URLError)):
                raise
            raise TranslateError(f"{type(e).__name__}: {e}")

    @staticmethod
    def _unescape(s):
        import html
        return html.unescape(s or "")

    # --- Chẩn đoán --------------------------------------------------------
    def diagnose(self):
        lines = ["CA file: %s" % (_ca_file() or "KHONG CO"),
                 "Xac thuc chung chi: %s" % ("TAT" if self.insecure else "BAT")]
        for name, func in self.sources():
            try:
                out = func("hello world", "en", "vi")
                lines.append("%s: OK -> %s" % (name, out))
            except Exception as e:
                lines.append("%s: LOI - %s" % (name, e))
        return "\n".join(lines)
