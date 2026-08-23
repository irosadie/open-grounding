import json
from pathlib import Path

from app.main import create_app


def main() -> None:
    output = Path(__file__).resolve().parents[3] / "docs" / "openapi.json"
    output.write_text(json.dumps(create_app().openapi(), indent=2) + "\n")


if __name__ == "__main__":
    main()
