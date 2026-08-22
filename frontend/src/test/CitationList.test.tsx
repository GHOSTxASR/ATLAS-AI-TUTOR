import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CitationList } from "../components/chat/CitationList";
import { Citation } from "../types";

function citation(overrides: Partial<Citation> = {}): Citation {
  return {
    index: 1,
    source_type: "document",
    source_id: "doc-1",
    filename: "thermodynamics.pdf",
    page_number: 12,
    char_offset_start: 0,
    char_offset_end: 200,
    snippet: "Entropy of an isolated system never decreases.",
    score: 0.91,
    ...overrides,
  };
}

/**
 * Regression: the backend has always sent citations, but the frontend typed
 * them with fields the API never returns (`source_label`, `doc_id`) and never
 * rendered them, so grounded answers looked identical to ungrounded ones.
 */
describe("CitationList", () => {
  it("renders nothing when there are no citations", () => {
    const { container } = render(<CitationList citations={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("summarises the source count without expanding by default", () => {
    render(<CitationList citations={[citation(), citation({ index: 2 })]} />);

    expect(screen.getByRole("button", { name: /2 sources/i })).toBeInTheDocument();
    expect(screen.queryByText(/Entropy of an isolated system/)).not.toBeInTheDocument();
  });

  it("uses the singular form for one source", () => {
    render(<CitationList citations={[citation()]} />);
    expect(screen.getByRole("button", { name: /1 source$/i })).toBeInTheDocument();
  });

  it("reveals filename, page and snippet when expanded", async () => {
    const user = userEvent.setup();
    render(<CitationList citations={[citation()]} />);

    await user.click(screen.getByRole("button", { name: /1 source/i }));

    expect(screen.getByText("thermodynamics.pdf, p.12")).toBeInTheDocument();
    expect(screen.getByText(/Entropy of an isolated system/)).toBeInTheDocument();
    expect(screen.getByText("[1]")).toBeInTheDocument();
  });

  it("labels non-document sources by their kind", async () => {
    const user = userEvent.setup();
    render(
      <CitationList
        citations={[
          citation({ source_type: "note", filename: "Carnot cycle", page_number: null }),
        ]}
      />
    );

    await user.click(screen.getByRole("button", { name: /1 source/i }));
    expect(screen.getByText("Note: Carnot cycle")).toBeInTheDocument();
  });

  it("omits the page suffix when the source has no page number", async () => {
    const user = userEvent.setup();
    render(<CitationList citations={[citation({ page_number: null })]} />);

    await user.click(screen.getByRole("button", { name: /1 source/i }));
    expect(screen.getByText("thermodynamics.pdf")).toBeInTheDocument();
  });
});
