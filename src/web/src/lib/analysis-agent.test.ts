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
          event: { message: "Foundry model request failed." },
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
    ).rejects.toThrow("Foundry model request failed.");
  });
});
