export type AnalysisPhase =
  | "idle"
  | "loading_candidates"
  | "selecting"
  | "loading_meals"
  | "evaluating"
  | "judging"
  | "completed"
  | "error";

export type EvaluationArea = "nutrition" | "health" | "menu_quality";

export interface SchoolCandidate {
  schoolCode: string;
  eduOfficeCode: string;
  schoolName: string;
  eduOfficeName: string;
  locationName: string | null;
}

export interface MealData {
  school: SchoolCandidate;
  date: string;
  dishes: string[];
  calorie: string | null;
  nutrition: string[];
  origin: string[];
  servings: number | null;
}

export interface SchoolAssessment {
  score: number;
  evidence: string[];
  strengths: string[];
  risks: string[];
  improvements: string[];
}

export interface SpecialistEvaluation {
  area: EvaluationArea;
  schoolA: SchoolAssessment;
  schoolB: SchoolAssessment;
  comparison: string;
  limitations: string[];
}

export interface WeightedAreaScore {
  area: EvaluationArea;
  rating: number;
  weight: number;
  weightedScore: number;
}

export interface SchoolScore {
  school: SchoolCandidate;
  areas: WeightedAreaScore[];
  total: number;
}

export interface JudgeReport {
  winner: "school_a" | "school_b" | "tie";
  headline: string;
  rationale: string[];
  schoolAImprovements: string[];
  schoolBImprovements: string[];
  qualityNotes: string[];
  limitations: string[];
}

export interface AnalysisResult {
  analysisDate: string;
  schoolAMeal: MealData;
  schoolBMeal: MealData;
  evaluations: SpecialistEvaluation[];
  schoolAScore: SchoolScore;
  schoolBScore: SchoolScore;
  judge: JudgeReport;
}

export interface AgentError {
  code: string;
  message: string;
  retryable: boolean;
}

export interface AnalysisState {
  action: "load_candidates" | "analyze" | null;
  phase: AnalysisPhase;
  candidates: SchoolCandidate[];
  selectedSchoolCodes: string[];
  selectedDate: string | null;
  result: AnalysisResult | null;
  error: AgentError | null;
}

export const INITIAL_ANALYSIS_STATE: AnalysisState = {
  action: null,
  phase: "idle",
  candidates: [],
  selectedSchoolCodes: [],
  selectedDate: null,
  result: null,
  error: null,
};
