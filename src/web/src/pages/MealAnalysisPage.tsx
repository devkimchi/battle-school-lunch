import { useRef, useState, type FormEvent } from "react";
import { MessageCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

type ChatMessage = {
  id: number;
  content: string;
};

export default function MealAnalysisPage() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const nextMessageId = useRef(1);
  const canSend = input.trim().length > 0;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const content = input.trim();
    if (!content) return;

    setMessages((current) => [
      ...current,
      { id: nextMessageId.current++, content },
    ]);
    setInput("");
  };

  return (
    <div className="mx-auto flex min-h-[calc(100vh-57px)] max-w-4xl flex-col px-6 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold">학교 급식 분석</h1>
        <p className="mt-2 text-sm text-[var(--color-muted-foreground)]">
          급식 메뉴와 영양 정보에 대해 궁금한 내용을 입력해 보세요.
        </p>
      </header>

      <section
        aria-label="급식 분석 채팅"
        className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border bg-[var(--color-card)]"
      >
        <div
          aria-live="polite"
          className="flex min-h-72 flex-1 flex-col gap-4 overflow-y-auto p-6"
        >
          {messages.length === 0 ? (
            <div className="flex flex-1 flex-col items-center justify-center text-center">
              <MessageCircle
                aria-hidden="true"
                className="mb-4 size-10 text-[var(--color-muted-foreground)]"
              />
              <h2 className="font-semibold">분석할 내용을 입력해 주세요</h2>
              <p className="mt-2 max-w-md text-sm text-[var(--color-muted-foreground)]">
                현재는 작성한 메시지를 이 화면에서 확인할 수 있으며, 분석
                서버에는 전송되지 않습니다.
              </p>
            </div>
          ) : (
            messages.map((message) => (
              <div
                key={message.id}
                className="ml-auto max-w-[85%] rounded-2xl rounded-br-sm bg-[var(--color-primary)] px-4 py-3 text-sm text-[var(--color-primary-foreground)]"
              >
                {message.content}
              </div>
            ))
          )}
        </div>

        <form
          onSubmit={handleSubmit}
          className="flex items-end gap-3 border-t p-4"
        >
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
            placeholder="예: 이번 주 급식의 영양 균형을 알려줘"
            rows={2}
            className="min-h-11 flex-1 resize-none rounded-md border border-[var(--color-input)] bg-transparent px-3 py-2 text-sm outline-none placeholder:text-[var(--color-muted-foreground)] focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]"
          />
          <Button type="submit" disabled={!canSend}>
            전송
          </Button>
        </form>
      </section>
    </div>
  );
}
