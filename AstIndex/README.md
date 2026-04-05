# AST Index

**Версия:** 0.1.1 (от 2026-03-24)

A structural code search tool that indexes codebases using Abstract Syntax Tree (AST) analysis.

## ✨ Что нового в 0.1.1

### 🐛 Исправленные критические ошибки:

1. ✅ **Исправлен сбой `--show-context`** в команде `usages` - теперь можно просматривать контекст использований
2. ✅ **Исправлен сбой `--file`** в команде `usages` - теперь фильтрация по файлу работает корректно
3. ✅ **Исправлен сбой при `--show-context` + `--limit`** - комбинация опций больше не вызывает ошибок

### 🔧 Улучшения:

4. ✅ **Валидация отрицательных лимитов** - теперь `--limit -5` вызовет понятную ошибку

## Features

- Multi-language support (Python, JavaScript, TypeScript, C#)
- Structural code search (find functions, classes, methods by name/pattern)
- Symbol usage tracking (find where symbols are referenced/called)
- SQLite-based index with FTS5 full-text search
- Incremental indexing with file change detection
- Inheritance hierarchy analysis
- JSON output for AI/CI integration

## Installation

### Quick install from source:

```bash
cd C:\Users\sc-20\source\repos\Diplom\AstIndex
pip install -e .
```

### Install from wheel:

```bash
cd C:\Users\sc-20\source\repos\Diplom\AstIndex\dist
pip install ast_index-0.1.1-py3-none-any.whl
```

Подробная инструкция: см. [INSTALL.md](INSTALL.md)

## Usage

```bash
# Index a project
ast-index index

# Search for symbols
ast-index search "SymbolName"

# Search for classes
ast-index class "ClassName"

# Find all usages of a symbol
ast-index usages "SymbolName"

# Find usages with context (исправлено в 0.1.1!)
ast-index usages "SymbolName" --show-context

# Filter usages by file (исправлено в 0.1.1!)
ast-index usages "SymbolName" --file "path/to/file.cs"

# Limit results with validation (новое в 0.1.1!)
ast-index search "Query" --limit 10

# Analyze inheritance
ast-index inheritance "BaseClass" --direction children

# View index statistics
ast-index stats

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

### C# Enhancements

For C# projects, AST Index provides enhanced reference extraction:

- ✅ **Using Directives Analysis**: Extracts and stores `using` statements (System, System.Collections.Generic, etc.)
- ✅ **Generic Types**: Extracts references to generic types like `List<T>`, `Dictionary<K,V>`
- ✅ **Context-Aware Filtering**: Excludes symbols from XML documentation (`/// <summary>`), attributes (`[Obsolete]`), and string interpolation (`$"{var}"`)
- ✅ **LINQ Extension Methods**: Identifies common LINQ methods (`Where`, `Select`, `ToList`, etc.)

**Show using directives for a C# file:**
```bash
ast-index usings Models/UserRepository.cs
```

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
