import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.evaluation_service import EvaluationService


def main() -> None:
    summary = EvaluationService().run()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
