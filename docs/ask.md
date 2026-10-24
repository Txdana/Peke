# `peke ask` - situation-aware research

```bash
peke ask "latest pricing for Scrapling alternatives" --depth 1
peke ask "what API does https://example.com/shop call for products?" --deep
peke ask "summarise https://example.com/a and www.example.org/b" --no-search
```

Before doing anything Peke checks what it can actually do (SearXNG reachable and returning JSON, REA CLI and the
browser debug port, a ready local model, Scrapling installed) and what the prompt needs (links, fresh information,
endpoint hunting). The plan adapts:

| Situation | Behaviour |
| --- | --- |
| Search works | Search first (recent results only if the prompt is time-sensitive); your own links are scraped first |
| Search down or JSON disabled | Falls back to the links in your prompt and says why (e.g. enable `json` in SearXNG `search.formats`) |
| No search and no links | Says so and asks for a URL; it never invents sources |
| Prompt mentions API/endpoints | REA + subagents run on the best pages (static analysis if REA/browser is not ready) |
| No local model | Returns ranked excerpts instead of an answer |
| Cloud provider configured | Page text is only sent with `--allow-cloud` |

Every URL, including search results, passes the SSRF check. Page text is treated as untrusted when answering.
Set `SEARXNG_URL` or pass `--searxng`; with neither, localhost ports 8080 and 8888 are tried. `--depth N` follows
the most relevant same-site links; `--max-sources 0` means unlimited.
