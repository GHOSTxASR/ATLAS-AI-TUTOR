from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field

SearchSource = Literal["document", "memory", "note", "chat_summary", "graph_node"]
GlobalCategory = Literal["chats", "notes", "documents", "graph", "roadmap"]


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Semantic search query string")
    top_k: int = Field(10, ge=1, le=100, description="Max number of results to return")
    sources: list[SearchSource] | None = Field(
        None, description="List of source collections to search across"
    )
    document_ids: list[str] | None = Field(
        None, description="Optional document IDs to filter by"
    )
    file_type: str | None = Field(None, description="Filter by file type (e.g. pdf, docx, txt)")
    category: str | None = Field(None, description="Filter memory by category (e.g. strength, weakness)")
    roadmap_node_id: str | None = Field(None, description="Filter by associated roadmap node ID")


class SearchResultItem(BaseModel):
    id: str
    source_type: str
    source_id: str
    profile_id: str
    text: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[SearchResultItem]


class GlobalSearchResultItem(BaseModel):
    id: str
    title: str
    subtitle: str | None = None
    snippet: str
    category: GlobalCategory
    url_path: str
    score: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class GlobalSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Global search query string")
    categories: list[GlobalCategory] | None = Field(
        None, description="Categories to filter search across: chats, notes, documents, graph, roadmap"
    )
    limit_per_category: int = Field(5, ge=1, le=20, description="Max items per category")
    include_semantic: bool = Field(True, description="Include semantic vector matches for notes and documents")


class GlobalSearchResponse(BaseModel):
    query: str
    total_results: int
    chats: list[GlobalSearchResultItem] = Field(default_factory=list)
    notes: list[GlobalSearchResultItem] = Field(default_factory=list)
    documents: list[GlobalSearchResultItem] = Field(default_factory=list)
    graph: list[GlobalSearchResultItem] = Field(default_factory=list)
    roadmap: list[GlobalSearchResultItem] = Field(default_factory=list)
