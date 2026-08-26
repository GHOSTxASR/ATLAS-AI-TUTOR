import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";

interface MarkdownContentProps {
  content: string;
  /** Assistant replies get full markdown; user text stays literal. */
  markdown?: boolean;
}

/**
 * Renders AI-authored markdown: chat replies and generated study notes.
 *
 * Every tutor and note prompt asks the model for headings, bullet lists,
 * tables and LaTeX. Those were dumped into a `whitespace-pre-wrap` div, so
 * students read raw `###` and `$$` markers instead of formatted material.
 */
export function MarkdownContent({ content, markdown = true }: MarkdownContentProps) {
  if (!markdown) {
    return <div className="whitespace-pre-wrap font-sans">{content}</div>;
  }

  return (
    <div className="markdown-body font-sans">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          // Open any model-supplied link safely in a new tab.
          a: ({ node: _node, ...props }) => (
            <a {...props} target="_blank" rel="noopener noreferrer nofollow" />
          ),
          // Tables can be wider than the bubble; give them their own scroller
          // instead of forcing the page to scroll sideways.
          table: ({ node: _node, ...props }) => (
            <div className="overflow-x-auto">
              <table {...props} />
            </div>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
