"""Dịch Anh <-> Việt qua Google Translate.

- Có API key  -> dùng Google Cloud Translation API v2 (chính thức, ổn định).
- Không có key -> dùng endpoint miễn phí translate.googleapis.com (client=gtx).

Trên Android, kho chứng chỉ của hệ thống không dùng được cho Python nên
chương trình đọc file cacert.pem đi kèm app. Nếu vẫn lỗi chứng chỉ thì tự
động thử lại ở chế độ không xác thực (chỉ là văn bản dịch, không nhạy cảm).
"""
import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request

OFFICIAL_URL = "https://translation.googleapis.com/language/translate/v2"
FREE_URL = "https://translate.googleapis.com/translate_a/single"
TIMEOUT = 10


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
            # Không có chứng chỉ gốc nào -> xác thực chắc chắn thất bại
            return None
        return ctx
    except Exception:
        return None


_CTX = _make_ctx()
_CTX_OFF = ssl._create_unverified_context()


class TranslateError(Exception):
    pass


class Translator:
    def __init__(self, api_key: str = ""):
        self.api_key = (api_key or "").strip()
        self.insecure = _CTX is None      # đã phải bỏ xác thực chứng chỉ?
        self._cache = {}

    def translate(self, text: str, src: str, dst: str) -> str:
        text = (text or "").strip()
        if not text:
            return ""
        key = (text, src, dst)
        if key in self._cache:
            return self._cache[key]
        out = self._official(text, src, dst) if self.api_key else self._free(text, src, dst)
        if len(self._cache) > 500:
            self._cache.clear()
        self._cache[key] = out
        return out

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
            return data["data"]["translations"][0]["translatedText"]
        except (KeyError, IndexError, TypeError) as e:
            raise TranslateError(f"Phản hồi API không hợp lệ: {e}")

    # --- Endpoint miễn phí --------------------------------------------------
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
            raise TranslateError(f"Phản hồi không hợp lệ: {e}")

    def _open(self, req):
        try:
            return self._fetch(req, _CTX_OFF if self.insecure else _CTX)
        except ssl.SSLError:
            pass
        except urllib.error.URLError as e:
            if not isinstance(e.reason, ssl.SSLError):
                raise TranslateError(f"Không kết nối được: {e.reason}")
        # Lỗi chứng chỉ -> thử lại không xác thực
        self.insecure = True
        try:
            return self._fetch(req, _CTX_OFF)
        except urllib.error.URLError as e:
            raise TranslateError(f"Không kết nối được: {e.reason}")

    @staticmethod
    def _fetch(req, ctx):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read().decode("utf-8"))["error"]["message"]
            except Exception:
                msg = e.reason
            raise TranslateError(f"HTTP {e.code}: {msg}")
        except (ValueError, TimeoutError, OSError) as e:
            if isinstance(e, (ssl.SSLError, urllib.error.URLError)):
                raise
            raise TranslateError(f"{type(e).__name__}: {e}")

    # --- Chẩn đoán (nút "Kiem tra ket noi" trong Cài đặt) ------------------
    def diagnose(self):
        lines = ["CA file: %s" % (_ca_file() or "KHÔNG CÓ"),
                 "Xác thực chứng chỉ: %s" % ("TẮT" if self.insecure else "BẬT"),
                 "Chế độ: %s" % ("API key" if self.api_key else "miễn phí")]
        try:
            out = self.translate("hello world", "en", "vi")
            lines.append("Kết quả: %s" % out)
            lines.append("=> DỊCH ĐƯỢC")
        except TranslateError as e:
            lines.append("Lỗi: %s" % e)
            lines.append("=> KHÔNG DỊCH ĐƯỢC")
        except Exception as e:
            lines.append("Lỗi lạ: %s: %s" % (type(e).__name__, e))
            lines.append("=> KHÔNG DỊCH ĐƯỢC")
        return "\n".join(lines)
