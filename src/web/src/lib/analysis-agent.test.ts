import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createAnalysisAgentClient,
  type AnalysisAgentClient,
} from "@/lib/analysis-agent";
import { INITIAL_ANALYSIS_STATE } from "@/lib/analysis-types";

const httpAgentMock = vi.hoisted(() => ({
  setMessages: vi.fn(),
  setState: vi.fn(),
  addMessage: vi.fn(),
  abortRun: vi.fn(),
  runAgent: vi.fn(),
}));

vi.mock("@ag-ui/client", () => ({
  HttpAgent: class {
    setMessages = httpAgentMock.setMessages;
    setState = httpAgentMock.setState;
    addMessage = httpAgentMock.addMessage;
    abortRun = httpAgentMock.abortRun;
    runAgent = httpAgentMock.runAgent;
  },
  randomUUID: () => "test-id",
}));

describe("AnalysisAgentClient", () => {
  let client: AnalysisAgentClient;

  beforeEach(() => {
    vi.clearAllMocks();
    client = createAnalysisAgentClient();
  });

  it("propagates an AG-UI run error after the event stream closes", async () => {
    httpAgentMock.runAgent.mockImplementation(
      async (
        _parameters: unknown,
        subscriber: {
          onRunErrorEvent: (params: {
            event: { message: string };
          }) => void;
        },
      ) => {
        subscriber.onRunErrorEvent({
          event: { message: "AI model request failed." },
        });
        return { result: null, newMessages: [] };
      },
    );

    await expect(
      client.analyze(
        {
          ...INITIAL_ANALYSIS_STATE,
          candidates: [],
          selectedSchoolCodes: ["A", "B"],
          selectedDate: "2026-07-26",
        },
        "분석해 주세요.",
        vi.fn(),
      ),
    ).rejects.toThrow("AI model request failed.");
  });

  it("aborts an active AG-UI run", () => {
    client.abort();

    expect(httpAgentMock.abortRun).toHaveBeenCalledOnce();
  });

  it("forwards streamed area progress and clears previous progress for a new run", async () => {
    const snapshot = {
      ...INITIAL_ANALYSIS_STATE,
      phase: "evaluating" as const,
      evaluationProgress: { nutrition: "completed" as const, health: "running" as const },
    };
    httpAgentMock.runAgent.mockImplementation(
      async (_parameters: unknown, subscriber: {
        onStateSnapshotEvent: (params: { event: { snapshot: typeof snapshot } }) => void;
      }) => {
        subscriber.onStateSnapshotEvent({ event: { snapshot } });
      },
    );
    const onState = vi.fn();
    await client.analyze(snapshot, "비교해 주세요.", onState);
    expect(httpAgentMock.setState).toHaveBeenCalledWith(
      expect.objectContaining({ evaluationProgress: {} }),
    );
    expect(onState).toHaveBeenCalledWith(snapshot);
    await client.loadCandidates(onState);
    expect(httpAgentMock.setState).toHaveBeenLastCalledWith(
      expect.objectContaining({ evaluationProgress: {} }),
    );
  });
});
