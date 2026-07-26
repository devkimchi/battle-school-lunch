from pathlib import Path

from .schemas import EvaluationArea

_ROLE_FILES = {
    EvaluationArea.NUTRITION: "nutrition.md",
    EvaluationArea.HEALTH: "health.md",
    EvaluationArea.MENU_QUALITY: "menu-quality.md",
}


class InstructionError(RuntimeError):
    """Raised when an agent instruction file cannot be loaded."""


class InstructionLoader:
    def __init__(
        self,
        *,
        rubric_path: Path | None = None,
        instruction_dir: Path | None = None,
    ) -> None:
        module_path = Path(__file__).resolve()
        self._rubric_path = rubric_path or self._find_rubric(module_path.parent)
        self._instruction_dir = instruction_dir or module_path.parents[1] / "instructions"

    def specialist(self, area: EvaluationArea) -> str:
        return self._combine(self._instruction_dir / _ROLE_FILES[area])

    def judge(self) -> str:
        return self._combine(self._instruction_dir / "judge.md")

    def _combine(self, role_path: Path) -> str:
        rubric = self._read(self._rubric_path)
        role = self._read(role_path)
        return f"{rubric}\n\n---\n\n{role}"

    @staticmethod
    def _read(path: Path) -> str:
        try:
            content = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise InstructionError(f"Unable to read agent instructions at {path}") from exc
        if not content:
            raise InstructionError(f"Agent instructions are empty at {path}")
        return content

    @staticmethod
    def _find_rubric(start: Path) -> Path:
        for directory in (start, *start.parents):
            candidate = directory / "EVALUATION-RUBRIC.md"
            if candidate.is_file():
                return candidate
        raise InstructionError("Unable to locate EVALUATION-RUBRIC.md")
