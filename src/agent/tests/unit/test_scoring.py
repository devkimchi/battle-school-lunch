import pytest

from app.schemas import (
    EvaluationArea,
    SchoolAssessment,
    SchoolCandidate,
    SpecialistEvaluation,
)
from app.scoring import calculate_school_scores, weighted_score

pytestmark = pytest.mark.unit


def school(code: str, name: str) -> SchoolCandidate:
    return SchoolCandidate(
        school_code=code,
        edu_office_code="B10",
        school_name=name,
        edu_office_name="서울특별시교육청",
    )


def evaluation(
    area: EvaluationArea,
    school_a_score: int,
    school_b_score: int,
) -> SpecialistEvaluation:
    def assessment(score: int) -> SchoolAssessment:
        return SchoolAssessment(
            score=score,
            evidence=["근거"],
            strengths=["강점"],
            improvements=["개선"],
        )

    return SpecialistEvaluation(
        area=area,
        school_a=assessment(school_a_score),
        school_b=assessment(school_b_score),
        comparison="비교",
    )


def test_weighted_score_uses_five_point_scale() -> None:
    assert weighted_score(4, 45) == 36.0


def test_calculate_school_scores_applies_configured_weights() -> None:
    score_a, score_b = calculate_school_scores(
        school("1", "가학교"),
        school("2", "나학교"),
        [
            evaluation(EvaluationArea.NUTRITION, 4, 3),
            evaluation(EvaluationArea.HEALTH, 5, 4),
            evaluation(EvaluationArea.MENU_QUALITY, 3, 5),
        ],
    )

    assert score_a.total == 81.0
    assert score_b.total == 76.0
    assert [item.weight for item in score_a.areas] == [45, 30, 25]


def test_calculate_school_scores_requires_each_area_once() -> None:
    with pytest.raises(ValueError, match="Exactly one evaluation"):
        calculate_school_scores(
            school("1", "가학교"),
            school("2", "나학교"),
            [evaluation(EvaluationArea.NUTRITION, 4, 3)],
        )
