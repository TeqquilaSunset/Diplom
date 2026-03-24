# AST Index

A structural code search tool that indexes codebases using Abstract Syntax Tree (AST) analysis.

## Features

- Multi-language support (Python, JavaScript, TypeScript, C#)
- Structural code search (find functions, classes, methods by name/pattern)
- Symbol usage tracking (find where symbols are referenced/called)
- SQLite-based index for fast queries
- Incremental indexing with file change detection

## Installation

```bash
pip install ast-index
```

## Usage

```bash
# Index a project
ast-index index /path/to/project

# Search for functions
ast-index search function "handle.*"

# Search for classes
ast-index search class "User"

# Find usages of a symbol
ast-index usages UserRepository

# Find usages with context
ast-index usages --show-context UserRepository

# Find usages in specific file
ast-index usages --file UserService.cs UserRepository
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check .

# Run type checking
mypy ast_index
```

## Symbol Usage Tracking

AST Index includes a **usages** command that finds where symbols are referenced in your codebase. This uses a regex-based approach with the following characteristics:

### What Works Well

- ✅ Finds CamelCase type references (classes, interfaces)
- ✅ Finds function/method calls
- ✅ Filters out language keywords and standard types
- ✅ Excludes locally-defined symbols
- ✅ Removes comments and string literals from search
- ✅ Shows context lines for each reference

### Known Limitations

The regex-based approach has some limitations:

- ⚠️ **False positives**: May find symbol references in string literals or comments (though we try to exclude these)
- ⚠️ **No import resolution**: Doesn't resolve imports/using statements, so references may point to the wrong definition
- ⚠️ **No scope awareness**: Doesn't understand variable scope or namespaces
- ⚠️ **Language-specific patterns**: Works best with CamelCase conventions; snake_case symbols without calls may be missed

### Example Output

```bash
$ ast-index usages --show-context UserRepository

Usages of UserRepository (3 found):

  src/UserService.cs:15
      var repo = new UserRepository();

  src/UserService.cs:16
      repo.GetData();

  tests/UserServiceTests.cs:42
      var mockRepo = new Mock<UserRepository>();
```

For more accurate results in complex scenarios, consider using language server protocol (LSP) based tools.
