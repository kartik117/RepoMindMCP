import logging
import shutil
from pathlib import Path

import git

from repomind.config import Settings, get_settings
from repomind.graph import GraphWriter, get_driver
from repomind.parsers import ParsedFile, parse_javascript_file, parse_python_file, parse_typescript_file

logger = logging.getLogger(__name__)

_PARSERS = {
    ".py": parse_python_file,
    ".js": parse_javascript_file,
    ".jsx": parse_javascript_file,
    ".mjs": parse_javascript_file,
    ".ts": parse_typescript_file,
    ".tsx": parse_typescript_file,
}

_IGNORED_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}


def clone_repo(repo_url: str, dest_dir: Path) -> Path:
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.parent.mkdir(parents=True, exist_ok=True)
    git.Repo.clone_from(repo_url, dest_dir, depth=1)
    return dest_dir


def parse_repo(repo_root: Path) -> list[ParsedFile]:
    parsed_files = []
    for file_path in repo_root.rglob("*"):
        if not file_path.is_file() or any(part in _IGNORED_DIRS for part in file_path.parts):
            continue
        parser = _PARSERS.get(file_path.suffix)
        if parser is None:
            continue
        try:
            parsed_files.append(parser(file_path, repo_root))
        except (SyntaxError, UnicodeDecodeError) as exc:
            logger.warning("Skipping unparseable file %s: %s", file_path, exc)
    return parsed_files


def repo_slug(repo_url: str) -> str:
    return repo_url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")


def ingest_repo(repo_url: str, settings: Settings | None = None, clear_existing: bool = True) -> dict:
    """Clones, parses, and graphs one repo.

    clear_existing wipes the whole graph first -- qualified names aren't
    namespaced per repo, so ingesting a second repo into the same graph
    without clearing risks colliding two unrelated modules that happen to
    share a path (e.g. both have a utils.py). One repo's graph at a time.
    """
    settings = settings or get_settings()
    clone_dir = Path(settings.clone_dir) / repo_slug(repo_url)
    repo_root = clone_repo(repo_url, clone_dir)
    parsed_files = parse_repo(repo_root)

    driver = get_driver(settings)
    try:
        writer = GraphWriter(driver)
        if clear_existing:
            writer.clear()
        writer.write_structure(parsed_files)
        writer.write_relationships(parsed_files)
    finally:
        driver.close()

    return {
        "repo_url": repo_url,
        "files_parsed": len(parsed_files),
        "classes": sum(len(f.classes) for f in parsed_files),
        "functions": sum(
            len(f.functions) + sum(len(cls.methods) for cls in f.classes) for f in parsed_files
        ),
    }
