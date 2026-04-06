# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

```bash
# Install dependencies (development mode)
pip install -e ".[dev]"

# Run all tests
pytest

# Run specific test file or test
pytest tests/test_integration.py
pytest tests/test_integration.py -k test_index

# Run tests with coverage report
pytest --cov=ast_index --cov-report=term-missing

# Linting
ruff check .

# Auto-fix linting issues
ruff check . --fix

# Type checking
mypy ast_index
```

## Architecture Overview

**AST Index** is a structural code search tool that indexes codebases using Abstract Syntax Tree (AST) analysis via tree-sitter parsers. The system stores symbols in SQLite with FTS5 full-text search for fast queries.

### Core Components

- **Parsers** (`ast_index/parsers/`): Tree-sitter based parsers for Python, C#, JavaScript, and TypeScript
  - Uses automatic registration via `__init_subclass__` pattern
  - Each parser inherits from `BaseParser` and implements `parse()` and `can_parse()`

- **Database** (`ast_index/database.py`): SQLite operations with FTS5 full-text search
  - Schema: files, symbols, symbols_fts, inheritance, refs, metadata tables
  - Database location: `~/.cache/ast-index/{project_hash}/index.db`
  - Uses djb2 hash for project path

- **Indexer** (`ast_index/indexer.py`): Main indexing logic with batch processing
  - Processes files in batches of 500 (BATCH_SIZE)
  - Supports incremental updates (detects new/modified/deleted files)
  - Concurrent parsing with thread pool

- **Search Engine** (`ast_index/search.py`): Three-level search strategy
  1. Exact match (SELECT WHERE name = 'Symbol')
  2. Prefix search via FTS5 (MATCH 'Sym*')
  3. Fuzzy search via LIKE (LIKE '%Symbol%')

- **CLI** (`ast_index/cli.py`): Click-based command interface
  - Commands: index, update, rebuild, search, class, usages, usings, inheritance, stats, definition
  - All commands support `--format json` for AI integration
  - `usages` command supports `--show-context` and `--file` options
  - **`usings` command** (NEW): Show using directives for C# files with `--format text|json`
  - **`definition` command** (NEW): Find symbol definition with import resolution
    ```bash
    ast-index definition SYMBOL [--file PATH] [--format text|json]
    ```

- **References Extraction** (`ast_index/references.py`): Regex-based symbol usage tracking
  - Universal method works across all supported languages
  - Extracts CamelCase types and function calls
  - Filters keywords, standard types, and locally-defined symbols
  - Removes comments and string literals before analysis
  - **Known limitations**: False positives in strings/comments, no import resolution, no scope awareness

### C# Parser Enhancements

**C#-specific improvements** for enhanced reference extraction:

- **Using Directives** (`ast_index/namespace_resolution.py`):
  - Extracts and stores `using` statements in database
  - Supports: regular using (`using System;`), static imports (`using static System.Math;`), aliases (`using App = MyNamespace.App;`)
  - Stored in `usings` table for cross-file analysis

- **Generic Types** (`ast_index/generic_parser.py`):
  - Extracts references to generic types like `List<T>`, `Dictionary<K,V>`
  - Handles nested generics: `List<List<int>>`, `Dictionary<string, List<T>>>`
  - Returns all type parameters as reference candidates

- **Context Filters** (`ast_index/context_filters.py`):
  - Excludes symbols from XML documentation (`/// <summary>`)
  - Excludes symbols from attributes (`[Obsolete("Do not use")]`)
  - Excludes symbols from string interpolation (`$"{user.Name}"`)
  - Identifies LINQ extension methods (`Where`, `Select`, `ToList`, etc.)

- **Enhanced CSharpParser** (`ast_index/parsers/csharp.py`):
  - Overrides `extract_references()` with C#-specific logic
  - Integrates all enhancement modules
  - Returns `NamespaceMapping` in `ParsedFile`

- **CLI usings command**: View using directives for C# files
  ```bash
  ast-index usings Models/UserRepository.cs
  ```

### Constants and Limits

- `BATCH_SIZE = 500` - Files processed per transaction
- `MAX_FILE_SIZE = 10MB` - Skip files larger than this
- Languages: Python, C#, JavaScript, TypeScript

### Data Flow

1. **Indexing**: Scan files → Parse with language-specific parsers → Extract symbols/inheritance/**references** → Store in SQLite
2. **Searching**: Query → SearchEngine (3-level strategy) → Return results
3. **References**: Query symbol name → Database lookup in `refs` table → Return all usages with context
4. **Updates**: Compare file mtimes → Parse changed files → Update database incrementally

### Language Parsers

All parsers follow the same pattern:
- Parse using tree-sitter grammar
- Extract: classes, functions, methods, interfaces, inheritance relationships, **references**
- Return `ParsedFile` with symbols, inheritances, and references
- Each parser calls `extract_references()` method (inherited from `BaseParser`) to find symbol usages

**Parser Registry**: Use `BaseParser.get_parser(language)` to get the appropriate parser class.

**References Extraction**:
- Handled by `ast_index/references.py` module
- Called automatically by all parsers during indexing
- Language-specific keywords and standard types defined in `ast_index/reference_keywords.py`
- Can be overridden per parser for language-specific optimizations

### Testing

- Tests use pytest fixtures in `tests/conftest.py`
- Test fixtures are in `tests/fixtures/` directory
- Integration tests cover full workflow: index → search → update → rebuild

### Configuration

- Project detection via `project_detection.py` using marker files (.csproj, package.json, etc.)
- Config file: `.ast-index.yaml` in project root (optional)
- Supports custom includes/excludes and language overrides

## References/Usages Implementation Details

The references extraction system uses a **regex-based approach** with these characteristics:

### Architecture

```
BaseParser.extract_references() (default implementation)
    ↓
extract_references_universal() (ast_index/references.py)
    ↓
1. strip_comments() - Remove comments
2. remove_string_literals() - Replace string literals with spaces
3. Extract identifiers using regex patterns:
   - CamelCase types: \b([A-Z][a-zA-Z0-9_$]*)\b
   - Function calls: \b([a-z][a-zA-Z0-9_$]*)\s*\(
4. Filter out exclusions via is_excluded_symbol()
5. Return list of Reference objects with context
```

### Filtering Logic

Symbols are excluded if they match:
- Language keywords (if, else, while, return, etc.)
- Standard library types (String, List, int, str, etc.)
- Locally-defined symbols in the same file
- Import/using/package statements

### Performance Optimizations

- Cached regex patterns (module-level)
- Skips lines > 2000 characters (minified code)
- Deduplicates references using set
- Context limited to 500 characters

### Accuracy Considerations

**Works well for:**
- Finding type references (UserRepository, IUserService)
- Finding method/function calls (getData(), handleClick())
- Quick approximations of symbol usage

**Known limitations:**
- No import resolution → may find usages of different symbols with same name
- No scope awareness → doesn't distinguish between local/remote symbols
- False positives in strings/comments (partially mitigated)
- False negatives for snake_case without calls
- Doesn't understand overload resolution or inheritance hierarchies

For exact semantic analysis, consider LSP-based tools or compiler APIs.
