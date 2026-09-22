"""Dịch Anh <-> Việt qua Google Translate.

- Có API key  -> dùng Google Cloud Translation API v2 (chính thức, ổn định).
- Không có key -> dùng endpoint miễn phí translate.googleapis.com (client=gtx).
"""
import json
import ssl
import urllib.parse
import urllib.request

try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:  # pragma: no cover
    _SSL_CTX = ssl.create_default_context()

OFFICIAL_URL = "https://translation.googleapis.com/language/translate/v2"
FREE_URL = "https://translate.googleapis.com/translate_a/single"
TIMEOUT = 8


class TranslateError(Exception):
    pass


class Translator:
    def __init__(self, api_key: str = ""):
        self.api_key = (api_key or "").strip()
        self._cache = {}

    def translate(self, text: str, src: str, dst: str) -> str:
        text = (text or "").strip()
        if not text:
            return ""
        key = (text, src, dst)
        if key in self._cache:
            return self._cache[key]
        if self.api_key:
            out = self._official(text, src, dst)
        else:
            out = self._free(text, src, dst)
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

    @staticmethod
    def _open(req):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=_SSL_CTX) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read().decode("utf-8"))["error"]["message"]
            except Exception:
                msg = str(e)
            raise TranslateError(f"HTTP {e.code}: {msg}")
        except urllib.error.URLError as e:
            raise TranslateError(f"Không có kết nối mạng ({e.reason})")
        except (ValueError, TimeoutError) as e:
            raise TranslateError(str(e))
