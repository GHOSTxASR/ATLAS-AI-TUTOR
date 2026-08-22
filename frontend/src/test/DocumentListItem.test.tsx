import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DocumentListItem } from "../components/documents/DocumentListItem";
import { Document } from "../types";

describe("DocumentListItem Component Tests", () => {
  const mockDoc: Document = {
    id: "doc-123",
    profile_id: "prof-1",
    filename: "Calculus_Notes.pdf",
    file_type: "pdf",
    status: "extracted",
    is_syllabus: true,
    page_count: 5,
    chunk_count: 10,
    word_count: 2400,
    roadmap_node_id: null,
    uploaded_at: "2026-08-19T10:00:00Z",
    indexed_at: "2026-08-19T10:05:00Z",
    error_message: null,
  };

  it("renders document name, type, syllabus tag, and status badge", () => {
    render(
      <DocumentListItem
        document={mockDoc}
        onDelete={vi.fn()}
        onReprocess={vi.fn()}
        isDeleting={false}
        isReprocessing={false}
      />
    );

    expect(screen.getByText("Calculus_Notes.pdf")).toBeInTheDocument();
    expect(screen.getByText("Syllabus")).toBeInTheDocument();
    expect(screen.getByText("Extracted")).toBeInTheDocument();
    expect(screen.getByText("5 pages")).toBeInTheDocument();
    expect(screen.getByText("2,400 words")).toBeInTheDocument();
  });

  it("triggers onDelete when delete button is clicked", () => {
    const onDeleteMock = vi.fn();
    render(
      <DocumentListItem
        document={mockDoc}
        onDelete={onDeleteMock}
        onReprocess={vi.fn()}
        isDeleting={false}
        isReprocessing={false}
      />
    );

    const deleteBtn = screen.getByRole("button", { name: /delete document/i });
    fireEvent.click(deleteBtn);
    expect(onDeleteMock).toHaveBeenCalledWith(mockDoc);
  });

  it("shows reprocess button on error status and triggers onReprocess", () => {
    const onReprocessMock = vi.fn();
    const errorDoc: Document = {
      ...mockDoc,
      status: "error",
      error_message: "OCR extraction failed.",
    };

    render(
      <DocumentListItem
        document={errorDoc}
        onDelete={vi.fn()}
        onReprocess={onReprocessMock}
        isDeleting={false}
        isReprocessing={false}
      />
    );

    expect(screen.getByText("OCR extraction failed.")).toBeInTheDocument();
    const retryBtn = screen.getByRole("button", { name: /retry processing/i });
    expect(retryBtn).toBeInTheDocument();
    fireEvent.click(retryBtn);
    expect(onReprocessMock).toHaveBeenCalledWith(errorDoc);
  });
});
