#!/usr/bin/env bash
#
# Optional: build whisper.cpp with the Vulkan backend inside a disposable
# Podman container, keeping the host toolchain clean.
#
# The container provides the build toolchain (cmake/g++/glslc/vulkan-devel).
# The resulting binary is a native host ELF and runs against the host's
# libvulkan + RADV driver at runtime. Output is extracted to
# third_party/whisper.cpp/build/bin/.
#
# Requirements: podman (rootless).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="${REPO_ROOT}/third_party/whisper.cpp"
CONTAINERFILE="${REPO_ROOT}/containers/whisper-build.Containerfile"
IMAGE="nova-whisper-build:latest"
CID=""

cleanup() {
  [[ -n "${CID}" ]] && podman rm -f "${CID}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

if [[ ! -f "${SRC_DIR}/CMakeLists.txt" ]]; then
  echo "error: whisper.cpp source not found at ${SRC_DIR}" >&2
  exit 1
fi

echo "==> Building toolchain image"
podman build -f "${CONTAINERFILE}" -t "${IMAGE}" "${REPO_ROOT}"

echo "==> Running build container"
CID="$(podman create -v "${SRC_DIR}:/src" "${IMAGE}")"
podman start -a "${CID}"

echo "==> Done. Binaries:"
ls -1 "${SRC_DIR}/build/bin" 2>/dev/null || true
