from __future__ import annotations

import json
from typing import Any

from agent_framework import (
    Agent,
    AgentExecutorResponse,
    Executor,
    SupportsChatGetResponse,
    Workflow,
    WorkflowContext,
    handler,
)
from agent_framework.orchestrations import ConcurrentBuilder
from typing_extensions import Never

from .instructions import InstructionLoader
from .schemas import (
    AnalysisResult,
    EvaluationArea,
    JudgeReport,
    MealData,
    SpecialistEvaluation,
)
from .scoring import calculate_school_scores


class EvaluationWorkflowError(RuntimeError):
    """Raised when a specialist or judge returns an invalid structured result."""


class JudgeAggregator(Executor):
    def __init__(
        self,
        *,
        judge: Agent[Any],
        school_a_meal: MealData,
        school_b_meal: MealData,
    ) -> None:
        super().__init__("judge")
        self._judge = judge
        self._school_a_meal = school_a_meal
        self._school_b_meal = school_b_meal

    @handler
    async def aggregate(
        self,
        results: list[AgentExecutorResponse],
        ctx: WorkflowContext[Never, AnalysisResult],
    ) -> None:
        evaluations = self._validated_evaluations(results)
        school_a_score, school_b_score = calculate_school_scores(
            self._school_a_meal.school,
            self._school_b_meal.school,
            evaluations,
        )
        judge_payload = {
            "school_a_meal": self._school_a_meal.model_dump(mode="json", by_alias=True),
            "school_b_meal": self._school_b_meal.model_dump(mode="json", by_alias=True),
            "evaluations": [
                evaluation.model_dump(mode="json", by_alias=True)
                for evaluation in evaluations
            ],
            "school_a_score": school_a_score.model_dump(mode="json", by_alias=True),
            "school_b_score": school_b_score.model_dump(mode="json", by_alias=True),
        }
        response = await self._judge.run(
            "다음 급식 비교 결과를 품질 검증하고 최종 보고서를 작성하세요.\n"
            + json.dumps(judge_payload, ensure_ascii=False)
        )
        if not isinstance(response.value, JudgeReport):
            raise EvaluationWorkflowError("Judge did not return a JudgeReport.")
        expected_winner = _winner(school_a_score.total, school_b_score.total)
        if response.value.winner != expected_winner:
            raise EvaluationWorkflowError("Judge winner does not match the calculated scores.")
        await ctx.yield_output(
            AnalysisResult(
                analysis_date=self._school_a_meal.date,
                school_a_meal=self._school_a_meal,
                school_b_meal=self._school_b_meal,
                evaluations=evaluations,
                school_a_score=school_a_score,
                school_b_score=school_b_score,
                judge=response.value,
            )
        )

    @staticmethod
    def _validated_evaluations(
        results: list[AgentExecutorResponse],
    ) -> list[SpecialistEvaluation]:
        evaluations: list[SpecialistEvaluation] = []
        for result in results:
            value = result.agent_response.value
            if not isinstance(value, SpecialistEvaluation):
                raise EvaluationWorkflowError(
                    f"{result.executor_id} did not return a SpecialistEvaluation."
                )
            evaluations.append(value)
        by_area = {evaluation.area: evaluation for evaluation in evaluations}
        if set(by_area) != set(EvaluationArea) or len(evaluations) != len(EvaluationArea):
            raise EvaluationWorkflowError("Specialist results do not cover each area exactly once.")
        return [by_area[area] for area in EvaluationArea]


def build_evaluation_workflow(
    *,
    client: SupportsChatGetResponse[Any],
    school_a_meal: MealData,
    school_b_meal: MealData,
    instructions: InstructionLoader | None = None,
) -> Workflow:
    loader = instructions or InstructionLoader()
    specialists = [
        Agent(
            client,
            name=f"{area.value}-agent",
            instructions=loader.specialist(area),
            default_options={"response_format": SpecialistEvaluation},
        )
        for area in EvaluationArea
    ]
    judge = Agent(
        client,
        name="ai-judge-agent",
        instructions=loader.judge(),
        default_options={"response_format": JudgeReport},
    )
    aggregator = JudgeAggregator(
        judge=judge,
        school_a_meal=school_a_meal,
        school_b_meal=school_b_meal,
    )
    return (
        ConcurrentBuilder(participants=specialists, intermediate_output_from="all_other")
        .with_aggregator(aggregator)
        .build()
    )


def evaluation_prompt(school_a_meal: MealData, school_b_meal: MealData) -> str:
    payload = {
        "school_a": school_a_meal.model_dump(mode="json", by_alias=True),
        "school_b": school_b_meal.model_dump(mode="json", by_alias=True),
    }
    return (
        "같은 날짜의 두 학교 중식을 담당 영역의 평가 기준으로 각각 평가하세요. "
        "입력에 없는 사실은 추정하지 마세요.\n"
        + json.dumps(payload, ensure_ascii=False)
    )


def _winner(score_a: float, score_b: float) -> str:
    if score_a == score_b:
        return "tie"
    return "school_a" if score_a > score_b else "school_b"
