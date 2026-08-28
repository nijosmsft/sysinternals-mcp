# Changelog

All notable changes to `sysinternals-mcp` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.1] - 2026-08-27

### Fixed
- Migrated to standalone `fastmcp` package (`fastmcp>=2.14.7,<3`);
  fixes startup crash under mcp SDK v2 where `mcp.server.fastmcp` was removed.
- Added callable-preserving shim covering all three tool-decorator forms
  (bare `@mcp.tool`, `@mcp.tool()`, `@mcp.tool(name=...)`) to match fleet pattern.
- Closes [mcp-servers#39](https://github.com/nijosmsft/mcp-servers/issues/39).

### Changed
- README: rewrote the Bootstrap section and the ProcMon recipes section
  in present tense — removed sprint-release framing.
- README: removed apologetic "for now" phrasing from the clone-install
  snippet.

### Removed
- README: dropped the `Federation` row from the tool table and the
  `SYSINTERNALS_MCP_EVIDENCE_PATH` env var row from the configuration
  table — these were references to an internal-only optional dependency
  that is a no-op for public users.
- README: dropped the internal `ASSUMPTIONS.md` A2 cross-reference from
  the ProcMon recipes section.

## [0.2.0] - 2024

### Added
- `bootstrap_sysinternals` tool — installs the Sysinternals Suite via
  zip / winget / live download, with a CONSENT REQUIRED first-call UX.
- `accept_sysinternals_eula` tool — emits an HKCU or HKLM `reg add`
  script to pre-accept the EULA for every known binary.
- Seven additional tool wrappers: `tcpvcon`, `autoruns`, `coreinfo`,
  `psinfo`, `listdlls`, `procdump`, `strings`, plus their matching
  `parse_<tool>_output` siblings.
- ProcMon recipes now splice descriptor rules into `/Filter` CLI
  arguments directly — no manual **File → Import Configuration** step
  required.
- LabLink-first remote dispatch helper — every `target="remote"` tool
  emits a markdown block plus a JSON sidecar that an LLM can hand
  straight to LabLink (or any equivalent remote-execution MCP).
