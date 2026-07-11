import { Copy } from "lucide-react";
import ReactMarkdown from "react-markdown";

import { API_BASE_URL } from "../api/client";

type Props = {
  markdown: string;
};

export function ReportPanel({ markdown }: Props) {
  if (!markdown) {
    return <div className="empty-state">生成报告后，这里会展示可复制的 Markdown 分析报告。</div>;
  }

  return (
    <div className="report-panel">
      <button className="copy-button" onClick={() => navigator.clipboard.writeText(markdown)}>
        <Copy size={15} />
        复制 Markdown
      </button>
      <article className="markdown-body">
        <ReactMarkdown
          components={{
            a: ({ href, children }) => (
              <a href={normalizeAssetUrl(href)} target="_blank" rel="noreferrer">
                {children}
              </a>
            ),
            img: ({ src, alt }) => <img className="report-image" src={normalizeAssetUrl(src)} alt={alt ?? ""} />,
          }}
        >
          {markdown}
        </ReactMarkdown>
      </article>
    </div>
  );
}

function normalizeAssetUrl(url: string | undefined) {
  if (!url) return "";
  if (url.startsWith("/artifacts/")) return `${API_BASE_URL}${url}`;
  return url;
}
