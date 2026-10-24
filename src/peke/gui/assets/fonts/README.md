# Font support

Peke can register DM Sans, Fraunces, and IBM Plex Mono from this directory when
licensed font files are present. No third-party font binaries are currently
redistributed with the application. If a requested font is unavailable, the UI
uses the platform's installed fallback fonts.

If font binaries are added in a future release, include the corresponding
upstream licence text and attribution in `LICENSES/` and update
`THIRD_PARTY_NOTICES.md`. Official upstream sources:

- DM Sans: https://github.com/google/fonts/tree/main/ofl/dmsans
- Fraunces: https://github.com/google/fonts/tree/main/ofl/fraunces
- IBM Plex Mono: https://github.com/google/fonts/tree/main/ofl/ibmplexmono
