# Peke 🐥

An open-source desktop workbench that orchestrates three powerful tools into one data-extraction pipeline:
1. **REA** (optional component): Reverse engineering of web applications to discover hidden endpoints, headers, and parameters.
2. **Scrapling**: Stealth web fetching and HTTP parsing engine.
3. **llama.cpp** (via `llama-cpp-python`): In-process local LLM that transforms raw, unformatted payload text into schema-valid JSON or Markdown.

---

## 🚀 Quickstart

Run Peke in 3 simple commands:

```bash
# 1. Install Peke
pip install -e .

# 2. Set your local GGUF model path
export MODEL_PATH="/path/to/your/model.gguf"

# 3. Execute extraction pipeline via CLI
peke run profiles/example.yaml -o out.json
```

To launch the desktop interface:
```bash
peke
```

---

## 🖼 Screenshots

*(Desktop Workbench interface screenshots coming soon)*

---

## 📜 Responsible Use

Peke is designed for authorized data extraction, API discovery, and local data processing. When using Peke, please ensure you adhere to responsible web scraping practices:

- **Respect `robots.txt`**: Always check and respect `robots.txt` rules and crawl directives for target domains.
- **Site Terms of Service**: Verify that your scraping activity complies with the target website's Terms of Service and API usage guidelines.
- **Rate Limits & Load**: Limit request frequency and enforce reasonable delays between requests to avoid overloading origin servers.
- **Permitted Data Only**: Collect only data you are permitted to access. Avoid gathering private, personal, sensitive, or protected intellectual property without permission.

---

## 📄 License

This project is released under the [MIT License](LICENSE).
