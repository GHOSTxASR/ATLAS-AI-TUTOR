from __future__ import annotations

from typing import AsyncIterator
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base
from app.db.repositories.profile_repo import ProfileRepository
from app.models.abstraction import BaseModelClient, ChatMessage, ChatResponse, StreamChunk
from app.schemas.graph import GraphEdgeCreate, GraphEnrichRequest, GraphNodeCreate
from app.services.graph_service import GraphService


class MockGraphLLM(BaseModelClient):
    """Mock LLM for Knowledge Graph concept extraction."""

    async def chat_complete(self, messages: list[ChatMessage], **kwargs) -> ChatResponse:
        return ChatResponse(
            content='{\n'
                    '  "concepts": [\n'
                    '    {"label": "Matrix Multiplication", "description": "Row by column dot products."},\n'
                    '    {"label": "Eigenvalues", "description": "Characteristic roots of linear transformations."}\n'
                    '  ],\n'
                    '  "relationships": [\n'
                    '    {"source": "Matrix Multiplication", "target": "Eigenvalues", "type": "prerequisite_of"}\n'
                    '  ]\n'
                    '}'
        )

    async def chat_stream(self, messages: list[ChatMessage], **kwargs) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(content="", done=True)

    async def close(self) -> None:
        pass

    def get_provider_name(self) -> str:
        return "mock_graph_llm"


@pytest.fixture
async def async_db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_knowledge_graph_node_and_edge_crud(async_db_session: AsyncSession, tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNINGOS_DATA_DIR", str(tmp_path / "learningos-data"))
    from app.config import get_settings
    get_settings.cache_clear()

    profile_repo = ProfileRepository(async_db_session)
    profile = await profile_repo.create(name="Graph Student", profile_type="GATE")

    service = GraphService(session=async_db_session)

    # 1. Create Nodes
    n1 = await service.create_node(
        profile.id,
        GraphNodeCreate(label="Linear Algebra", type="subject", description="Foundations of vector spaces"),
    )
    n2 = await service.create_node(
        profile.id,
        GraphNodeCreate(label="Vectors", type="concept", description="Magnitude and direction", mastery_score=0.8),
    )
    n3 = await service.create_node(
        profile.id,
        GraphNodeCreate(label="Dot Product", type="concept", description="Scalar projection", mastery_score=0.6),
    )

    assert n1.id is not None
    assert n2.mastery_score == 0.8

    # 2. Create Edges
    e1 = await service.create_edge(
        profile.id,
        GraphEdgeCreate(source=n1.id, target=n2.id, type="taught_in"),
    )
    e2 = await service.create_edge(
        profile.id,
        GraphEdgeCreate(source=n2.id, target=n3.id, type="prerequisite_of"),
    )
    assert e1.source == n1.id
    assert e2.type == "prerequisite_of"

    # 3. Retrieve Graph Data & Stats
    graph_data = await service.get_graph_data(profile.id)
    assert len(graph_data.nodes) == 3
    assert len(graph_data.links) >= 2
    assert graph_data.stats is not None
    assert graph_data.stats.concepts_count == 2
    assert graph_data.stats.average_mastery == 0.7  # (0.8 + 0.6) / 2

    # 4. Find Path between Vectors (n2) and Dot Product (n3)
    path_res = await service.find_concept_path(profile.id, n2.id, n3.id)
    assert path_res.path_found is True
    assert path_res.length == 1
    assert path_res.path[0].id == n2.id
    assert path_res.path[1].id == n3.id

    # 5. Search Nodes
    search_res = await service.search_nodes(profile.id, "scalar")
    assert len(search_res) == 1
    assert search_res[0].label == "Dot Product"


@pytest.mark.asyncio
async def test_knowledge_graph_enrichment(async_db_session: AsyncSession, tmp_path, monkeypatch):
    monkeypatch.setenv("LEARNINGOS_DATA_DIR", str(tmp_path / "learningos-data"))
    monkeypatch.setattr("app.services.graph_service.get_model_client", lambda s: MockGraphLLM())

    from app.config import get_settings
    get_settings.cache_clear()

    profile_repo = ProfileRepository(async_db_session)
    profile = await profile_repo.create(name="Enrichment Learner", profile_type="JEE")

    service = GraphService(session=async_db_session)

    # Enrich from learning content
    enrich_req = GraphEnrichRequest(
        text="Matrix multiplication transforms coordinate bases. Eigenvalues and eigenvectors characterize invariant subspaces.",
        source_type="document",
        source_id="doc-12345",
        source_label="Linear Algebra Notes.pdf",
    )
    enriched_graph = await service.enrich_from_text(profile.id, enrich_req)

    assert len(enriched_graph.nodes) >= 3  # Document + 2 extracted concepts
    labels = [n.label for n in enriched_graph.nodes]
    assert "Matrix Multiplication" in labels
    assert "Eigenvalues" in labels
