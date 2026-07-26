import { HttpAgent, randomUUID } from "@ag-ui/client";
import type { AnalysisState } from "@/lib/analysis-types";

export interface AnalysisAgentClient {
  loadCandidates(onState: (state: AnalysisState) => void): Promise<void>;
  analyze(
    state: AnalysisState,
    prompt: string,
    onState: (state: AnalysisState) => void,
  ): Promise<void>;
  abort(): void;
}

class HttpAnalysisAgentClient implements AnalysisAgentClient {
  private readonly agent = new HttpAgent({
    url: "/agent",
    threadId: randomUUID(),
  });

  async loadCandidates(
    onState: (state: AnalysisState) => void,
  ): Promise<void> {
    this.agent.setMessages([]);
    await this.run(
      {
        action: "load_candidates",
        phase: "idle",
        candidates: [],
        selectedSchoolCodes: [],
        selectedDate: null,
        result: null,
        error: null,
      },
      onState,
    );
  }

  async analyze(
    state: AnalysisState,
    prompt: string,
    onState: (state: AnalysisState) => void,
  ): Promise<void> {
    this.agent.addMessage({
      id: randomUUID(),
      role: "user",
      content: prompt,
    });
    await this.run(
      {
        ...state,
        action: "analyze",
        phase: "selecting",
        result: null,
        error: null,
      },
      onState,
    );
  }

  abort(): void {
    this.agent.abortRun();
  }

  private async run(
    state: AnalysisState,
    onState: (state: AnalysisState) => void,
  ): Promise<void> {
    this.agent.setState(state);
    let runError: string | null = null;
    await this.agent.runAgent({}, {
      onStateSnapshotEvent: ({ event }) => {
        onState(event.snapshot as AnalysisState);
      },
      onRunErrorEvent: ({ event }) => {
        runError = event.message;
      },
    });
    if (runError) {
      throw new Error(runError);
    }
  }
}

export function createAnalysisAgentClient(): AnalysisAgentClient {
  return new HttpAnalysisAgentClient();
}

function kstDateParts(now: Date): { year: number; month: number; day: number } {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  const value = (type: Intl.DateTimeFormatPartTypes) =>
    Number(parts.find((part) => part.type === type)?.value);
  return { year: value("year"), month: value("month"), day: value("day") };
}

function isoDate(year: number, month: number, day: number): string {
  return [year, month, day]
    .map((value, index) =>
      index === 0 ? String(value) : String(value).padStart(2, "0"),
    )
    .join("-");
}

export function allowedAnalysisDates(now = new Date()): {
  min: string;
  max: string;
} {
  const { year, month, day } = kstDateParts(now);
  const previousMonth = month === 1 ? 12 : month - 1;
  const previousYear = month === 1 ? year - 1 : year;
  return {
    min: isoDate(previousYear, previousMonth, 1),
    max: isoDate(year, month, day),
  };
}
