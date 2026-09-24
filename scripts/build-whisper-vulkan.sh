#!/usr/bin/env bash
#
# Build whisper.cpp with the Vulkan backend on the host toolchain.
#
# Produces native binaries under third_party/whisper.cpp/build/bin/:
#   - whisper-cli     (file transcription)
#   - whisper-stream  (streaming / wake-word loop, later increments)
#
# Requirements (host, one-time):
#   sudo dnf install cmake gcc-c++ glslc vulkan-loader-devel spirv-headers-devel glslang
#
# The vendored source is expected at third_party/whisper.cpp (see docs).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="${REPO_ROOT}/third_party/whisper.cpp"
BUILD_DIR="${SRC_DIR}/build"

if [[ ! -f "${SRC_DIR}/CMakeLists.txt" ]]; then
  echo "error: whisper.cpp source not found at ${SRC_DIR}" >&2
  echo "clone it first: git clone --depth 1 --branch v1.9.4 https://github.com/ggml-org/whisper.cpp.git third_party/whisper.cpp" >&2
  exit 1
fi

echo "==> Configuring (Vulkan backend, Release)"
cmake -S "${SRC_DIR}" -B "${BUILD_DIR}" \
  -DCMAKE_BUILD_TYPE=Release \
  -DGGML_VULKAN=ON \
  -DWHISPER_BUILD_EXAMPLES=ON \
  -DWHISPER_BUILD_TESTS=OFF

echo "==> Building"
cmake --build "${BUILD_DIR}" --config Release -j"$(nproc)"

echo "==> Done. Binaries:"
ls -1 "${BUILD_DIR}/bin" 2>/dev/null || true
