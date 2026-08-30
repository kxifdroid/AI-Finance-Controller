"use client";

import { useState, useRef, useEffect } from "react";
import { 
  Send, 
  Sparkles, 
  Bot, 
  User, 
  Wrench, 
  HelpCircle, 
  RotateCcw,
  Brain,
  CheckCircle2
} from "lucide-react";
import { ChatMessage, ToolCall } from "@/types";
import { postFinanceChatMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import Markdown from "react-markdown";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/accordion";

const SAMPLE_QUESTIONS = [
  "What is my total reconciliation exposure?",
  "Show high risk exceptions and discrepancies",
  "Explain MDR fee variance policy",
  "What is our 7-day cash trajectory?",
  "How many transactions are unresolved?",
];

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "Hello! I am your **AI Finance Operations Controller Copilot**.\n\nI have read-only, real-time access to the active reconciliation ledger and can answer queries about transaction matches, exception exposures, largest discrepancies, or cash flows with strict mathematical grounding. How can I assist your financial audit today?",
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const handleSend = async (userText: string) => {
    if (!userText.trim() || loading) return;

    const userMsg: ChatMessage = {
      id: `u_${Date.now()}`,
      role: "user",
      content: userText,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    const thinkingId = `thinking_${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      userMsg,
      {
        id: thinkingId,
        role: "assistant",
        content: "",
        isThinking: true,
        thought_process: ["Analyzing your financial query…", "Querying ledger database tools with zero hallucination…"],
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      },
    ]);
    setInput("");
    setLoading(true);

    try {
      const res = await postFinanceChatMessage(userText);
      const assistantMsg: ChatMessage = {
        id: `a_${Date.now()}`,
        role: "assistant",
        content: res.answer,
        isThinking: false,
        thought_process: res.thought_process,
        tools_used: res.tools_used,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) =>
        prev
          .filter((m) => m.id !== thinkingId)
          .concat(assistantMsg)
      );
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: `err_${Date.now()}`,
        role: "assistant",
        content: `Error querying finance ledger: ${err.message || "Failed to fetch data."}`,
        isThinking: false,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) =>
        prev
          .filter((m) => m.id !== thinkingId)
          .concat(errorMsg)
      );
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setMessages([
      {
        id: "welcome",
        role: "assistant",
        content: "Ledger conversation reset. Ask any operational question regarding reconciliations or exceptions.",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      },
    ]);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8.5rem)] space-y-4">
      
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border pb-3 shrink-0">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-ai-light" />
            Finance Operations Copilot
          </h1>
          <p className="text-xs text-gray-400">
            Real-time tool-grounded inquiries over financial ledger state with zero hallucinated figures.
          </p>
        </div>
        <button
          onClick={handleClear}
          className="flex items-center gap-1.5 rounded-lg border border-border bg-surface-secondary px-3 py-1 text-xs text-gray-400 hover:text-white hover:bg-surface-elevated transition-colors focus-ring"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          Reset Chat
        </button>
      </div>

      {/* Suggested Prompt Chips */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 shrink-0">
        <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider shrink-0 flex items-center gap-1">
          <HelpCircle className="h-3.5 w-3.5 text-ai-light" /> Prompts:
        </span>
        {SAMPLE_QUESTIONS.map((q) => (
          <button
            key={q}
            onClick={() => handleSend(q)}
            className="rounded-full border border-border bg-surface-secondary px-3 py-1 text-xs text-gray-300 hover:border-border-strong hover:bg-surface-elevated hover:text-white transition-all whitespace-nowrap focus-ring"
          >
            {q}
          </button>
        ))}
      </div>

      {/* Message Thread */}
      <div className="flex-1 overflow-y-auto rounded-xl border border-border bg-surface-secondary p-4 space-y-4 shadow-sm">
        {messages.map((msg) => {
          const isUser = msg.role === "user";

          return (
            <div
              key={msg.id}
              className={cn("flex gap-3 max-w-3xl", isUser ? "ml-auto justify-end" : "mr-auto")}
            >
              {!isUser && (
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-ai/15 text-ai-light border border-ai/30">
                  <Bot className="h-4 w-4" />
                </div>
              )}

              <div className="space-y-2">
                {!isUser && msg.isThinking && (
                  <div className="flex items-center gap-2.5 rounded-2xl rounded-bl-none bg-surface border border-border px-4 py-3 text-xs text-gray-400 shadow-sm">
                    <div className="relative flex h-5 w-5 items-center justify-center">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-ai opacity-30" />
                      <Brain className="relative h-4 w-4 text-ai-light animate-pulse" />
                    </div>
                    <span>AI Copilot querying ledger database state…</span>
                  </div>
                )}

                {!isUser && !msg.isThinking && msg.thought_process && msg.thought_process.length > 0 && (
                  <Accordion type="single" collapsible className="w-full max-w-2xl">
                    <AccordionItem value={`thought-${msg.id}`} className="border border-border rounded-lg bg-surface overflow-hidden">
                      <AccordionTrigger className="px-3 py-2 text-[11px] font-semibold text-ai-light hover:no-underline">
                        <span className="flex items-center gap-1.5">
                          <Brain className="h-3.5 w-3.5" />
                          Tool Execution &amp; Thought Trace ({msg.tools_used?.length ?? 0} tools executed)
                        </span>
                      </AccordionTrigger>
                      <AccordionContent className="px-3 pb-3 pt-1">
                        <ol className="space-y-1.5">
                          {msg.thought_process.map((step, idx) => (
                            <li key={idx} className="flex gap-2 text-[11px] text-gray-400 leading-relaxed">
                              <span className="font-mono text-ai-light shrink-0">{idx + 1}.</span>
                              <span>{step}</span>
                            </li>
                          ))}
                        </ol>
                      </AccordionContent>
                    </AccordionItem>
                  </Accordion>
                )}

                {!msg.isThinking && (
                  <div
                    className={cn(
                      "rounded-2xl px-4 py-3 text-xs leading-relaxed shadow-sm",
                      isUser
                        ? "bg-primary text-white rounded-br-none font-medium"
                        : "bg-surface border border-border text-gray-200 rounded-bl-none"
                    )}
                  >
                    {isUser ? (
                      <div className="whitespace-pre-wrap">{msg.content}</div>
                    ) : (
                      <div className="prose prose-invert prose-xs max-w-none [&_code]:bg-surface-elevated [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-ai-light [&_code]:font-mono">
                        <Markdown>{msg.content}</Markdown>
                      </div>
                    )}
                  </div>
                )}

                {/* Tool Invocation Badges */}
                {msg.tools_used && msg.tools_used.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-0.5">
                    {msg.tools_used.map((tool, idx) => (
                      <span
                        key={idx}
                        className="inline-flex items-center gap-1 rounded-md bg-ai/10 border border-ai/25 px-2 py-0.5 text-[10px] font-mono text-ai-light"
                      >
                        <Wrench className="h-3 w-3" />
                        <span>Tool: {tool.tool_name}()</span>
                      </span>
                    ))}
                  </div>
                )}

                <div className={cn("text-[10px] text-gray-500 px-1 font-mono", isUser ? "text-right" : "text-left")}>
                  {msg.timestamp}
                </div>
              </div>

              {isUser && (
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-surface-elevated border border-border text-gray-300">
                  <User className="h-4 w-4" />
                </div>
              )}
            </div>
          );
        })}

        {loading && (
          <div className="flex gap-3 max-w-3xl mr-auto">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-ai/15 text-ai-light border border-ai/30">
              <Bot className="h-4 w-4 animate-pulse" />
            </div>
            <div className="rounded-2xl rounded-bl-none bg-surface border border-border p-3 text-xs text-gray-400 flex items-center gap-2">
              <div className="h-3 w-3 animate-spin rounded-full border-2 border-ai-light border-t-transparent" />
              <span>Executing deterministic database queries and synthesizing response…</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Bar */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend(input);
        }}
        className="flex items-center gap-2 shrink-0 bg-surface-secondary p-2 rounded-xl border border-border shadow-sm"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question about reconciled totals, exceptions, or specific transactions..."
          className="flex-1 rounded-lg border border-border bg-surface px-4 py-2 text-xs text-white placeholder-gray-500 focus-ring"
        />
        <button
          type="submit"
          disabled={!input.trim() || loading}
          className="flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-xs font-bold text-white hover:bg-primary-hover disabled:opacity-50 transition-colors shadow-sm focus-ring"
        >
          <Send className="h-3.5 w-3.5" />
          Send Query
        </button>
      </form>

    </div>
  );
}
