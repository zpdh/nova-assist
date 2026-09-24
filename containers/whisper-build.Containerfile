# Disposable build environment for whisper.cpp (Vulkan backend).
# Toolchain lives in the image; the produced binary runs natively on the host.
FROM registry.fedoraproject.org/fedora:44

RUN dnf install -y \
      cmake \
      gcc-c++ \
      glslc \
      vulkan-loader-devel \
      spirv-headers-devel \
      glslang \
      make \
      git \
    && dnf clean all

WORKDIR /src

# Configure + build with the Vulkan backend. Output lands in /src/build/bin,
# which is bind-mounted from the host via the wrapper script.
CMD ["bash", "-lc", "\
  cmake -S /src -B /src/build \
    -DCMAKE_BUILD_TYPE=Release \
    -DGGML_VULKAN=ON \
    -DWHISPER_BUILD_EXAMPLES=ON \
    -DWHISPER_BUILD_TESTS=OFF && \
  cmake --build /src/build --config Release -j\"$(nproc)\" \
"]
