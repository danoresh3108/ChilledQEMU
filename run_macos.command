#!/bin/zsh

set -u

SCRIPT_DIR="${0:A:h}"
LOG_FILE="$SCRIPT_DIR/launcher.log"
cd -- "$SCRIPT_DIR" || exit 1

exec > >(/usr/bin/tee -a "$LOG_FILE") 2>&1
print "\n=== ChilledQEMU launcher: $(date) ==="
print "Папка проекта: $SCRIPT_DIR"

pause_with_error() {
  print "\nОШИБКА: $1"
  print "Диагностика сохранена в: $LOG_FILE"
  read "?Нажмите Enter, чтобы закрыть окно…"
  exit 1
}

python_is_compatible() {
  "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1
}

find_compatible_python() {
  SELECTED_PYTHON=""
  local candidate resolved version
  local -a candidates=()
  if [[ -n "${CHILLEDQEUM_PYTHON:-}" ]]; then
    candidates+=("$CHILLEDQEUM_PYTHON")
  fi
  candidates+=(
    /opt/homebrew/opt/python@3.12/bin/python3.12
    /usr/local/opt/python@3.12/bin/python3.12
    /opt/homebrew/bin/python3.12
    /usr/local/bin/python3.12
    /Library/Frameworks/Python.framework/Versions/3.12/bin/python3
    python3.12 python3.11 python3.10
    /opt/homebrew/bin/python3
    /usr/local/bin/python3
    /Library/Frameworks/Python.framework/Versions/Current/bin/python3
    python3
  )
  for candidate in "${candidates[@]}"; do
    if [[ "$candidate" == /* ]]; then
      [[ -x "$candidate" ]] || continue
      resolved="$candidate"
    else
      resolved="$(command -v "$candidate" 2>/dev/null)"
      [[ -n "$resolved" ]] || continue
    fi
    version="$("$resolved" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))' 2>/dev/null)"
    [[ -n "$version" ]] || continue
    print "Проверяю Python $version: $resolved"
    if python_is_compatible "$resolved"; then
      SELECTED_PYTHON="$resolved"
      return 0
    fi
  done
  return 1
}

find_homebrew() {
  HOMEBREW_BIN=""
  local candidate
  for candidate in /opt/homebrew/bin/brew /usr/local/bin/brew brew; do
    if [[ "$candidate" == /* && -x "$candidate" ]]; then
      HOMEBREW_BIN="$candidate"
      return 0
    elif [[ "$candidate" != /* ]] && command -v "$candidate" >/dev/null 2>&1; then
      HOMEBREW_BIN="$(command -v "$candidate")"
      return 0
    fi
  done
  return 1
}

if ! find_compatible_python; then
  print "\nНе найден Python 3.10 или новее. Старый Python из Conda не подходит."
  if find_homebrew; then
    read "?Установить совместимый Python 3.12 через Homebrew? [y/N] " INSTALL_PYTHON
    if [[ "$INSTALL_PYTHON" == [yYдД] ]]; then
      "$HOMEBREW_BIN" install python@3.12 || pause_with_error "Homebrew не смог установить Python 3.12."
      find_compatible_python || pause_with_error "Python 3.12 установлен, но запускатель не смог его найти."
    else
      pause_with_error "Установите Python 3.10+ с python.org или выполните: $HOMEBREW_BIN install python@3.12"
    fi
  else
    pause_with_error "Установите Python 3.10+ с https://www.python.org/downloads/macos/ и запустите файл снова."
  fi
fi

print "Выбран Python: $SELECTED_PYTHON"

PYTHON="$SCRIPT_DIR/.venv/bin/python"
if [[ -x "$PYTHON" ]] && ! python_is_compatible "$PYTHON"; then
  BACKUP_VENV="$SCRIPT_DIR/.venv-incompatible-$(date +%Y%m%d-%H%M%S)-$$"
  print "Старое несовместимое .venv переношу в: $BACKUP_VENV"
  mv "$SCRIPT_DIR/.venv" "$BACKUP_VENV" || pause_with_error "Не удалось убрать старое .venv."
fi
if [[ ! -x "$PYTHON" ]]; then
  print "Создаю локальное Python-окружение через $SELECTED_PYTHON…"
  "$SELECTED_PYTHON" -m venv "$SCRIPT_DIR/.venv" || pause_with_error "Не удалось создать .venv."
fi

if ! "$PYTHON" -c "import PySide6" >/dev/null 2>&1; then
  print "Обновляю pip внутри локального окружения…"
  "$PYTHON" -m ensurepip --upgrade >/dev/null 2>&1 || true
  "$PYTHON" -m pip install --upgrade "pip>=23.1" || \
    pause_with_error "Не удалось обновить pip. Проверьте интернет и launcher.log."
  "$PYTHON" -m pip --version
  print "Устанавливаю PySide6 при первом запуске…"
  "$PYTHON" -m pip install -r "$SCRIPT_DIR/requirements.txt" || \
    pause_with_error "Не удалось установить зависимости. Проверьте интернет и launcher.log."
fi

if [[ "${CHILLEDQEUM_LAUNCHER_TEST:-0}" == "1" ]]; then
  print "ChilledQEMU launcher self-test: OK"
  exit 0
fi

print "Запускаю ChilledQEMU…"
"$PYTHON" "$SCRIPT_DIR/main.py"
EXIT_CODE=$?
if (( EXIT_CODE != 0 )); then
  pause_with_error "Приложение завершилось с кодом $EXIT_CODE."
fi
