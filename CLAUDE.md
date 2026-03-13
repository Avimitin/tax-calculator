# Development Environment

This project uses Nix for development environment management. Always use `uv` from the nix flake for Python dependency management.

## Setup

Enter the development shell before running any Python-related commands:

```bash
nix develop
```

## Python Dependencies

Use `uv` for all Python package management:

- `uv add <package>` - Add a new dependency
- `uv remove <package>` - Remove a dependency
- `uv sync` - Sync dependencies from pyproject.toml
- `uv run <command>` - Run a command in the virtual environment
- `uv pip list` - List installed packages
