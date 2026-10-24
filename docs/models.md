# Local GGUF models

Peke uses the standalone `llama-server` executable from the official [llama.cpp project](https://github.com/ggml-org/llama.cpp) as its primary local inference runtime. The server exposes an OpenAI-compatible API and avoids compiling `llama-cpp-python` during ordinary Peke installation. Peke does not bundle multi-gigabyte model weights.

Set `MODEL_PATH` to the absolute path of a `.gguf` file. Set `LLAMA_SERVER_PATH` to the full path of `llama-server.exe` on Windows or `llama-server` on Linux/macOS, or put the executable on `PATH`. The server binds to `127.0.0.1` by default. Use `peke ai status` to inspect runtime discovery and `peke ai test` to start the configured server and verify its health endpoint.

## Runtime installation

Download or build a CPU-compatible `llama-server` from the official llama.cpp project. GPU-enabled builds are optional and must match the machine's supported backend and drivers. Peke does not assume a GPU is usable merely because a display adapter is detected. For a source build, follow the official [build documentation](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md). Normal Peke installation does not build llama.cpp or `llama-cpp-python`.

The legacy `llama-cpp-python` provider is not installed by Peke. Existing environments that deliberately retain it may opt into the compatibility path by setting `PEKE_ALLOW_LEGACY_LLAMA_CPP_PYTHON=1`; this is not recommended for ordinary installation because it can require native compilation.

## RAM/VRAM planning

Quantization reduces memory use at a cost to quality. As a rough starting point, quantized 2B–4B models are more appropriate for constrained machines; 7B/8B models often need several additional GB of memory, and larger models require substantially more. Exact requirements vary with architecture, quantization, context length, KV cache, runtime overhead, and GPU offload. Always leave extra memory for the operating system and other applications.

- **Low RAM / CPU-only:** prefer a small 1B–3B quantized GGUF and a 2048-token context.
- **Mid-range system:** consider a 3B–4B quantized GGUF before trying 7B/8B.
- **GPU system:** only enable offload after checking the runtime build, driver compatibility, and available VRAM.
- **Quality-sensitive extraction:** compare output against a fixed validation set; quantization and small models can miss details.

Model download and licence terms depend on the selected publisher. Verify the artifact, source, licence, and available checksums before use. The first download requires an internet connection unless the model file is already available locally; inference can run offline once runtime and model files are installed.
