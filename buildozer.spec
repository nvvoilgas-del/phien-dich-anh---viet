[app]
title = Phien dich Anh Viet
package.name = dichanhviet
package.domain = org.viet
source.dir = .
source.include_exts = py,png,jpg,kv,json,pem
source.exclude_dirs = bin,.buildozer,.github
version = 1.0.1

requirements = python3,kivy,pyjnius,android,openssl,certifi

orientation = portrait
fullscreen = 0

# ---- Android ----
android.permissions = INTERNET,RECORD_AUDIO
android.api = 33
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True
# Khai bao <queries> de Android 11+ thay dich vu nhan dang giong noi & TTS
android.extra_manifest_xml = ./extra_manifest.xml
android.allow_backup = True

# Ghim python-for-android ban on dinh (Python 3.11). Ban master moi nhat
# dung Python 3.14 va dang loi khi cai charset-normalizer.
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 0
