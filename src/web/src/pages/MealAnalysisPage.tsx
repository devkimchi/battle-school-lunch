import {
  AlertCircle,
  Bot,
  LoaderCircle,
  RefreshCw,
  Send,
  Trophy,
} from "lucide-react";
import {
  useEffect,
  useCallback,
  useMemo,
  useRef,
  useState,
  type FormEvent,
} from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  allowedAnalysisDates,
  createAnalysisAgentClient,
  type AnalysisAgentClient,
} from "@/lib/analysis-agent";
import {
  INITIAL_ANALYSIS_STATE,
  type AnalysisPhase,
  type AnalysisResult,
  type AnalysisState,
  type EvaluationArea,
  type SchoolCandidate,
  type SchoolScore,
  type SpecialistEvaluation,
} from "@/lib/analysis-types";

const PHASE_LABELS: Partial<Record<AnalysisPhase, string>> = {
  loading_candidates: "무작위 학교 후보를 찾고 있어요.",
  loading_meals: "선택한 학교의 중식 데이터를 확인하고 있어요.",
  evaluating: "세 전문 에이전트가 동시에 평가하고 있어요.",
  judging: "AI Judge가 근거와 결과를 종합하고 있어요.",
};

const AREA_LABELS: Record<EvaluationArea, string> = {
  nutrition: "영양 균형",
  health: "건강성",
  menu_quality: "식재료 및 메뉴 품질",
};

function comparisonPrompt(
  selectedSchools: SchoolCandidate[],
  selectedDate: string,
): string {
  if (selectedSchools.length !== 2 || !selectedDate) return "";
  return `${selectedDate} 중식을 기준으로 ${selectedSchools[0].schoolName}과 ${selectedSchools[1].schoolName}의 급식을 비교 분석해 주세요.`;
}

function ErrorNotice({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-900"
    >
      <AlertCircle aria-hidden="true" className="mt-0.5 size-5 shrink-0" />
      <div className="flex-1">
        <p className="font-semibold">분석을 진행할 수 없습니다.</p>
        <p className="mt-1">{message}</p>
      </div>
      {onRetry ? (
        <Button type="button" variant="outline" size="sm" onClick={onRetry}>
          다시 시도
        </Button>
      ) : null}
    </div>
  );
}

function ScoreCard({
  score,
  winner,
}: {
  score: SchoolScore;
  winner: boolean;
}) {
  return (
    <Card className={winner ? "border-emerald-500 ring-1 ring-emerald-500" : ""}>
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardTitle>{score.school.schoolName}</CardTitle>
            <CardDescription>{score.school.eduOfficeName}</CardDescription>
          </div>
          {winner ? (
            <Trophy
              aria-label="더 높은 점수"
              className="size-6 text-emerald-600"
            />
          ) : null}
        </div>
        <p className="pt-2 text-4xl font-bold">
          {score.total}
          <span className="ml-1 text-base font-normal text-[var(--color-muted-foreground)]">
            / 100점
          </span>
        </p>
      </CardHeader>
      <CardContent>
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b text-[var(--color-muted-foreground)]">
              <th className="py-2 font-medium">평가 영역</th>
              <th className="py-2 text-center font-medium">평점</th>
              <th className="py-2 text-right font-medium">환산</th>
            </tr>
          </thead>
          <tbody>
            {score.areas.map((area) => (
              <tr key={area.area} className="border-b last:border-0">
                <th className="py-3 font-medium">{AREA_LABELS[area.area]}</th>
                <td className="py-3 text-center">{area.rating} / 5</td>
                <td className="py-3 text-right">
                  {area.weightedScore} / {area.weight}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

function MealCard({
  schoolName,
  dishes,
  calorie,
}: {
  schoolName: string;
  dishes: string[];
  calorie: string | null;
}) {
  return (
    <div className="rounded-lg bg-[var(--color-muted)] p-4">
      <h4 className="font-semibold">{schoolName} 중식</h4>
      <p className="mt-2 text-sm leading-6">{dishes.join(" · ")}</p>
      {calorie ? (
        <p className="mt-2 text-xs text-[var(--color-muted-foreground)]">
          열량 {calorie}
        </p>
      ) : null}
    </div>
  );
}

function EvaluationDetails({
  evaluation,
  schoolAName,
  schoolBName,
}: {
  evaluation: SpecialistEvaluation;
  schoolAName: string;
  schoolBName: string;
}) {
  return (
    <details className="rounded-lg border p-4">
      <summary className="cursor-pointer font-semibold">
        {AREA_LABELS[evaluation.area]} 평가 근거
      </summary>
      <p className="mt-3 text-sm">{evaluation.comparison}</p>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        {[
          [schoolAName, evaluation.schoolA],
          [schoolBName, evaluation.schoolB],
        ].map(([name, assessment]) => {
          if (typeof name !== "string" || typeof assessment === "string") {
            return null;
          }
          return (
            <div key={name}>
              <h4 className="text-sm font-semibold">{name}</h4>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                {assessment.evidence.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    </details>
  );
}

function AnalysisReport({ result }: { result: AnalysisResult }) {
  const isTie = result.judge.winner === "tie";
  const schoolAWins = result.judge.winner === "school_a";
  const schoolBWins = result.judge.winner === "school_b";

  return (
    <section aria-labelledby="analysis-result-title" className="space-y-6">
      <div>
        <p className="text-sm font-semibold text-emerald-700">분석 완료</p>
        <h2 id="analysis-result-title" className="mt-1 text-2xl font-bold">
          {result.judge.headline}
        </h2>
        <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">
          {result.analysisDate} 중식 ·{" "}
          {isTie ? "두 학교가 같은 총점을 받았습니다." : "총점이 높은 학교를 표시했습니다."}
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <ScoreCard score={result.schoolAScore} winner={schoolAWins} />
        <ScoreCard score={result.schoolBScore} winner={schoolBWins} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>비교한 급식 메뉴</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <MealCard
            schoolName={result.schoolAMeal.school.schoolName}
            dishes={result.schoolAMeal.dishes}
            calorie={result.schoolAMeal.calorie}
          />
          <MealCard
            schoolName={result.schoolBMeal.school.schoolName}
            dishes={result.schoolBMeal.dishes}
            calorie={result.schoolBMeal.calorie}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>AI Judge 종합 의견</CardTitle>
          <CardDescription>
            Judge는 전문 에이전트의 점수를 바꾸지 않고 근거와 일관성을
            검토합니다.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <ul className="list-disc space-y-2 pl-5 text-sm">
            {result.judge.rationale.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <div className="grid gap-4 md:grid-cols-2">
            {[
              [
                result.schoolAScore.school.schoolName,
                result.judge.schoolAImprovements,
              ],
              [
                result.schoolBScore.school.schoolName,
                result.judge.schoolBImprovements,
              ],
            ].map(([name, improvements]) => (
              <div key={name as string} className="rounded-lg border p-4">
                <h3 className="font-semibold">{name as string} 개선 제안</h3>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                  {(improvements as string[]).map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          {[...result.judge.qualityNotes, ...result.judge.limitations].length >
          0 ? (
            <div className="rounded-lg bg-amber-50 p-4 text-sm text-amber-950">
              <h3 className="font-semibold">분석 시 참고사항</h3>
              <ul className="mt-2 list-disc space-y-1 pl-5">
                {[...result.judge.qualityNotes, ...result.judge.limitations].map(
                  (item) => (
                    <li key={item}>{item}</li>
                  ),
                )}
              </ul>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <div className="space-y-3">
        {result.evaluations.map((evaluation) => (
          <EvaluationDetails
            key={evaluation.area}
            evaluation={evaluation}
            schoolAName={result.schoolAScore.school.schoolName}
            schoolBName={result.schoolBScore.school.schoolName}
          />
        ))}
      </div>
    </section>
  );
}

export default function MealAnalysisPage() {
  const client = useRef<AnalysisAgentClient | null>(null);
  if (!client.current) {
    client.current = createAnalysisAgentClient();
  }
  const agentClient = client.current;
  const [state, setState] = useState<AnalysisState>(INITIAL_ANALYSIS_STATE);
  const [selectedCodes, setSelectedCodes] = useState<string[]>([]);
  const [selectedDate, setSelectedDate] = useState("");
  const [input, setInput] = useState("");
  const [submittedPrompt, setSubmittedPrompt] = useState("");
  const [transportError, setTransportError] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const dateRange = useMemo(() => allowedAnalysisDates(), []);
  const selectedSchools = useMemo(
    () =>
      state.candidates.filter((school) =>
        selectedCodes.includes(school.schoolCode),
      ),
    [selectedCodes, state.candidates],
  );
  const generatedPrompt = comparisonPrompt(selectedSchools, selectedDate);

  const loadCandidates = useCallback(async () => {
    setTransportError("");
    setIsRunning(true);
    try {
      await agentClient.loadCandidates(setState);
    } catch {
      setTransportError("학교 후보를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      setIsRunning(false);
    }
  }, [agentClient]);

  useEffect(() => {
    void loadCandidates();
    return () => agentClient.abort();
  }, [agentClient, loadCandidates]);

  useEffect(() => {
    setInput(generatedPrompt);
  }, [generatedPrompt]);

  const toggleSchool = (schoolCode: string) => {
    setSelectedCodes((current) => {
      if (current.includes(schoolCode)) {
        return current.filter((code) => code !== schoolCode);
      }
      if (current.length >= 2) return current;
      return [...current, schoolCode];
    });
    setSubmittedPrompt("");
    setState((current) => ({ ...current, result: null, error: null }));
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const prompt = input.trim();
    if (selectedCodes.length !== 2 || !selectedDate || !prompt || isRunning) {
      return;
    }

    const requestState: AnalysisState = {
      ...state,
      action: "analyze",
      selectedSchoolCodes: selectedCodes,
      selectedDate,
      result: null,
      error: null,
    };
    setSubmittedPrompt(prompt);
    setTransportError("");
    setIsRunning(true);
    try {
      await agentClient.analyze(requestState, prompt, setState);
    } catch {
      setTransportError("분석 서버와 연결하지 못했습니다. 다시 시도해 주세요.");
    } finally {
      setIsRunning(false);
    }
  };

  const currentError = state.error?.message ?? transportError;
  const canSend =
    selectedCodes.length === 2 &&
    Boolean(selectedDate) &&
    input.trim().length > 0 &&
    !isRunning;

  return (
    <div className="mx-auto max-w-5xl space-y-8 px-6 py-8">
      <header>
        <p className="text-sm font-semibold text-emerald-700">
          Concurrent Multi-Agent
        </p>
        <h1 className="mt-1 text-3xl font-bold">학교 급식 분석</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--color-muted-foreground)]">
          무작위 학교 두 곳의 같은 날 중식을 영양 균형 45%, 건강성 30%,
          메뉴 품질 25% 기준으로 비교합니다.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>1. 비교할 학교 두 곳을 선택하세요</CardTitle>
          <CardDescription>
            MCP 서버에서 무작위로 가져온 후보 10곳입니다. 선택은 최대 두
            곳까지 가능합니다.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {state.phase === "loading_candidates" ||
          (isRunning && state.candidates.length === 0) ? (
            <div
              role="status"
              className="flex items-center gap-2 py-8 text-sm text-[var(--color-muted-foreground)]"
            >
              <LoaderCircle aria-hidden="true" className="size-5 animate-spin" />
              학교 후보를 불러오고 있어요.
            </div>
          ) : null}
          {currentError && state.candidates.length === 0 ? (
            <ErrorNotice message={currentError} onRetry={loadCandidates} />
          ) : null}
          {state.candidates.length > 0 ? (
            <>
              <div className="grid gap-3 sm:grid-cols-2">
                {state.candidates.map((school) => {
                  const selected = selectedCodes.includes(school.schoolCode);
                  const disabled = !selected && selectedCodes.length >= 2;
                  return (
                    <button
                      key={school.schoolCode}
                      type="button"
                      aria-pressed={selected}
                      disabled={disabled}
                      onClick={() => toggleSchool(school.schoolCode)}
                      className={`rounded-lg border p-4 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-45 ${
                        selected
                          ? "border-emerald-600 bg-emerald-50 ring-1 ring-emerald-600"
                          : "hover:bg-[var(--color-muted)]"
                      }`}
                    >
                      <span className="block font-semibold">
                        {school.schoolName}
                      </span>
                      <span className="mt-1 block text-xs text-[var(--color-muted-foreground)]">
                        {school.eduOfficeName}
                        {school.locationName ? ` · ${school.locationName}` : ""}
                      </span>
                    </button>
                  );
                })}
              </div>
              <div className="mt-4 flex items-center justify-between">
                <p aria-live="polite" className="text-sm">
                  {selectedCodes.length} / 2개 학교 선택
                </p>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  disabled={isRunning}
                  onClick={() => {
                    setSelectedCodes([]);
                    setSelectedDate("");
                    setSubmittedPrompt("");
                    void loadCandidates();
                  }}
                >
                  <RefreshCw aria-hidden="true" className="size-4" />
                  후보 새로고침
                </Button>
              </div>
            </>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>2. 분석 날짜를 선택하세요</CardTitle>
          <CardDescription>
            한국 시간 기준 지난달 1일부터 오늘까지 선택할 수 있습니다.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <label htmlFor="analysis-date" className="mb-2 block text-sm font-medium">
            중식 날짜
          </label>
          <Input
            id="analysis-date"
            type="date"
            min={dateRange.min}
            max={dateRange.max}
            value={selectedDate}
            disabled={selectedCodes.length !== 2 || isRunning}
            onChange={(event) => {
              setSelectedDate(event.target.value);
              setSubmittedPrompt("");
              setState((current) => ({
                ...current,
                result: null,
                error: null,
              }));
            }}
            className="max-w-xs"
          />
          <p className="mt-2 text-xs text-[var(--color-muted-foreground)]">
            선택 가능: {dateRange.min} ~ {dateRange.max}
          </p>
        </CardContent>
      </Card>

      <section
        aria-label="급식 분석 채팅"
        className="overflow-hidden rounded-xl border bg-[var(--color-card)]"
      >
        <div aria-live="polite" className="min-h-40 space-y-4 p-6">
          {!submittedPrompt && !isRunning && !state.result ? (
            <div className="flex flex-col items-center justify-center py-5 text-center">
              <Bot
                aria-hidden="true"
                className="mb-3 size-9 text-[var(--color-muted-foreground)]"
              />
              <h2 className="font-semibold">선택을 마치고 분석을 요청하세요</h2>
              <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">
                학교와 날짜를 선택하면 요청 문장이 자동으로 입력됩니다.
              </p>
            </div>
          ) : null}
          {submittedPrompt ? (
            <div className="ml-auto max-w-[85%] rounded-2xl rounded-br-sm bg-[var(--color-primary)] px-4 py-3 text-sm text-[var(--color-primary-foreground)]">
              {submittedPrompt}
            </div>
          ) : null}
          {isRunning && PHASE_LABELS[state.phase] ? (
            <div role="status" className="flex items-center gap-3 text-sm">
              <LoaderCircle aria-hidden="true" className="size-5 animate-spin" />
              {PHASE_LABELS[state.phase]}
            </div>
          ) : null}
          {currentError && state.candidates.length > 0 ? (
            <ErrorNotice message={currentError} />
          ) : null}
        </div>

        <form onSubmit={handleSubmit} className="flex items-end gap-3 border-t p-4">
          <textarea
            aria-label="분석 질문"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (
                event.key === "Enter" &&
                (event.ctrlKey || event.metaKey) &&
                !event.nativeEvent.isComposing
              ) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
            placeholder="학교 두 곳과 날짜를 먼저 선택해 주세요."
            rows={2}
            disabled={isRunning}
            className="min-h-11 flex-1 resize-none rounded-md border border-[var(--color-input)] bg-transparent px-3 py-2 text-sm outline-none placeholder:text-[var(--color-muted-foreground)] focus-visible:ring-2 focus-visible:ring-[var(--color-ring)] disabled:opacity-50"
          />
          <Button type="submit" disabled={!canSend}>
            <Send aria-hidden="true" className="size-4" />
            전송
          </Button>
        </form>
      </section>

      {state.result ? <AnalysisReport result={state.result} /> : null}
    </div>
  );
}
