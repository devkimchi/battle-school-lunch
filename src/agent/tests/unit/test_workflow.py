import asyncio
from datetime import date
from typing import Any

import pytest
from agent_framework import ChatResponse, Message

from app.schemas import (
    AnalysisResult,
    EvaluationArea,
    JudgeReport,
    MealData,
    SchoolAssessment,
    SchoolCandidate,
    SpecialistEvaluation,
)
from app.workflow import build_evaluation_workflow, evaluation_prompt

pytestmark = pytest.mark.unit


def school(code: str, name: str) -> SchoolCandidate:
    return SchoolCandidate(
        school_code=code,
        edu_office_code="B10",
        school_name=name,
        edu_office_name="서울특별시교육청",
    )


def meal(candidate: SchoolCandidate) -> MealData:
    return MealData(
        school=candidate,
        date=date(2026, 7, 1),
        dishes=["현미밥", "된장국", "채소무침"],
        calorie="700 Kcal",
        nutrition=["탄수화물(g): 80"],
    )


class FakeChatClient:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0

    async def get_response(
        self,
        messages: list[Message],
        *,
        stream: bool = False,
        options: dict[str, Any] | None = None,
        **_kwargs: Any,
    ) -> ChatResponse[Any]:
        assert not stream
        assert messages
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1
        response_format = (options or {}).get("response_format")
        instructions = str((options or {}).get("instructions", ""))
        if response_format is JudgeReport:
            value: Any = JudgeReport(
                winner="school_a",
                headline="가학교 우세",
                rationale=["총점이 더 높습니다."],
                school_a_improvements=["채소 종류를 늘립니다."],
                school_b_improvements=["가공식품을 줄입니다."],
            )
        else:
            area = (
                EvaluationArea.NUTRITION
                if "Nutrition Agent" in instructions
                else EvaluationArea.HEALTH
                if "Health Agent" in instructions
                else EvaluationArea.MENU_QUALITY
            )
            assessment_a = SchoolAssessment(
                score=5,
                evidence=["현미밥"],
                strengths=["균형"],
                improvements=["과일 추가"],
            )
            assessment_b = SchoolAssessment(
                score=3,
                evidence=["구성"],
                strengths=["기본 구성"],
                improvements=["채소 추가"],
            )
            value = SpecialistEvaluation(
                area=area,
                school_a=assessment_a,
                school_b=assessment_b,
                comparison="가학교가 우수합니다.",
            )
        return ChatResponse(
            messages=[Message(role="assistant", contents=["structured response"])],
            value=value,
        )


async def test_workflow_runs_specialists_concurrently_then_judges() -> None:
    client = FakeChatClient()
    school_a_meal = meal(school("1", "가학교"))
    school_b_meal = meal(school("2", "나학교"))
    workflow = build_evaluation_workflow(
        client=client,
        school_a_meal=school_a_meal,
        school_b_meal=school_b_meal,
    )

    result = await workflow.run(evaluation_prompt(school_a_meal, school_b_meal))
    outputs = result.get_outputs()

    assert client.max_active == 3
    assert len(outputs) == 1
    assert isinstance(outputs[0], AnalysisResult)
    assert outputs[0].school_a_score.total == 100
    assert outputs[0].school_b_score.total == 60
    assert outputs[0].judge.winner == "school_a"
