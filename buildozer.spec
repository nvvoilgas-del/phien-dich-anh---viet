[app]
title = Phien dich Anh Viet
package.name = dichanhviet
package.domain = org.viet
source.dir = .
source.include_exts = py,png,jpg,kv,json
source.exclude_dirs = bin,.buildozer,.github
version = 1.0.0

requirements = python3,kivy==2.3.1,pyjnius,android,certifi

orientation = portrait
fullscreen = 0

# ---- Android ----
android.permissions = INTERNET,RECORD_AUDIO
android.api = 34
android.minapi = 24
android.archs = arm64-v8a
android.accept_sdk_license = True
# Khai báo <queries> để Android 11+ cho phép thấy dịch vụ nhận dạng giọng nói & TTS
android.extra_manifest_xml = ./extra_manifest.xml
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 0
