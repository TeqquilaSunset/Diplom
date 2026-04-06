# Definition Command

## Overview

The `definition` command finds the definition of a symbol with import resolution.

## Usage

```bash
ast-index definition SYMBOL [--file PATH] [--format text|json]
```

### Arguments

- `SYMBOL`: Symbol name to find

### Options

- `--file PATH`: Reference file path (enables import resolution)
- `--format text|json`: Output format (default: text)
- `--root PATH`: Project root directory (default: current directory)

## Examples

### Find definition without file context

```bash
ast-index definition UserRepository
```

Output:
```
Definition of UserRepository:
  Kind: class
  File: /project/Models/UserRepository.cs
  Lines: 10-50
  Signature: class UserRepository : IUserRepository
```

### Find definition with import resolution

```bash
ast-index definition UserRepository --file Controllers/HomeController.cs
```

This will use the `using` directives in `HomeController.cs` to resolve which `UserRepository` is being referenced.

### JSON output for AI integration

```bash
ast-index definition User --format json
```

Output:
```json
{
  "name": "User",
  "kind": "class",
  "file_path": "/project/Models/User.cs",
  "line_start": 1,
  "line_end": 25,
  "signature": "class User"
}
```

## How It Works

1. If `--file` is specified:
   - Reads using/import directives from the file
   - Resolves the symbol considering imports
   - Returns the most likely definition

2. If `--file` is not specified:
   - Returns all symbols with the given name
   - Prioritizes classes/interfaces
   - Returns the first match if multiple

## Resolution Algorithm

When `--file` is specified, the resolver uses a scoring system:

1. **Same file** (score +1000): Symbol defined in the same file as reference
2. **Using/import match** (score +500): Symbol's namespace matches using directives
3. **Alias match** (score +600): Symbol matches an alias in using directives

The symbol with the highest score is returned.

## Limitations

- Currently supports C# using directives
- Python/JS/TS import resolution coming soon
- Namespace heuristics may not match all project structures
- Requires symbols to be indexed first

## Use Cases

### Refactoring

Find where a symbol is defined before renaming:
```bash
ast-index definition OldClassName --file src/FileUsingIt.cs
```

### Code Navigation

Quickly jump to a symbol's definition:
```bash
ast-index definition MyClass
```

### Impact Analysis

Understand which definition will be affected:
```bash
ast-index definition processData --file src/AnotherFile.cs --format json
```

## Related Commands

- `usages` - Find all usages of a symbol
- `search` - Search for symbols by name
- `class` - Search for class/interface definitions
- `usings` - Show using directives for a file
