# Atlas Documentation

Design and implementation notes for Atlas. These describe how the system works
and why it is built the way it is — start with the README at the repository
root for installing and running it.

## Where to start

| If you want to | Read |
| --- | --- |
| Understand the whole system | [01_ARCHITECTURE.md](01_ARCHITECTURE.md) |
| Find your way around the code | [02_REPOSITORY_STRUCTURE.md](02_REPOSITORY_STRUCTURE.md) |
| Work on the API | [04_API_SPECIFICATION.md](04_API_SPECIFICATION.md) |
| Work on retrieval | [07_RAG_ARCHITECTURE.md](07_RAG_ARCHITECTURE.md), [19_VECTOR_DATABASE_DESIGN.md](19_VECTOR_DATABASE_DESIGN.md) |
| Change the schema | [03_DATABASE_DESIGN.md](03_DATABASE_DESIGN.md) |
| Add a model provider | [18_MODEL_INTEGRATION.md](18_MODEL_INTEGRATION.md) |

## Contents

**System**
- [01_ARCHITECTURE.md](01_ARCHITECTURE.md) — how the pieces fit together
- [02_REPOSITORY_STRUCTURE.md](02_REPOSITORY_STRUCTURE.md) — what lives where
- [06_BACKEND_ARCHITECTURE.md](06_BACKEND_ARCHITECTURE.md) — FastAPI layering
- [05_FRONTEND_ARCHITECTURE.md](05_FRONTEND_ARCHITECTURE.md) — React app structure

**Data**
- [03_DATABASE_DESIGN.md](03_DATABASE_DESIGN.md) — schema and migrations
- [19_VECTOR_DATABASE_DESIGN.md](19_VECTOR_DATABASE_DESIGN.md) — collections and namespacing
- [10_DOCUMENT_PROCESSING.md](10_DOCUMENT_PROCESSING.md) — extraction, OCR, chunking

**The AI parts**
- [07_RAG_ARCHITECTURE.md](07_RAG_ARCHITECTURE.md) — retrieval and citation
- [08_MEMORY_SYSTEM.md](08_MEMORY_SYSTEM.md) — long-term learner memory
- [09_KNOWLEDGE_GRAPH.md](09_KNOWLEDGE_GRAPH.md) — concept extraction and layout
- [11_ROADMAP_ENGINE.md](11_ROADMAP_ENGINE.md) — syllabus to topic DAG
- [12_AI_TUTOR_ENGINE.md](12_AI_TUTOR_ENGINE.md) — tutoring modes and prompting
- [18_MODEL_INTEGRATION.md](18_MODEL_INTEGRATION.md) — providers and the client abstraction

**Interface, quality, operations**
- [15_UI_UX_SPEC.md](15_UI_UX_SPEC.md) — visual system and interaction rules
- [16_TESTING_STRATEGY.md](16_TESTING_STRATEGY.md) — what is tested and how
- [17_SECURITY_AND_PRIVACY.md](17_SECURITY_AND_PRIVACY.md) — key handling, local-first guarantees
- [13_DEPLOYMENT.md](13_DEPLOYMENT.md) — install and run
- [14_DEVELOPMENT_ROADMAP.md](14_DEVELOPMENT_ROADMAP.md) — MVP definition and direction
- [../backend/evals/README.md](../backend/evals/README.md) — how the AI parts are measured

## A caveat

Several of these were written before the code and have drifted from it in
places. Where a document and the code disagree, the code is right — and a pull
request correcting the document is welcome.
