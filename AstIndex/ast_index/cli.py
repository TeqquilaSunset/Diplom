import json
import sys
from pathlib import Path
from typing import Optional

import click

from . import __version__
from .config import Config, load_config, save_config
from .indexer import Indexer
from .search import SearchEngine
from .database import Database


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
@click.option("--limit", type=int, default=50, help="Maximum results")
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
@click.option("--limit", type=int, default=50, help="Maximum results")
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
@click.option("--limit", type=int, default=100, help="Maximum results")
@click.option("--show-context", is_flag=True, help="Show context of each reference")
@click.option("--file", type=str, help="Filter results by file path")
def usages(symbol: str, root: str, format: str, limit: int, show_context: bool, file: str):
    """Find all usages of a symbol."""
    config = load_config(Path(root))

    with SearchEngine(config=config) as engine:
        results = engine.search_usages(symbol, limit=limit)

        # Filter by file if specified
        if file:
            results = [r for r in results if r.get("ref_file", "").endswith(file)]

    if format == "json":
        output_result(results, format, f"Usages of {symbol}")
    elif show_context:
        # Custom output with context
        if not results:
            click.echo(f"No usages found for {symbol}")
            return

        click.echo(f"Usages of {symbol} ({len(results)} found):")
        click.echo()
        for ref in results:
            click.echo(f"  {ref['ref_file']}:{ref['ref_line']}")
            if ref.get('context'):
                click.echo(f"    {ref['context']}")
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


def main():
    cli()


if __name__ == "__main__":
    main()
