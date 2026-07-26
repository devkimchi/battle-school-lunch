import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "@/App";
import { allowedAnalysisDates } from "@/lib/analysis-agent";
import type {
  AnalysisAgentClient,
} from "@/lib/analysis-agent";
import type {
  AnalysisResult,
  AnalysisState,
  SchoolAssessment,
  SchoolCandidate,
} from "@/lib/analysis-types";
import { renderWithProviders } from "@/test/test-utils";

const agentMock = vi.hoisted(() => ({
  loadCandidates: vi.fn(),
  analyze: vi.fn(),
  abort: vi.fn(),
}));

vi.mock("@/lib/analysis-agent", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/analysis-agent")>();
  return {
    ...actual,
    createAnalysisAgentClient: () => agentMock as AnalysisAgentClient,
  };
});

const candidates: SchoolCandidate[] = Array.from({ length: 10 }, (_, index) => ({
  schoolCode: `S${index + 1}`,
  eduOfficeCode: `E${index + 1}`,
  schoolName: `${index + 1}번학교`,
  eduOfficeName: "서울특별시교육청",
  locationName: "서울특별시",
}));

const assessment = (score: number): SchoolAssessment => ({
  score,
  evidence: ["메뉴와 영양 정보에 근거했습니다."],
  strengths: ["식품군 구성이 다양합니다."],
  risks: [],
  improvements: ["채소 반찬을 보강하세요."],
});

function resultFixture(): AnalysisResult {
  const schoolA = candidates[0];
  const schoolB = candidates[1];
  const areas = [
    { area: "nutrition" as const, ratingA: 5, ratingB: 4, weight: 45 },
    { area: "health" as const, ratingA: 4, ratingB: 3, weight: 30 },
    { area: "menu_quality" as const, ratingA: 4, ratingB: 4, weight: 25 },
  ];

  return {
    analysisDate: allowedAnalysisDates().max,
    schoolAMeal: {
      school: schoolA,
      date: allowedAnalysisDates().max,
      dishes: ["현미밥", "된장국", "닭구이"],
      calorie: "650 Kcal",
      nutrition: ["단백질 25g"],
      origin: [],
      servings: 420,
    },
    schoolBMeal: {
      school: schoolB,
      date: allowedAnalysisDates().max,
      dishes: ["쌀밥", "미역국", "돈가스"],
      calorie: "720 Kcal",
      nutrition: ["단백질 22g"],
      origin: [],
      servings: 380,
    },
    evaluations: areas.map((area) => ({
      area: area.area,
      schoolA: assessment(area.ratingA),
      schoolB: assessment(area.ratingB),
      comparison: "첫 번째 학교가 채소와 단백질 구성이 더 좋습니다.",
      limitations: [],
    })),
    schoolAScore: {
      school: schoolA,
      areas: areas.map((area) => ({
        area: area.area,
        rating: area.ratingA,
        weight: area.weight,
        weightedScore: (area.ratingA / 5) * area.weight,
      })),
      total: 87,
    },
    schoolBScore: {
      school: schoolB,
      areas: areas.map((area) => ({
        area: area.area,
        rating: area.ratingB,
        weight: area.weight,
        weightedScore: (area.ratingB / 5) * area.weight,
      })),
      total: 72,
    },
    judge: {
      winner: "school_a",
      headline: "1번학교의 중식이 더 균형 잡혔습니다.",
      rationale: ["세 평가 영역에서 일관된 근거가 확인됐습니다."],
      schoolAImprovements: ["나트륨 정보를 추가로 확인하세요."],
      schoolBImprovements: ["튀김 조리법 비중을 줄이세요."],
      qualityNotes: ["수치가 없는 항목은 메뉴명으로 정성 평가했습니다."],
      limitations: ["당류와 포화지방의 정량 데이터는 제공되지 않았습니다."],
    },
  };
}

function selectingState(): AnalysisState {
  return {
    action: "load_candidates",
    phase: "selecting",
    candidates,
    selectedSchoolCodes: [],
    selectedDate: null,
    result: null,
    error: null,
  };
}

async function chooseComparison(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole("button", { name: /1번학교/ }));
  await user.click(screen.getByRole("button", { name: /2번학교/ }));
  await user.type(
    screen.getByLabelText("중식 날짜"),
    allowedAnalysisDates().max,
  );
}

describe("Meal analysis", () => {
  beforeEach(() => {
    agentMock.loadCandidates.mockReset();
    agentMock.analyze.mockReset();
    agentMock.abort.mockReset();
    agentMock.loadCandidates.mockImplementation(
      async (onState: (state: AnalysisState) => void) => {
        onState(selectingState());
      },
    );
  });

  it("switches to the analysis tab and loads ten random candidates", async () => {
    const user = userEvent.setup();
    renderWithProviders(<App />, { initialEntries: ["/"] });

    await user.click(
      screen.getByRole("link", { name: "학교 급식 분석" }),
    );

    expect(
      screen.getByRole("heading", { name: "학교 급식 분석" }),
    ).toBeInTheDocument();
    expect(await screen.findAllByRole("button", { name: /번학교/ })).toHaveLength(
      10,
    );
    expect(
      screen.queryByText("선택을 마치고 분석을 요청하세요"),
    ).not.toBeInTheDocument();
    expect(screen.queryByLabelText("중식 날짜")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("분석 질문")).not.toBeInTheDocument();
    expect(agentMock.loadCandidates).toHaveBeenCalledOnce();
  });

  it("opens each setup step after the previous selection is complete", async () => {
    const user = userEvent.setup();
    renderWithProviders(<App />, { initialEntries: ["/analysis"] });

    await user.click(await screen.findByRole("button", { name: /1번학교/ }));
    expect(screen.queryByLabelText("중식 날짜")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /2번학교/ }));
    expect(screen.queryByRole("button", { name: /1번학교/ })).not.toBeInTheDocument();
    expect(screen.getByLabelText("중식 날짜")).toBeInTheDocument();
    expect(screen.queryByLabelText("분석 질문")).not.toBeInTheDocument();

    await user.type(
      screen.getByLabelText("중식 날짜"),
      allowedAnalysisDates().max,
    );
    expect(screen.queryByLabelText("중식 날짜")).not.toBeInTheDocument();
    expect(screen.getByLabelText("분석 질문")).toHaveAttribute("rows", "2");

    await user.click(screen.getByRole("button", { name: "날짜 변경" }));
    expect(screen.getByLabelText("중식 날짜")).toHaveValue(
      allowedAnalysisDates().max,
    );
    expect(screen.queryByLabelText("분석 질문")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "학교 선택 변경" }));
    expect(screen.getByRole("button", { name: /1번학교/ })).toBeInTheDocument();
    expect(screen.queryByLabelText("중식 날짜")).not.toBeInTheDocument();
  });

  it("limits school selection and prepares a prompt without sending it", async () => {
    const user = userEvent.setup();
    renderWithProviders(<App />, { initialEntries: ["/analysis"] });

    await chooseComparison(user);
    await user.click(screen.getByRole("button", { name: "날짜 변경" }));

    expect(screen.getByLabelText("중식 날짜")).toHaveAttribute(
      "placeholder",
      "yyyy-mm-dd",
    );
    expect(screen.getByLabelText("중식 날짜")).toHaveValue(
      allowedAnalysisDates().max,
    );
    const calendarButton = screen.getByRole("button", {
      name: "달력에서 날짜 선택",
    });
    expect(calendarButton).toBeEnabled();
    await user.click(calendarButton);
    expect(
      screen.getByRole("dialog", { name: "날짜 선택 달력" }),
    ).toBeInTheDocument();
    expect(calendarButton).toHaveAttribute("aria-expanded", "true");
    await user.keyboard("{Escape}");
    expect(
      screen.queryByRole("dialog", { name: "날짜 선택 달력" }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "학교 선택 변경" }));
    expect(screen.getByRole("button", { name: /3번학교/ })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "분석 질문 열기" }));
    expect(screen.getByLabelText("분석 질문")).toHaveValue(
      `${allowedAnalysisDates().max} 중식을 기준으로 1번학교 (서울특별시 · 서울특별시교육청 · 학교 코드 S1)와 2번학교 (서울특별시 · 서울특별시교육청 · 학교 코드 S2)의 급식을 비교 분석해 주세요.`,
    );
    expect(agentMock.analyze).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "전송" })).toBeEnabled();
  });

  it("streams progress and renders the weighted report after manual send", async () => {
    const user = userEvent.setup();
    const result = resultFixture();
    let finishAnalysis: (() => void) | undefined;
    const waitUntilFinished = new Promise<void>((resolve) => {
      finishAnalysis = resolve;
    });
    agentMock.analyze.mockImplementation(
      async (
        state: AnalysisState,
        _prompt: string,
        onState: (next: AnalysisState) => void,
      ) => {
        onState({ ...state, phase: "evaluating" });
        await waitUntilFinished;
        onState({ ...state, phase: "completed", result });
      },
    );
    renderWithProviders(<App />, { initialEntries: ["/analysis"] });
    await chooseComparison(user);

    await user.click(screen.getByRole("button", { name: "전송" }));

    expect(
      await screen.findByText("세 전문 에이전트가 동시에 평가하고 있어요."),
    ).toBeInTheDocument();
    finishAnalysis?.();
    expect(
      await screen.findByRole("heading", {
        name: "1번학교의 중식이 더 균형 잡혔습니다.",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("87")).toBeInTheDocument();
    expect(screen.getByText("72")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByLabelText("분석 질문")).not.toBeInTheDocument();
    });
    expect(
      screen.getByRole("button", { name: "분석 질문 열기" }),
    ).toBeInTheDocument();
    expect(agentMock.analyze).toHaveBeenCalledOnce();
  });

  it("stops before evaluation when either school has no lunch", async () => {
    const user = userEvent.setup();
    agentMock.analyze.mockImplementation(
      async (
        state: AnalysisState,
        _prompt: string,
        onState: (next: AnalysisState) => void,
      ) => {
        onState({
          ...state,
          phase: "error",
          error: {
            code: "MEAL_NOT_FOUND",
            message: "2번학교의 해당 날짜 중식이 없습니다. 다른 날짜를 선택해 주세요.",
            retryable: false,
          },
        });
      },
    );
    renderWithProviders(<App />, { initialEntries: ["/analysis"] });
    await chooseComparison(user);

    await user.click(screen.getByRole("button", { name: "전송" }));

    expect(
      await screen.findByText(
        "2번학교의 해당 날짜 중식이 없습니다. 다른 날짜를 선택해 주세요.",
      ),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.queryByRole("heading", { name: /더 균형/ }),
      ).not.toBeInTheDocument(),
    );
  });
});
