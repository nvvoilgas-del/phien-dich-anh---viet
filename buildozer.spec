[app]
title = Phien dich Anh Viet
package.name = dichanhviet
package.domain = org.viet
source.dir = .
source.include_exts = py,png,jpg,kv,json
source.exclude_dirs = bin,.buildozer,.github
version = 1.0.0

requirements = python3,kivy,pyjnius,android,certifi

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,RECORD_AUDIO
android.api = 33
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True
android.extra_manifest_xml = ./extra_manifest.xml
android.allow_backup = True

p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 0
