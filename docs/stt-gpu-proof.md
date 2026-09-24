# STT GPU Proof (whisper.cpp + Vulkan)

Increment I0/I1: prove that whisper.cpp runs on the AMD GPU via Vulkan and is
faster than CPU, before building any application code.

## Environment

| Item | Value |
|---|---|
| Host | Fedora 44, kernel 7.1.4 |
| GPU | AMD Radeon RX 6650 XT (RADV NAVI23), 8 GB VRAM |
| Vulkan | loader 1.4.341, radv driver |
| whisper.cpp | v1.9.4 (`927cfce34f31707e17f2bff35c349632fb9e2c3a`) |
| Model | `ggml-tiny.en` (77 MB) |
| Build flags | `-DGGML_VULKAN=ON -DCMAKE_BUILD_TYPE=Release` |

## Build requirements (host)

```
sudo dnf install cmake gcc-c++ glslc vulkan-loader-devel spirv-headers-devel glslang
```

Two of these are non-obvious and were discovered during the build:

- `spirv-headers-devel` — provides `SPIRV-HeadersConfig.cmake`, required by
  `ggml/src/ggml-vulkan/CMakeLists.txt`.
- `glslang` — provides `glslangValidator`, needed by the Vulkan shader toolchain.

## Build

```
./scripts/build-whisper-vulkan.sh
```

Produces `third_party/whisper.cpp/build/bin/whisper-cli` and
`libggml-vulkan.so`.

## GPU detection (gate)

```
ggml_vulkan: Found 1 Vulkan devices:
ggml_vulkan: 0 = AMD Radeon RX 6650 XT (RADV NAVI23) (radv) | ...
whisper_backend_init_gpu: found GPU device 0: Vulkan0
```

Gate passed: the model is loaded onto `Vulkan0`, not CPU.

## Command

```
./third_party/whisper.cpp/build/bin/whisper-cli \
  -m models/ggml-tiny.en.bin -f tmp/nova_test.wav
```

Input `tmp/nova_test.wav`: 16 kHz mono, 2.86 s (converted from mp3 via ffmpeg).

## Results

Transcript (identical on both backends): `Hello, test.`

| Backend | Load time | Encode time | Total time |
|---|---|---|---|
| Vulkan (GPU) | ~82 ms | ~28 ms | **~201 ms** |
| CPU (`-ng`) | ~58 ms | ~237 ms | ~411 ms |

- **Total: ~2.0x faster on GPU.**
- **Encode (the heavy compute stage): ~8.4x faster** (237 ms -> 28 ms).
- Load time is a fixed one-time cost; the app will keep the model resident, so
  steady-state per-command latency is dominated by encode+decode.

## Notes / implications

- The two backends are selected with no GPU (`-ng`) vs default. In the app the
  device is chosen by config, with CPU fallback if Vulkan init fails.
- Numbers are for the `tiny` model; larger models (`small`, `medium`) will show
  a bigger GPU advantage since encode scales with model size.
- Runtime links against the host `libvulkan.so.1` + RADV; the binary is a native
  Fedora ELF. A Podman build is available as an optional alternative
  (`scripts/build-whisper-podman.sh`) but is not required.
- The build sets an `$ORIGIN` RUNPATH so the binaries are relocatable: they
  resolve `libwhisper.so`/`libggml*.so` from their own directory. Without this,
  moving or renaming the repo makes the dynamic loader fail with
  `libwhisper.so.1: cannot open shared object file`.
- The app is named **Nova**; the wake phrase is **"Hey Nova"**. On the `tiny.en`
  model a recorded clip transcribes the phrase verbatim:
  `Hey Nova, this is a test to see if you pick up my audio correctly.`

## Reproduction

```
# 1. deps (see above), then:
git clone --depth 1 --branch v1.9.4 \
  https://github.com/ggml-org/whisper.cpp.git third_party/whisper.cpp
./scripts/build-whisper-vulkan.sh
# 2. model + audio
curl -L -o models/ggml-tiny.en.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.en.bin
ffmpeg -i <clip> -ar 16000 -ac 1 -c:a pcm_s16le tmp/nova_test.wav
# 3. transcribe
./third_party/whisper.cpp/build/bin/whisper-cli \
  -m models/ggml-tiny.en.bin -f tmp/nova_test.wav
```
