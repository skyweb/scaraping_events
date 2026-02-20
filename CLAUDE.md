# Project Name

## Quick Facts
- **Stack**: Django, PostgreSQL, HTMX
- **Package Manager**: uv
- **Test Command**: `uv run pytest`
- **Lint Command**: `uv run ruff check .`
- **Format Command**: `uv run ruff format .`
- **Type Check**: `uv run pyright`

## Key Directories
- `apps/` - Django applications
- `config/` - Django settings and root URLconf
- `templates/` - Django templates
- `tests/` - Test files

## Code Style
- Python 3.12+ with type hints required
- No `Any` types - use proper type hints
- Use early returns, avoid nested conditionals
- Prefer Function-Based Views
