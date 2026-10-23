# Local GGUF models

Peke uses `llama-cpp-python` in-process and reads the model path from `MODEL_PATH`. It does not download models or start a model daemon. Choose a model whose license and intended use fit your project; verify its provenance and license independently. Peke does not host or bundle model weights.

## RAM/VRAM planning

Quantization reduces memory use at a cost to quality. As a rough starting point, quantized 7B/8B models often need several GB of memory, 12B/14B models need substantially more, and 30B+ models generally require high-memory systems or careful offload. Exact requirements vary with architecture, quantization, context length, and runtime overhead. Always leave extra memory for the KV cache and operating system.

- **Low RAM / CPU-only:** prefer a small 2B–4B quantized GGUF, short context, and `N_GPU_LAYERS=0`.
- **Mid-range system:** consider a 7B/8B quantized model and increase `N_CTX` only if needed.
- **GPU system:** set `N_GPU_LAYERS` gradually; monitor memory and reduce layers if allocation fails.
- **Quality-sensitive extraction:** compare output against a fixed validation set; quantization and small models can miss details.

## Configuration

Set `MODEL_PATH` to the absolute path of a `.gguf` file. `N_CTX` controls context capacity, `N_THREADS=0` lets the library choose CPU threads, `N_GPU_LAYERS=0` keeps execution on CPU, and `TEMPERATURE` is clamped to 0.0–0.1 for reproducible extraction. A compatible native build of llama-cpp-python may be needed for GPU acceleration. See the upstream llama-cpp-python installation instructions for platform-specific build details.
