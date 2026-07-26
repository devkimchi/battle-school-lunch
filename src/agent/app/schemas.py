from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
    )


class EvaluationArea(StrEnum):
    NUTRITION = "nutrition"
    HEALTH = "health"
    MENU_QUALITY = "menu_quality"


class SchoolCandidate(ApiModel):
    school_code: str
    edu_office_code: str
    school_name: str
    edu_office_name: str
    location_name: str | None = None


class MealData(ApiModel):
    school: SchoolCandidate
    date: date
    dishes: list[str]
    calorie: str | None = None
    nutrition: list[str] = Field(default_factory=list)
    origin: list[str] = Field(default_factory=list)
    servings: int | float | None = None


class SchoolAssessment(ApiModel):
    score: int = Field(ge=1, le=5)
    evidence: list[str] = Field(min_length=1)
    strengths: list[str] = Field(min_length=1)
    risks: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(min_length=1)


class SpecialistEvaluation(ApiModel):
    area: EvaluationArea
    school_a: SchoolAssessment
    school_b: SchoolAssessment
    comparison: str = Field(min_length=1)
    limitations: list[str] = Field(default_factory=list)


class WeightedAreaScore(ApiModel):
    area: EvaluationArea
    rating: int = Field(ge=1, le=5)
    weight: int
    weighted_score: float


class SchoolScore(ApiModel):
    school: SchoolCandidate
    areas: list[WeightedAreaScore]
    total: float = Field(ge=0, le=100)


class JudgeReport(ApiModel):
    winner: Literal["school_a", "school_b", "tie"]
    headline: str = Field(min_length=1)
    rationale: list[str] = Field(min_length=1)
    school_a_improvements: list[str] = Field(min_length=1)
    school_b_improvements: list[str] = Field(min_length=1)
    quality_notes: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class AnalysisResult(ApiModel):
    analysis_date: date
    school_a_meal: MealData
    school_b_meal: MealData
    evaluations: list[SpecialistEvaluation]
    school_a_score: SchoolScore
    school_b_score: SchoolScore
    judge: JudgeReport


class AgentError(ApiModel):
    code: str
    message: str
    retryable: bool = False


class AnalysisState(ApiModel):
    action: Literal["load_candidates", "analyze"] | None = None
    phase: Literal[
        "idle",
        "loading_candidates",
        "selecting",
        "loading_meals",
        "evaluating",
        "judging",
        "completed",
        "error",
    ] = "idle"
    candidates: list[SchoolCandidate] = Field(default_factory=list)
    selected_school_codes: list[str] = Field(default_factory=list)
    selected_date: date | None = None
    result: AnalysisResult | None = None
    error: AgentError | None = None
