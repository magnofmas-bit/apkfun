[app]

title = Controle de Vendas
package.name = controlevendas
package.domain = com.controlevendas
version = 1.0.0
requirements = python3,kivy==2.3.1,requests,pillow,bcrypt
fullscreen = 1
icon.filename = %(source.dir)s/data/icon.png
presplash.filename = %(source.dir)s/data/presplash.png
presplash.locking = 1
android.presplash_color = #FFFFFF

source.dir = .
source.include_exts = py,kv,json,png,jpg,atlas,db
source.include_patterns = assets/*,data/*

requirements.python = 3
requirements.kivy = 2.3.1

orientation = portrait
osx_requirements = python3,kivy

[app:android]

permissions = INTERNET, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE, ACCESS_NETWORK_STATE
android.bootstrap = sdl2
android.logcat_filters =  *:S python:D

# 🔥 CORRIGIDO AQUI
android.api = 33
android.minapi = 21
android.targetsdk = 33
android.ndk = r25b
android.archs = arm64-v8a
android.gradle_dependencies = 

android.permissions = INTERNET, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE, ACCESS_NETWORK_STATE
android.features = 
android.usesCleartextTraffic = true
android.allow_backup = True
android.accept_sdk_license = True
android.build_format = apk
android.package_format = apk

ios.kivy_ios_url = https://github.com/kivy/kivy-ios
ios.kivy_ios_branch = master
ios.codesign.allowed = false

osx.python_version = 3
osx.kivy_version = 1.9.1

[buildozer]

log_level = 2
warn_on_root = 1
bin_dir = ./aplicativo
buildozer_spec = buildozer.spec

[buildozer:android]

# p4a settings
p4a.bootstrap = sdl2
p4a.branch = develop
p4a.requirements = python3,kivy,requests,pillow,bcrypt
p4a.textinput_class = EditText
p4a.java_src_dir = 
p4a.add_libs_armeabi_v7a = 
p4a.add_libs_arm64_v8a = 

android.entrypoint = org.kivy.android.PythonActivity
android.release_artifact = apk
android.gradle_version = 7.6.3
android.gradle_options = org.gradle.jvmargs=-Xmx4096m

# 🔥 CORRIGIDO AQUI
android.compilesdkversion = 33

# Storage
android.apk_dir = bin

# ❌ REMOVIDO (IMPORTANTE — NÃO COLOCAR DE VOLTA)
# env.JAVA_HOME
# env.ANDROID_HOME
