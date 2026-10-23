# Bundled font assets

Peke registers DM Sans, Fraunces, and IBM Plex Mono from this directory when
font files are present, and falls back to installed system fonts otherwise.
The build environment used to prepare this Phase 2 patch had no network access
and did not contain these upstream font files, so the licensed font binaries
are intentionally not fabricated or substituted. Add the upstream variable
font files and their OFL license texts here before publishing a wheel that
claims to bundle them:

- DM Sans: https://github.com/google/fonts/tree/main/ofl/dmsans
- Fraunces: https://github.com/google/fonts/tree/main/ofl/fraunces
- IBM Plex Mono: https://github.com/google/fonts/tree/main/ofl/ibmplexmono

Place the respective OFL.txt files in `LICENSES/`.
