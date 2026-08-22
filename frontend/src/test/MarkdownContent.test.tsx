import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MarkdownContent } from "../components/common/MarkdownContent";

/**
 * Regression: assistant replies were rendered inside a `whitespace-pre-wrap`
 * div, so students saw literal `###`, `**` and `$$` markers instead of the
 * formatting every tutor prompt asks the model to produce.
 */
describe("MarkdownContent", () => {
  it("renders markdown headings as real heading elements", () => {
    render(<MarkdownContent content={"### Core Concept\n\nSome explanation."} />);

    const heading = screen.getByRole("heading", { name: "Core Concept" });
    expect(heading).toBeInTheDocument();
    expect(screen.queryByText(/###/)).not.toBeInTheDocument();
  });

  it("renders bullet lists as list items", () => {
    render(<MarkdownContent content={"- First point\n- Second point"} />);

    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent("First point");
  });

  it("renders bold text without leaving asterisks behind", () => {
    const { container } = render(<MarkdownContent content="A **key** idea" />);

    expect(container.querySelector("strong")).toHaveTextContent("key");
    expect(container.textContent).not.toContain("**");
  });

  it("renders GFM tables", () => {
    const table = ["| Term | Meaning |", "| --- | --- |", "| Entropy | Disorder |"].join("\n");
    render(<MarkdownContent content={table} />);

    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Entropy" })).toBeInTheDocument();
  });

  it("renders inline LaTeX through KaTeX", () => {
    const { container } = render(<MarkdownContent content={"Energy is $E = mc^2$"} />);

    expect(container.querySelector(".katex")).toBeInTheDocument();
    expect(container.textContent).not.toContain("$E = mc^2$");
  });

  it("renders code blocks", () => {
    const { container } = render(
      <MarkdownContent content={"```python\nprint('hi')\n```"} />
    );

    expect(container.querySelector("pre code")).toBeInTheDocument();
  });

  it("opens model-supplied links in a new tab with safe rel attributes", () => {
    render(<MarkdownContent content="[docs](https://example.com)" />);

    const link = screen.getByRole("link", { name: "docs" });
    expect(link).toHaveAttribute("target", "_blank");
    expect(link.getAttribute("rel")).toContain("noopener");
  });

  it("leaves user text literal so their typed markup is not reinterpreted", () => {
    render(<MarkdownContent content="What does **this** mean?" markdown={false} />);

    expect(screen.getByText("What does **this** mean?")).toBeInTheDocument();
  });
});
