import json
from pathlib import Path

import click

from . import __version__
from .config import Config, load_config, save_config
from .database import Database
from .indexer import Indexer
from .search import SearchEngine


def validate_limit(ctx, param, value):
    """Validate that limit is a positive integer."""
    if value is not None and value <= 0:
        raise click.BadParameter("Limit must be a positive integer")
    return value


def output_result(result, format: str, message: str = None):
    """Output result in specified format."""
    if format == "json":
        click.echo(json.dumps(result, indent=2, default=str))
    else:
        if message:
            click.echo(message)
        if isinstance(result, dict):
            for key, value in result.items():
                click.echo(f"{key}: {value}")
        elif isinstance(result, list):
            for item in result:
                if isinstance(item, dict):
                    click.echo(f"- {item.get('name', item)}")
                else:
                    click.echo(f"- {item}")


@click.group()
@click.version_option(version=__version__)
def cli():
    """AST Index - Structural code search tool."""
    pass


@cli.command()
@click.option("--root", type=click.Path(exists=True), default=".", help="Project root directory")
@click.option("--format", type=click.Choice(["text", "json"]), default="text", help="Output format")
def index(root: str, format: str):
    """Index the project."""
    config = load_config(Path(root))

    with Indexer(config=config) as indexer:
        stats = indexer.index()

    output_result(stats, format, "Indexing complete")


@cli.command()
@click.option("--root", type=click.Path(exists=True), default=".", help="Project root directory")
@click.option("--format", type=click.Choice(["text", "json"]), default="text", help="Output format")
def update(root: str, format: str):
    """Update index (incremental)."""
    config = load_config(Path(root))

    with Indexer(config=config) as indexer:
        stats = indexer.update()

    output_result(stats, format, "Update complete")


@cli.command()
@click.option("--root", type=click.Path(exists=True), default=".", help="Project root directory")
@click.option("--format", type=click.Choice(["text", "json"]), default="text", help="Output format")
def rebuild(root: str, format: str):
    """Rebuild index from scratch."""
    config = load_config(Path(root))

    with Indexer(config=config) as indexer:
        stats = indexer.rebuild()

    output_result(stats, format, "Rebuild complete")


@cli.command()
@click.argument("query")
@click.option("--root", type=click.Path(exists=True), default=".", help="Project root directory")
@click.option("--format", type=click.Choice(["text", "json"]), default="text", help="Output format")
@click.option(
    "--level",
    type=click.Choice(["exact", "prefix", "fuzzy"]),
    default="prefix",
    help="Search level",
)
@click.option("--limit", type=int, default=50, help="Maximum results", callback=validate_limit)
def search(query: str, root: str, format: str, level: str, limit: int):
    """Search for symbols by name."""
    config = load_config(Path(root))

    with SearchEngine(config=config) as engine:
        results = engine.search(query, limit=limit, level=level)

    output_result(results, format, f"Found {len(results)} symbols")


@cli.command("class")
@click.argument("name")
@click.option("--root", type=click.Path(exists=True), default=".", help="Project root directory")
@click.option("--format", type=click.Choice(["text", "json"]), default="text", help="Output format")
@click.option("--limit", type=int, default=50, help="Maximum results", callback=validate_limit)
def search_class(name: str, root: str, format: str, limit: int):
    """Search for class/interface definitions."""
    config = load_config(Path(root))

    with SearchEngine(config=config) as engine:
        results = engine.search_class(name, limit=limit)

    output_result(results, format, f"Found {len(results)} classes")


@cli.command()
@click.argument("symbol")
@click.option("--root", type=click.Path(exists=True), default=".", help="Project root directory")
@click.option("--format", type=click.Choice(["text", "json"]), default="text", help="Output format")
@click.option("--limit", type=int, default=100, help="Maximum results", callback=validate_limit)
@click.option("--show-context", is_flag=True, help="Show context of each reference")
@click.option("--file", type=str, help="Filter results by file path")
def usages(symbol: str, root: str, format: str, limit: int, show_context: bool, file: str):
    """Find all usages of a symbol."""
    config = load_config(Path(root))

    with SearchEngine(config=config) as engine:
        results = engine.search_usages(symbol, limit=limit)

        # Filter by file if specified - filter references, not the whole result dict
        if file:
            results["references"] = [
                r for r in results["references"]
                if r.get("ref_file", "").endswith(file)
            ]

    if format == "json":
        output_result(results, format, f"Usages of {symbol}")
    elif show_context:
        # Custom output with context - iterate over references, not the dict
        references = results["references"]
        definitions = results.get("definitions", [])

        if not references and not definitions:
            click.echo(f"No usages found for {symbol}")
            return

        # Show definitions first
        if definitions:
            click.echo(f"Definitions of {symbol}:")
            for defn in definitions:
                click.echo(f"  {defn['file_path']}:{defn['line_start']}")
            click.echo()

        # Show references
        if references:
            click.echo(f"Usages of {symbol} ({len(references)} found):")
            click.echo()
            for ref in references:
                click.echo(f"  {ref['ref_file']}:{ref['ref_line']}")
                if ref.get('context'):
                    # Truncate context if too long
                    context = ref['context']
                    if len(context) > 200:
                        context = context[:200] + "..."
                    click.echo(f"    {context}")
                click.echo()
    else:
        output_result(results, format, f"Usages of {symbol}")


@cli.command()
@click.argument("symbol")
@click.option("--root", type=click.Path(exists=True), default=".", help="Project root directory")
@click.option("--format", type=click.Choice(["text", "json"]), default="text", help="Output format")
@click.option(
    "--direction",
    type=click.Choice(["children", "parents", "both"]),
    default="both",
    help="Direction",
)
def inheritance(symbol: str, root: str, format: str, direction: str):
    """Search inheritance hierarchy."""
    config = load_config(Path(root))

    with SearchEngine(config=config) as engine:
        results = engine.search_inheritance(symbol, direction=direction)

    output_result(results, format, f"Inheritance for {symbol}")


@cli.command()
@click.option("--root", type=click.Path(exists=True), default=".", help="Project root directory")
@click.option("--format", type=click.Choice(["text", "json"]), default="text", help="Output format")
def stats(root: str, format: str):
    """Show index statistics."""
    config = load_config(Path(root))

    with Database(config.db_path) as db:
        stats = db.get_stats()

    output_result(stats, format, "Index statistics")


@cli.command()
@click.option("--root", type=click.Path(exists=True), default=".", help="Project root directory")
def init(root: str):
    """Initialize project with default config."""
    config_path = Path(root) / ".ast-index.yaml"

    if config_path.exists():
        click.echo(f"Config already exists at {config_path}")
        return

    config = Config(root=Path(root))
    save_config(config, config_path)
    click.echo(f"Created config at {config_path}")


@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--root", type=click.Path(exists=True), help="Project root directory")
@click.option("--format", type=click.Choice(["text", "json"]), default="text", help="Output format")
def usings(file_path: str, root: str, format: str):
    """Показать using директивы для C# файла."""
    from pathlib import Path

    from .database import Database
    from .project_detection import detect_project_root

    if root:
        project_root = Path(root).resolve()
    else:
        project_root = detect_project_root(Path(file_path).resolve())

    if not project_root:
        click.echo("Error: Cannot find project root", err=True)
        return

    config = load_config(project_root)
    db = Database(config.db_path)
    file_path_str = str(Path(file_path).resolve())

    with db:
        mapping = db.get_usings_for_file(file_path_str)

    if format == "json":
        import json
        output = {
            'file': file_path_str,
            'imports': list(mapping.imports),
            'static_imports': list(mapping.static_imports),
            'aliases': mapping.aliases
        }
        click.echo(json.dumps(output, indent=2))
    else:
        click.echo(f"Usings for {file_path}:")
        click.echo("\nImports:")
        for imp in sorted(mapping.imports):
            click.echo(f"  {imp}")

        if mapping.static_imports:
            click.echo("\nStatic Imports:")
            for imp in sorted(mapping.static_imports):
                click.echo(f"  {imp}")

        if mapping.aliases:
            click.echo("\nAliases:")
            for alias, target in sorted(mapping.aliases.items()):
                click.echo(f"  {alias} = {target}")


def main():
    cli()


if __name__ == "__main__":
    main()
