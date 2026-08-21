#!/bin/zsh

set -u
setopt NO_BG_NICE

APP_EXECUTABLE="${1:?Передайте путь к ChilledQEUM.app/Contents/MacOS/ChilledQEUM}"
if [[ ! -x "$APP_EXECUTABLE" ]]; then
  print -u2 "Исполняемый файл приложения не найден: $APP_EXECUTABLE"
  exit 2
fi

env PATH="/usr/bin:/bin:/usr/sbin:/sbin" QT_QPA_PLATFORM=offscreen CHILLEDQEUM_UI_LANGUAGE=en "$APP_EXECUTABLE" &
APP_PID=$!
sleep 2
if ! kill -0 "$APP_PID" 2>/dev/null; then
  wait "$APP_PID"
  EXIT_CODE=$?
  print -u2 "Приложение завершилось слишком рано: код $EXIT_CODE"
  exit 1
fi

kill -TERM "$APP_PID"
wait "$APP_PID"
EXIT_CODE=$?
if (( EXIT_CODE != 143 )); then
  print -u2 "Неожиданный код после тестового завершения: $EXIT_CODE"
  exit 1
fi
print "OK  packaged .app starts with Finder-like PATH"
