from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

GraphNodeType = Literal["concept", "chapter", "subject", "document", "note", "quiz"]
GraphEdgeType = Literal["prerequisite_of", "related_to", "taught_in", "referenced_by", "learned_from", "tested_by"]


class GraphNodeCreate(BaseModel):
    label: str = Field(..., description="Name or title of the concept/entity")
    type: GraphNodeType = Field("concept", description="Node entity type")
    description: str | None = Field(None, description="Summary or definition")
    mastery_score: float = Field(0.0, ge=0.0, le=1.0, description="Concept mastery score")
    roadmap_node_id: str | None = None
    document_ids: list[str] = Field(default_factory=list)
    chat_session_ids: list[str] = Field(default_factory=list)


class GraphNodeUpdate(BaseModel):
    label: str | None = None
    description: str | None = None
    mastery_score: float | None = Field(None, ge=0.0, le=1.0)
    mention_count: int | None = Field(None, ge=0)


class GraphNode(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    label: str
    type: GraphNodeType
    profile_id: str
    description: str | None = None
    mastery_score: float = 0.0
    mention_count: int = 1
    first_seen: datetime
    last_seen: datetime
    roadmap_node_id: str | None = None
    document_ids: list[str] = Field(default_factory=list)
    chat_session_ids: list[str] = Field(default_factory=list)


class GraphEdgeCreate(BaseModel):
    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    type: GraphEdgeType = Field("related_to", description="Relationship type")
    weight: float = Field(1.0, ge=0.0, description="Edge weight or relationship confidence")


class GraphEdge(BaseModel):
    source: str
    target: str
    type: GraphEdgeType
    weight: float = 1.0
    created_at: datetime


class GraphStats(BaseModel):
    total_nodes: int = 0
    total_edges: int = 0
    concepts_count: int = 0
    documents_count: int = 0
    average_mastery: float = 0.0


class GraphDataResponse(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    links: list[GraphEdge] = Field(default_factory=list)
    directed: bool = True
    multigraph: bool = False
    stats: GraphStats | None = None


class GraphEnrichRequest(BaseModel):
    """Where to read concepts from: a document already uploaded, or pasted text.

    `text` used to be required, which meant the only way to map a syllabus was
    to paste it in again after uploading it. Naming `document_id` instead reads
    the text that was already extracted on upload.
    """

    text: str | None = Field(
        None, description="Text to extract from. Ignored when document_id is given."
    )
    document_id: str | None = Field(
        None, description="An uploaded document to read the text from"
    )
    document_ids: list[str] | None = Field(
        None,
        description=(
            "Several uploaded documents to read in one pass -- every syllabus "
            "for a course, or the whole set of materials when none is marked."
        ),
    )
    source_type: str = Field("document", description="document or chat")
    source_id: str | None = Field(None, description="Optional ID of originating document or chat session")
    source_label: str | None = Field(None, description="Optional display name of source document or session")

    @model_validator(mode="after")
    def _needs_a_source(self) -> "GraphEnrichRequest":
        if not (self.text or "").strip() and not self.document_id and not self.document_ids:
            raise ValueError("Provide documents or text to extract from.")
        return self


class GraphPathResponse(BaseModel):
    source_id: str
    target_id: str
    path_found: bool
    path: list[GraphNode] = Field(default_factory=list)
    length: int = 0
