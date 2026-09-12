#!/usr/bin/env bash
# Create Autodesk's required python -> mayapy symlink so uv can use Maya's interpreter.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: link-mayapy.sh [VERSION] [--dry-run] [--help]

Create a python symlink next to mayapy in Maya.app/Contents/bin (macOS).
uv and venv require an executable named python; mayapy alone is not enough.

Arguments:
  VERSION     Maya year to target (default: 2027)

Options:
  --dry-run   Print the ln command without creating the symlink
  --help      Show this help

Environment:
  MAYA_LOCATION   If set, use $MAYA_LOCATION/bin instead of the default
                  /Applications/Autodesk/maya${VERSION}/Maya.app/Contents/bin
EOF
}

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "error: this script supports macOS only" >&2
  exit 1
fi

original_args=("$@")
dry_run=0
maya_version="2027"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help | -h)
      usage
      exit 0
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    --)
      shift
      break
      ;;
    -*)
      echo "error: unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      maya_version="$1"
      shift
      ;;
  esac
done

if [[ ! "${maya_version}" =~ ^[0-9]{4}$ ]]; then
  echo "error: VERSION must be a four-digit Maya year (got: ${maya_version})" >&2
  exit 2
fi

if [[ -n "${MAYA_LOCATION:-}" ]]; then
  maya_bin="${MAYA_LOCATION%/}/bin"
else
  maya_bin="/Applications/Autodesk/maya${maya_version}/Maya.app/Contents/bin"
fi

mayapy="${maya_bin}/mayapy"
python_link="${maya_bin}/python"

if [[ ! -e "${mayapy}" ]]; then
  echo "error: mayapy not found at ${mayapy}" >&2
  echo "error: install Maya ${maya_version} or set MAYA_LOCATION" >&2
  exit 1
fi

is_correct_symlink() {
  [[ -L "${python_link}" ]] || return 1
  local target
  target="$(readlink "${python_link}")"
  [[ "${target}" == "mayapy" || "${target}" == "${mayapy}" ]]
}

print_uv_hints() {
  cat <<EOF
UV_PYTHON=${python_link}
uv venv --python "${python_link}"
export UV_PYTHON="${python_link}"
EOF
}

if is_correct_symlink; then
  echo "python already links to mayapy: ${python_link}"
  if [[ "${dry_run}" -eq 0 ]]; then
    "${python_link}" -c "import sys; print(sys.version)"
  fi
  print_uv_hints
  exit 0
fi

if [[ -e "${python_link}" || -L "${python_link}" ]]; then
  echo "error: ${python_link} exists and is not a symlink to mayapy" >&2
  ls -l "${python_link}" >&2 || true
  exit 1
fi

if [[ "${dry_run}" -eq 1 ]]; then
  echo "dry-run: (cd ${maya_bin} && ln -s -f mayapy python)"
  print_uv_hints
  exit 0
fi

if [[ ! -w "${maya_bin}" && "${EUID}" -ne 0 ]]; then
  echo "Maya bin is not writable; re-running with sudo"
  exec sudo --preserve-env=MAYA_LOCATION -- "$0" "${original_args[@]}"
fi

(
  cd "${maya_bin}"
  ln -s -f mayapy python
)

if ! is_correct_symlink; then
  echo "error: failed to create ${python_link} -> mayapy" >&2
  exit 1
fi

echo "created ${python_link} -> mayapy"
"${python_link}" -c "import sys; print(sys.version)"
print_uv_hints
