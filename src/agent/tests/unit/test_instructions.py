from pathlib import Path

import pytest

from app.instructions import InstructionError, InstructionLoader
from app.schemas import EvaluationArea

pytestmark = pytest.mark.unit


def test_loader_combines_canonical_rubric_with_role(tmp_path: Path) -> None:
    rubric = tmp_path / "EVALUATION-RUBRIC.md"
    instructions = tmp_path / "instructions"
    instructions.mkdir()
    rubric.write_text("canonical rubric", encoding="utf-8")
    (instructions / "nutrition.md").write_text("nutrition role", encoding="utf-8")

    result = InstructionLoader(
        rubric_path=rubric,
        instruction_dir=instructions,
    ).specialist(EvaluationArea.NUTRITION)

    assert "canonical rubric" in result
    assert "nutrition role" in result


def test_loader_rejects_missing_instruction(tmp_path: Path) -> None:
    rubric = tmp_path / "EVALUATION-RUBRIC.md"
    rubric.write_text("rubric", encoding="utf-8")
    with pytest.raises(InstructionError, match="Unable to read"):
        InstructionLoader(
            rubric_path=rubric,
            instruction_dir=tmp_path,
        ).judge()
