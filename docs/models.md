# Choosing GGUF Models and Quantization

Peke executes local LLM extraction in-process via `llama-cpp-python`. You must provide a GGUF quantized model file and configure its location via the `MODEL_PATH` environment variable.

## Recommended Model Families

For structured extraction from HTML and unstructured text payloads, small instruction-tuned models (SLMs) with 3B to 8B parameters perform best:

- **Llama 3.2 (3B Instruct)**: Lightweight, fast inference, low RAM usage.
- **Qwen 2.5 (3B / 7B Instruct)**: Exceptional JSON formatting and schema compliance.
- **Mistral / Phi-3 (7B / 3.8B Instruct)**: Robust reasoning on complex unstructured pages.

## Quantization & Resource Matrix

| Model Size | Quantization | RAM Required | VRAM (GPU Offload) | Recommended Use Case |
|------------|--------------|--------------|--------------------|----------------------|
| ~3B Params | Q4_K_M | ~3.5 GB | ~2.5 GB | Laptops, CPU extraction |
| ~3B Params | Q8_0 | ~4.5 GB | ~3.5 GB | Higher extraction fidelity |
| ~7B/8B Params | Q4_K_M | ~6.5 GB | ~5.5 GB | Complex HTML documents |
| ~7B/8B Params | Q8_0 | ~9.0 GB | ~8.0 GB | Dedicated GPU workstations |

## Environment Configuration

Set your model path in `.env` or system environment variables:

```bash
export MODEL_PATH="/home/user/models/qwen2.5-3b-instruct-q4_k_m.gguf"
```
