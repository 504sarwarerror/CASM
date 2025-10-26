#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Use main.py as the canonical entrypoint
CASM_PY="$SCRIPT_DIR/main.py"

DEST_DIR=""
FORCE=false

print_usage() {
  cat <<EOF
Usage: $0 [--dest DIR] [--force]
Installs a 'casm' wrapper that runs main.py with python.

Options:
  --dest DIR    Install into DIR (overrides automatic choice)
  --force       Overwrite existing files without prompting
  --help        Show this help
EOF
}

while [[ ${#} -gt 0 ]]; do
  case "$1" in
    --dest)
      DEST_DIR="$2"
      shift 2
      ;;
    --force)
      FORCE=true
      shift
      ;;
    -h|--help)
      print_usage
      exit 0
      ;;
    *)
      echo "Unknown arg: $1"
      print_usage
      exit 1
      ;;
  esac
done

if [ ! -f "$CASM_PY" ]; then
  echo "Error: main.py not found at $CASM_PY"
  echo "Please ensure you have renamed your entry script to 'main.py' or place main.py in the project root."
  exit 1
fi

# Choose default destination based on platform
UNAME_OUT="$(uname -s || echo Unknown)"
case "$UNAME_OUT" in
  Darwin|Linux)
    : ${DEST_DIR:="/usr/local/bin"}
    PLATFORM="unix"
    ;;
  MINGW*|MSYS*|CYGWIN*|Windows_NT)
    : ${DEST_DIR:="$HOME/bin"}
    PLATFORM="windows"
    ;;
  *)
    : ${DEST_DIR:="/usr/local/bin"}
    PLATFORM="unix"
    ;;
esac

echo "Installer detected platform: $PLATFORM"
echo "main.py: $CASM_PY"
echo "Installing to: $DEST_DIR"

mkdir -p "$DEST_DIR"

install_unix_wrapper() {
  local target="$DEST_DIR/casm"

  if [ -e "$target" ] && [ "$FORCE" != true ]; then
    echo "A file already exists at $target. Use --force to overwrite."
    return 1
  fi

  TMPFILE="$(mktemp /tmp/casm_wrapper.XXXXXX)"
  # Use an unescaped here-doc but escape $@ so it's preserved literally in the
  # generated wrapper while $CASM_PY is expanded at install time.
  cat > "$TMPFILE" <<EOF
#!/usr/bin/env bash
# Auto-generated wrapper to run main.py
exec python3 "$CASM_PY" "\$@"
EOF

  chmod +x "$TMPFILE"

  if [ -w "$DEST_DIR" ]; then
    mv -f "$TMPFILE" "$target"
  else
    echo "Moving wrapper to $target using sudo..."
    sudo mv -f "$TMPFILE" "$target"
  fi

  echo "Installed Unix wrapper: $target"
}

install_windows_wrappers() {
  local target_sh="$DEST_DIR/casm"
  local target_cmd="$DEST_DIR/casm.cmd"

  if [ -e "$target_sh" ] && [ "$FORCE" != true ]; then
    echo "A file already exists at $target_sh. Use --force to overwrite."
    return 1
  fi
  if [ -e "$target_cmd" ] && [ "$FORCE" != true ]; then
    echo "A file already exists at $target_cmd. Use --force to overwrite."
    return 1
  fi

  # Bash-style wrapper (for Git Bash / MSYS / Cygwin)
  # For the shell wrapper we also escape $@ to avoid expansion during install
  cat > "$target_sh" <<EOF
#!/usr/bin/env bash
exec python3 "$CASM_PY" "\$@"
EOF
  chmod +x "$target_sh"

  # Create Windows batch wrapper
  CASM_PY_WIN="$CASM_PY"
  if command -v cygpath >/dev/null 2>&1; then
    CASM_PY_WIN="$(cygpath -w "$CASM_PY")"
  fi

  cat > "$target_cmd" <<EOF
@echo off
REM Auto-generated wrapper to run main.py
python "%CASM_PY_WIN%" %*
EOF

  echo "Installed Windows wrappers: $target_sh and $target_cmd"
}

if [ "$PLATFORM" = "unix" ]; then
  install_unix_wrapper
  STATUS=$?
else
  install_windows_wrappers
  STATUS=$?
fi

if [ $STATUS -ne 0 ]; then
  echo "Installation aborted or encountered issues."
  exit $STATUS
fi

# Provide final instructions
case ":$PATH:" in
  *":$DEST_DIR:"*)
    echo "Done. You can now run: casm <command>"
    ;;
  *)
    echo "Done, but $DEST_DIR is not in your PATH. Add it to your PATH to run 'casm' from anywhere."
    echo "Example (macOS / Linux):"
    echo "  echo 'export PATH=\"$DEST_DIR:\$PATH\"' >> ~/.profile"
    echo "Then open a new terminal."
    ;;
esac

exit 0
