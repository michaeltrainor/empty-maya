#!/usr/bin/env bash
# Create .venv.maya from Maya's python and install debugpy into it.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: venv-maya.sh [VERSION] [--dry-run] [--force] [--help]

Create .venv.maya with Maya's python and install debugpy into it.
The project .venv is left unchanged. debugpy is not a dependency of mtmaya.

Arguments:
  VERSION     Maya year to target (default: 2027)

Options:
  --dry-run   Print the uv commands without writing .venv.maya
  --force     Replace an existing .venv.maya
  --help      Show this help

Environment:
  MAYA_LOCATION   If set, use $MAYA_LOCATION/bin instead of the default
                  /Applications/Autodesk/maya${VERSION}/Maya.app/Contents/bin
  UV_PYTHON       If set, it must be Maya's python next to mayapy.
                  Otherwise the script sets it for `uv venv` only.

The python symlink comes from scripts/macos/link-mayapy.sh.
This script does not put Maya's bin on PATH, does not install into Maya's
site-packages, and does not install PyPI PySide6.
EOF
}

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "error: this script supports macOS only" >&2
  exit 1
fi

dry_run=0
force=0
maya_version="2027"
saw_version=0

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
    --force)
      force=1
      shift
      ;;
    -*)
      echo "error: unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      if [[ "${saw_version}" -eq 1 ]]; then
        echo "error: unexpected argument: $1" >&2
        exit 2
      fi
      maya_version="$1"
      saw_version=1
      shift
      ;;
  esac
done

if [[ ! "${maya_version}" =~ ^[0-9]{4}$ ]]; then
  echo "error: VERSION must be a four-digit Maya year (got: ${maya_version})" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
venv_dir="${repo_root}/.venv.maya"
venv_python="${venv_dir}/bin/python"
requirements="${repo_root}/scripts/maya-debug.txt"
verifier="${repo_root}/scripts/verify_maya_venv.py"

if [[ -n "${MAYA_LOCATION:-}" ]]; then
  maya_bin="${MAYA_LOCATION%/}/bin"
else
  maya_bin="/Applications/Autodesk/maya${maya_version}/Maya.app/Contents/bin"
fi

mayapy="${maya_bin}/mayapy"
python_link="${maya_bin}/python"

abs_path() {
  local dir base
  dir="$(cd "$(dirname "$1")" && pwd)"
  base="$(basename "$1")"
  printf '%s/%s' "${dir}" "${base}"
}

if [[ ! -e "${mayapy}" ]]; then
  echo "error: mayapy not found at ${mayapy}" >&2
  echo "error: install Maya ${maya_version} or set MAYA_LOCATION" >&2
  exit 1
fi

if [[ ! -e "${python_link}" ]]; then
  echo "error: python not found at ${python_link}" >&2
  echo "error: run scripts/macos/link-mayapy.sh to create it" >&2
  exit 1
fi

if [[ ! -L "${python_link}" ]]; then
  echo "error: ${python_link} exists and is not a symlink to mayapy" >&2
  exit 1
fi

link_target="$(readlink "${python_link}")"
if [[ "${link_target}" != "mayapy" && "${link_target}" != "${mayapy}" ]]; then
  echo "error: ${python_link} exists and is not a symlink to mayapy" >&2
  exit 1
fi

if [[ -n "${UV_PYTHON:-}" ]]; then
  if [[ ! -e "${UV_PYTHON}" ]]; then
    echo "error: UV_PYTHON does not exist: ${UV_PYTHON}" >&2
    exit 1
  fi
  if [[ "$(abs_path "${UV_PYTHON}")" != "$(abs_path "${python_link}")" ]]; then
    echo "error: UV_PYTHON must be Maya's python next to mayapy (${python_link})" >&2
    exit 1
  fi
fi

if [[ ! -f "${requirements}" ]]; then
  echo "error: requirements not found at ${requirements}" >&2
  exit 1
fi

saw_debugpy=0
while IFS= read -r line || [[ -n "${line}" ]]; do
  case "${line}" in
    "" | \#*)
      continue
      ;;
    debugpy==*)
      saw_debugpy=1
      ;;
    *)
      echo "error: scripts/maya-debug.txt may only install debugpy (got: ${line})" >&2
      exit 1
      ;;
  esac
done < "${requirements}"

if [[ "${saw_debugpy}" -eq 0 ]]; then
  echo "error: scripts/maya-debug.txt does not list debugpy" >&2
  exit 1
fi

if [[ ! -f "${verifier}" ]]; then
  echo "error: verifier not found at ${verifier}" >&2
  exit 1
fi

if [[ -L "${venv_dir}" ]]; then
  echo "error: .venv.maya is a link; refusing to replace it" >&2
  exit 1
fi

if [[ -e "${venv_dir}" && "${force}" -eq 0 ]]; then
  echo "error: .venv.maya already exists at ${venv_dir}" >&2
  echo "error: re-run with --force to replace it" >&2
  exit 1
fi

if [[ "${dry_run}" -eq 1 ]]; then
  if [[ -e "${venv_dir}" ]]; then
    echo "dry-run: replace ${venv_dir}"
  fi
  echo "directory=${repo_root}"
  echo "UV_PYTHON=${python_link}"
  echo "uv venv .venv.maya --no-managed-python --no-python-downloads --no-project"
  echo "uv pip install --python \"${venv_python}\" --no-deps --requirement \"${requirements}\" --no-managed-python --no-python-downloads"
  exit 0
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "error: uv is not on PATH" >&2
  exit 1
fi

remove_venv() {
  case "${venv_dir}" in
    "${repo_root}/.venv.maya") ;;
    *)
      echo "error: refusing to remove ${venv_dir}" >&2
      exit 1
      ;;
  esac
  case "${venv_dir}" in
    "${maya_bin}" | "${maya_bin}"/*)
      echo "error: refusing to remove a path inside Maya" >&2
      exit 1
      ;;
  esac
  if [[ -L "${venv_dir}" ]]; then
    echo "error: .venv.maya is a link; refusing to replace it" >&2
    exit 1
  fi
  rm -rf -- "${venv_dir}"
}

if [[ -e "${venv_dir}" ]]; then
  remove_venv
fi

(
  cd "${repo_root}"
  env -u VIRTUAL_ENV -u UV_MANAGED_PYTHON UV_PYTHON="${python_link}" \
    uv venv .venv.maya --no-managed-python --no-python-downloads --no-project
)

if [[ ! -x "${venv_python}" && ! -f "${venv_python}" ]]; then
  echo "error: uv venv did not create ${venv_python}" >&2
  exit 1
fi

home="$(awk -F ' = ' '$1 == "home" { print $2 }' "${venv_dir}/pyvenv.cfg")"
system_site="$(awk -F ' = ' '$1 == "include-system-site-packages" { print $2 }' "${venv_dir}/pyvenv.cfg")"
if [[ -z "${home}" || "$(abs_path "${home}")" != "$(abs_path "${maya_bin}")" ]]; then
  echo "error: .venv.maya was not created from Maya's python" >&2
  exit 1
fi
if [[ "${system_site}" != "false" ]]; then
  echo "error: .venv.maya must not include system site-packages" >&2
  exit 1
fi

case "${venv_python}" in
  "${venv_dir}/"*) ;;
  *)
    echo "error: refusing to install outside .venv.maya (${venv_python})" >&2
    exit 1
    ;;
esac
case "${venv_python}" in
  "${maya_bin}" | "${maya_bin}"/*)
    echo "error: refusing to install into Maya (${venv_python})" >&2
    exit 1
    ;;
esac

env -u UV_PYTHON -u UV_SYSTEM_PYTHON -u UV_MANAGED_PYTHON -u VIRTUAL_ENV \
  uv pip install \
  --python "${venv_python}" \
  --no-deps \
  --requirement "${requirements}" \
  --no-managed-python \
  --no-python-downloads

MTMAYA_VENV_DIR="${venv_dir}" MTMAYA_MAYA_BIN="${maya_bin}" \
  "${venv_python}" "${verifier}"

echo "created ${venv_dir}"
