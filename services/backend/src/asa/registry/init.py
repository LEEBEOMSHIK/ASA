"""Explicit registry migration for an already configured local/production database."""
import sys

from asa.config import Settings
from asa.registry.repository import migrate


def main() -> int:
    settings = Settings()
    if not settings.database_url:
        print("ASA_DATABASE_URL is required.", file=sys.stderr)
        return 1
    try:
        migrate(settings.database_url, settings.workspace_id)
    except Exception as error:
        print(f"Registry initialization failed ({type(error).__name__}).", file=sys.stderr)
        return 1
    print("Registry schema and workspace initialized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
