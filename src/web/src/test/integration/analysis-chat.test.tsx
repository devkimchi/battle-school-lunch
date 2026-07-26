import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "@/App";
import { renderWithProviders } from "@/test/test-utils";

describe("Meal analysis chat", () => {
  it("switches between the lookup and analysis tabs", async () => {
    const user = userEvent.setup();
    renderWithProviders(<App />, { initialEntries: ["/"] });

    const lookupTab = screen.getByRole("link", {
      name: "학교 급식 조회",
    });
    const analysisTab = screen.getByRole("link", {
      name: "학교 급식 분석",
    });

    expect(lookupTab).toHaveAttribute("aria-current", "page");
    expect(analysisTab).not.toHaveAttribute("aria-current");

    await user.click(analysisTab);

    expect(
      screen.getByRole("heading", { name: "학교 급식 분석" }),
    ).toBeInTheDocument();
    expect(analysisTab).toHaveAttribute("aria-current", "page");
    expect(lookupTab).not.toHaveAttribute("aria-current");
  });

  it("adds non-empty messages to the local conversation", async () => {
    const user = userEvent.setup();
    renderWithProviders(<App />, { initialEntries: ["/analysis"] });

    const input = screen.getByRole("textbox", { name: "분석 질문" });
    const sendButton = screen.getByRole("button", { name: "전송" });

    expect(
      screen.getByText("분석할 내용을 입력해 주세요"),
    ).toBeInTheDocument();
    expect(sendButton).toBeDisabled();

    await user.type(input, "  이번 주 급식의 영양 균형을 알려줘  ");
    await user.click(sendButton);

    expect(
      screen.getByText("이번 주 급식의 영양 균형을 알려줘"),
    ).toBeInTheDocument();
    expect(input).toHaveValue("");
    expect(sendButton).toBeDisabled();
  });
});
