from collections.abc import Iterable
from typing import Literal

from .schemas import (
    EvaluationArea,
    SchoolCandidate,
    SchoolScore,
    SpecialistEvaluation,
    WeightedAreaScore,
)

AREA_WEIGHTS: dict[EvaluationArea, int] = {
    EvaluationArea.NUTRITION: 45,
    EvaluationArea.HEALTH: 30,
    EvaluationArea.MENU_QUALITY: 25,
}


def weighted_score(rating: int, weight: int) -> float:
    if not 1 <= rating <= 5:
        raise ValueError("Rating must be between 1 and 5.")
    if not 0 <= weight <= 100:
        raise ValueError("Weight must be between 0 and 100.")
    return round((rating / 5) * weight, 1)


def calculate_school_scores(
    school_a: SchoolCandidate,
    school_b: SchoolCandidate,
    evaluations: Iterable[SpecialistEvaluation],
) -> tuple[SchoolScore, SchoolScore]:
    by_area = {evaluation.area: evaluation for evaluation in evaluations}
    missing = set(AREA_WEIGHTS) - set(by_area)
    unexpected = set(by_area) - set(AREA_WEIGHTS)
    if missing or unexpected or len(by_area) != len(AREA_WEIGHTS):
        raise ValueError("Exactly one evaluation per configured area is required.")

    def build_score(
        school: SchoolCandidate,
        side: Literal["school_a", "school_b"],
    ) -> SchoolScore:
        areas: list[WeightedAreaScore] = []
        for area, weight in AREA_WEIGHTS.items():
            assessment = getattr(by_area[area], side)
            areas.append(
                WeightedAreaScore(
                    area=area,
                    rating=assessment.score,
                    weight=weight,
                    weighted_score=weighted_score(assessment.score, weight),
                )
            )
        return SchoolScore(
            school=school,
            areas=areas,
            total=round(sum(item.weighted_score for item in areas), 1),
        )

    return build_score(school_a, "school_a"), build_score(school_b, "school_b")
