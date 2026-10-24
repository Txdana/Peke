# Bundled SearXNG in Peke (Windows x64)

Peke bundles the SearXNG Python source, its runtime dependencies, its default
settings/templates/static assets, and a per-user service controller. The normal
PowerShell installer remains the supported installation method. Once Peke is
installed, **Docker is not required** and the user does not need to install a
separate SearXNG service.

## Use the desktop workspace

1. Open **Search & Research** from the navigation rail.
2. Select **Start bundled SearXNG**. Peke creates a per-user configuration file
   with a random secret key, moderate safe-search defaults, JSON output enabled,
   and a loopback bind address.
3. Peke starts `python -m searx.webapp` in its existing pipx environment and
   waits for the actual JSON search API to return a valid `results` list.
4. Search normally, or select **Research with Peke** to fetch relevant sources
   and produce an evidence-based answer when a configured provider is available.
5. Select **Stop local** to stop only the SearXNG process launched by the current
   Peke session. Peke never kills a service it did not start.

The local service listens at `http://127.0.0.1:8888`; it is not bound to the LAN.
Its settings and log are stored below Peke's per-user configuration directory
(`platformdirs` location, in a `searxng` subdirectory). The log file is named
`searxng.log`. The service uses the installed Peke Python environment and shuts
itself down when the app exits normally.

## Search API and external connectivity

Search is real metasearch, not bundled sample results. SearXNG queries configured
external search engines, so internet connectivity is needed for live results.
The service can start offline, but external search engines will not return live
results until connectivity is available. Engines may rate-limit, block, or
change their APIs. A SearXNG API health check only proves that the local service
responds; it does not guarantee every upstream engine works.

You may still configure a separate JSON-enabled SearXNG instance through the
Base URL field. If an instance returns HTTP 403, enable `json` under
`search.formats` in that instance's `settings.yml`. See the [official search API
documentation](https://docs.searxng.org/dev/search_api.html).

## Windows installation method

Use the existing PowerShell installer from the project README. It continues to
verify the Peke release wheel and hash-locked runtime dependencies before
installing into a user-level `pipx` environment. SearXNG's source is packaged
inside the Peke wheel, and its Python runtime requirements are included in the
release dependency lock. No Docker daemon or SearXNG container image is used.

The installer still requires Python 3.10+ and `pipx` under the existing
installation design. This work bundles the SearXNG service, not a separate
Python distribution.

## Bundled source and licensing

The bundled SearXNG source is under `src/searx/` and retains upstream source
notices. The exact original uploaded source archive is also preserved at
`vendor/searxng-master-source-archive.zip` so the snapshot can be independently
recovered and compared. The upstream AGPL-3.0-or-later licence is included at
`licenses/SEARXNG-LICENSE` and in the built wheel as `searx/SEARXNG-LICENSE`.
Its upstream runtime requirements are recorded in
`licenses/SEARXNG-REQUIREMENTS.txt`. Review `THIRD_PARTY_NOTICES.md` and the
SearXNG licence before redistributing modified builds. The supplied upstream
archive did not include Git metadata, so the bundled source version is marked
as an archive snapshot rather than falsely claiming a commit hash.

## Troubleshooting

- If startup fails, inspect `searxng.log` in Peke's per-user configuration
  directory; the UI reports the tail of the log when startup exits or times out.
- If the port is occupied by another service, close that service or change the
  port consistently in the generated settings and `BASE_URL` before rebuilding.
- If the server starts but searches return no results, check connectivity and
  the enabled SearXNG engines. Some engines may require configuration or may be
  blocked by their upstream providers.
- If imports fail, reinstall Peke using the verified PowerShell installer so
  its bundled source and hash-locked dependencies are installed together.

## Official references

- [SearXNG source](https://github.com/searxng/searxng)
- [SearXNG search API](https://docs.searxng.org/dev/search_api.html)
- [SearXNG settings](https://docs.searxng.org/admin/settings/settings.html)
