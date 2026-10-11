from pathlib import Path
from .config import settings

def get_data_root() -> Path:
    # Resolve against current working directory, which is the workspace root
    return settings.data_root.resolve()

def get_book_dir(slug: str) -> Path:
    return get_data_root() / "books" / slug

def get_page_dir(slug: str, page_number: int) -> Path:
    return get_book_dir(slug) / "pages" / f"p{page_number:04d}"

def get_relative_path(absolute_path: Path) -> str:
    """Returns path relative to DATA_ROOT for DB storage."""
    try:
        return str(absolute_path.relative_to(get_data_root())).replace("\\", "/")
    except ValueError:
        return str(absolute_path).replace("\\", "/")

def resolve_path(relative_path: str) -> Path:
    """Resolves DB relative path back to an absolute path."""
    return get_data_root() / relative_path
