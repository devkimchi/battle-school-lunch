import { test, expect, type Page } from "../support/test-base";

const candidates = Array.from({ length: 10 }, (_, index) => ({
  schoolCode: `S${index + 1}`,
  eduOfficeCode: "B10",
  schoolName: index === 0 ? "한빛중학교" : index === 1 ? "새봄중학교" : `후보${index + 1}학교`,
  eduOfficeName: "서울특별시교육청",
  locationName: "서울특별시",
}));

function sse(body: { threadId: string; runId: string }, snapshot: unknown) {
  return [
    { type: "RUN_STARTED", threadId: body.threadId, runId: body.runId },
    { type: "STATE_SNAPSHOT", snapshot },
    { type: "RUN_FINISHED", threadId: body.threadId, runId: body.runId },
  ]
    .map((event) => `data: ${JSON.stringify(event)}\n\n`)
    .join("");
}

function completedState(selectedDate: string) {
  const assessment = (score: number) => ({
    score,
    evidence: ["메뉴와 영양 정보에 근거했습니다."],
    strengths: ["식품군 구성이 다양합니다."],
    risks: [],
    improvements: ["채소 반찬을 보강하세요."],
  });
  const areas = [
    { area: "nutrition", ratingA: 5, ratingB: 4, weight: 45 },
    { area: "health", ratingA: 4, ratingB: 3, weight: 30 },
    { area: "menu_quality", ratingA: 4, ratingB: 4, weight: 25 },
  ];
  const meal = (school: (typeof candidates)[number], dishes: string[]) => ({
    school,
    date: selectedDate,
    dishes,
    calorie: "680 Kcal",
    nutrition: ["단백질(g): 25"],
    origin: [],
    servings: 400,
  });

  return {
    action: "analyze",
    phase: "completed",
    candidates,
    selectedSchoolCodes: ["S1", "S2"],
    selectedDate,
    error: null,
    result: {
      analysisDate: selectedDate,
      schoolAMeal: meal(candidates[0], ["현미밥", "된장국", "닭구이"]),
      schoolBMeal: meal(candidates[1], ["쌀밥", "미역국", "돈가스"]),
      evaluations: areas.map((area) => ({
        area: area.area,
        schoolA: assessment(area.ratingA),
        schoolB: assessment(area.ratingB),
        comparison: "한빛중학교의 식품군 구성이 더 다양합니다.",
        limitations: [],
      })),
      schoolAScore: {
        school: candidates[0],
        areas: areas.map((area) => ({
          area: area.area,
          rating: area.ratingA,
          weight: area.weight,
          weightedScore: (area.ratingA / 5) * area.weight,
        })),
        total: 87,
      },
      schoolBScore: {
        school: candidates[1],
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
        headline: "한빛중학교의 중식이 더 균형 잡혔습니다.",
        rationale: ["세 평가 영역의 근거가 일관됩니다."],
        schoolAImprovements: ["나트륨 정보를 확인하세요."],
        schoolBImprovements: ["튀김 조리법 비중을 줄이세요."],
        qualityNotes: [],
        limitations: ["일부 영양소는 정량 데이터가 없습니다."],
      },
    },
  };
}

async function installAgentMock(
  page: Page,
  analyze: (selectedDate: string) => unknown,
) {
  let analyzeRequests = 0;
  await page.route("**/agent", async (route) => {
    const body = route.request().postDataJSON() as {
      threadId: string;
      runId: string;
      state: {
        action: "load_candidates" | "analyze";
        selectedDate?: string;
      };
    };
    const snapshot =
      body.state.action === "load_candidates"
        ? {
            action: "load_candidates",
            phase: "selecting",
            candidates,
            selectedSchoolCodes: [],
            selectedDate: null,
            result: null,
            error: null,
          }
        : analyze(body.state.selectedDate ?? "");
    if (body.state.action === "analyze") analyzeRequests += 1;
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      headers: { "Cache-Control": "no-store" },
      body: sse(body, snapshot),
    });
  });
  return () => analyzeRequests;
}

async function selectComparison(page: Page) {
  await page.getByRole("button", { name: /한빛중학교/ }).click();
  await page.getByRole("button", { name: /새봄중학교/ }).click();
  const date = page.getByLabel("중식 날짜");
  await date.fill((await date.getAttribute("max")) ?? "");
}

test("user selects two schools and manually starts a comparison", async ({
  page,
}) => {
  const analyzeRequests = await installAgentMock(page, completedState);
  await page.goto("/analysis");

  await expect(page.getByRole("button", { name: /후보10학교/ })).toBeVisible();
  await selectComparison(page);
  await expect(page.getByLabel("분석 질문")).toHaveValue(
    /한빛중학교과 새봄중학교/,
  );
  expect(analyzeRequests()).toBe(0);

  await page.getByRole("button", { name: "전송" }).click();

  await expect(
    page.getByRole("heading", {
      name: "한빛중학교의 중식이 더 균형 잡혔습니다.",
    }),
  ).toBeVisible();
  await expect(page.getByText("87")).toBeVisible();
  expect(analyzeRequests()).toBe(1);
});

test("analysis stops with guidance when lunch data is unavailable", async ({
  page,
}) => {
  await installAgentMock(page, (selectedDate) => ({
    action: "analyze",
    phase: "error",
    candidates,
    selectedSchoolCodes: ["S1", "S2"],
    selectedDate,
    result: null,
    error: {
      code: "DATA_UNAVAILABLE",
      message: "새봄중학교의 중식이 없습니다. 다른 날짜를 선택해 주세요.",
      retryable: false,
    },
  }));
  await page.goto("/analysis");
  await selectComparison(page);

  await page.getByRole("button", { name: "전송" }).click();

  await expect(
    page.getByText("새봄중학교의 중식이 없습니다. 다른 날짜를 선택해 주세요."),
  ).toBeVisible();
  await expect(page.getByText("분석 완료")).toHaveCount(0);
});
