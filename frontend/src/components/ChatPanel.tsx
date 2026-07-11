import { Bot, Lightbulb, Send, User } from "lucide-react";
import { FormEvent, useState } from "react";

import type { AgentTraceStep, ChatMessage } from "../types/api";
import { AgentThinking } from "./AgentThinking";

type Props = {
  disabled: boolean;
  loading: boolean;
  thinkingVisible: boolean;
  thinkingSteps?: AgentTraceStep[];
  messages: ChatMessage[];
  onSend: (message: string) => void;
  onGenerateReport: () => void;
};

const QUICK_MESSAGES = [
  "销售额最高的三个产品是什么",
  "查看月度销售趋势",
  "哪个地区下降最多",
];

export function ChatPanel({ disabled, loading, thinkingVisible, thinkingSteps, messages, onSend, onGenerateReport }: Props) {
  const [draft, setDraft] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    const message = draft.trim();
    if (!message || disabled || loading) return;
    setDraft("");
    onSend(message);
  }

  return (
    <div className="chat-panel">
      <div className="quick-actions">
        {QUICK_MESSAGES.map((message) => (
          <button className="quick-chip" key={message} onClick={() => onSend(message)} disabled={disabled || loading}>
            {message}
          </button>
        ))}
        <button className="quick-chip" onClick={onGenerateReport} disabled={disabled || loading}>
          生成报告
        </button>
      </div>

      <div className="message-list">
        {messages.length === 0 && !thinkingVisible && <EmptyChatState />}
        {messages.map((message) => (
          <div className={`message ${message.role}`} key={message.id}>
            <div className="avatar">{message.role === "user" ? <User size={15} /> : <Bot size={15} />}</div>
            <div className="message-body">
              <p>{message.content}</p>
              {message.response?.warnings.map((warning) => (
                <div className="alert warning" key={warning}>
                  {warning}
                </div>
              ))}
              {message.response?.errors.map((error) => (
                <div className="alert error" key={error}>
                  {error}
                </div>
              ))}
            </div>
          </div>
        ))}
        {thinkingVisible && <AgentThinking active steps={thinkingSteps} />}
      </div>

      <form className="chat-form" onSubmit={submit}>
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          disabled={disabled || loading}
          placeholder={disabled ? "请先上传数据集" : "问一个业务问题，例如：查看月度销售趋势"}
        />
        <button className="send-btn" disabled={disabled || loading || !draft.trim()} type="submit" aria-label="发送问题">
          <Send size={16} />
        </button>
      </form>
    </div>
  );
}

function EmptyChatState() {
  return (
    <div className="empty-state chat-empty-state">
      <div className="step-flow">
        <div className="flow-step">
          <div className="flow-icon">📁</div>
          <div className="flow-text">上传数据</div>
        </div>
        <div className="flow-arrow">→</div>
        <div className="flow-step">
          <div className="flow-icon">💬</div>
          <div className="flow-text">提问分析</div>
        </div>
        <div className="flow-arrow">→</div>
        <div className="flow-step">
          <div className="flow-icon">📊</div>
          <div className="flow-text">获取洞察</div>
        </div>
      </div>
      <h3>开始你的数据分析</h3>
      <p>从左侧上传 CSV 或 XLSX 文件，然后用自然语言提问，DataAgent 会生成结论、图表和报告。</p>
      <div className="empty-hint">
        <Lightbulb size={15} />
        <span>支持：销售趋势、异常检测、数据对比、自动报告</span>
      </div>
    </div>
  );
}
