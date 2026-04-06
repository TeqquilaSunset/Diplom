# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-04-06

### Added

- **Definition command** - New CLI command for finding symbol definitions with import resolution
  - `ast-index definition SYMBOL [--file PATH] [--format text|json]`
  - Resolves symbols considering using/import directives
  - Supports namespace-aware symbol lookup for C#

- **SymbolResolver module** - Core module for import-aware symbol resolution
  - Scoring system for multiple symbol candidates
  - Namespace extraction from file paths
  - Integration with existing usings table

- **Database enhancements**
  - `Database.get_symbols_by_name_and_namespace()` method
  - Namespace-filtered symbol queries

- **SearchEngine enhancements**
  - `SearchEngine.search_definition()` method
  - Lazy-loaded SymbolResolver integration

- **Comprehensive testing**
  - 4 new test modules for symbol resolution
  - Integration tests for definition command
  - Edge case coverage (not found, multiple candidates)

- **Documentation**
  - Updated CLAUDE.md with definition command
  - New `docs/definition-command.md` with usage examples
  - Architecture documentation for import resolution system

### Changed

- Improved symbol search accuracy with import resolution
- Better handling of ambiguous symbol names

### Fixed

- Namespace extraction for different project structures
- Symbol resolution priority scoring

## [0.1.1] - 2026-04-06

### Added

- C# parser improvements
  - Using directives extraction and storage
  - Generic types reference extraction
  - Context filters for XML docs, attributes, string interpolation
  - LINQ extension method identification

- CLI `usings` command for C# files
- NamespaceMapping model
- Database schema updates (usings table)

### Changed

- Enhanced reference extraction for C# projects
- Improved filtering of false positives

## [0.1.0] - Initial Release

### Added

- Core AST indexing functionality
- Support for Python, JavaScript, TypeScript, C#
- CLI commands: index, search, class, usages, inheritance, stats
- SQLite database with FTS5 full-text search
- Regex-based reference extraction
- Tree-sitter parser integration
