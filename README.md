# RAG over Scanned Books: Project Plan 


## 1. Project summary

**Goal:** Build an MCP server that lets a user in LM Studio query two scanned books (about 900 and 600 pages) containing tables, formulas, figures, and two-column text. The server returns cited text, exact tables and formulas, and page and figure images that the user's vision-capable model can look at.

**Fixed constraints**

- The production data is sensitive and lives in an air-gapped environment.
- During development you provide your own **development data**. **All development data is deleted from the database and disk once development is finished** (see Phase 6).
- Numbers must be accurate, so plain OCR is not acceptable. A vision model reads tables and formulas during ingestion.
- The user works in LM Studio. Our deliverable is the **MCP server** plus the ingestion tooling.
- Python environment: **uv** (no Docker for Python code).
- **Docker is used only for PostgreSQL + pgvector.**
- All models are downloaded in advance and stored in `offline_bundle/models/`.
- Production data will change over time, so the schema, database, and ingestion must support re-ingestion.

**Pipeline**

```
scanned PDFs
  -> split into per-page folders (page image, regions, figures)
  -> layout + vision extraction (Docling + vision model + number cross-check)
  -> structured chunking (text / table / formula / figure)
  -> embeddings (bge-m3 for text, SigLIP for images)
  -> PostgreSQL + pgvector (vectors + metadata + full-text)
  -> MCP server (hybrid retrieval + rerank + image return)
  -> LM Studio
```

---

## 2. Models in the offline bundle

| Model | Dim | Role | Used by |
|---|---|---|---|
| `BAAI/bge-m3` | 1024 | Main text embedding for all text, table, formula, and figure-caption chunks | ingestion, MCP server |
| `BAAI/bge-reranker-v2-m3` | n/a | Cross-encoder reranker on the merged candidate list | MCP server |
| `docling-project/docling-models` | n/a | Layout detection and table-structure weights for Docling | ingestion |
| `google/siglip-so400m-patch14-384` | 1152 | Image embeddings for figure crops, and text-to-image search over figures | ingestion, MCP server |

**Notes**

- **bge-m3** is the single text embedding space. One vector column and one index serve all text-like chunks.
- **SigLIP** is a separate embedding space, so it gets its **own table and own index**. Its text encoder accepts short inputs (about 64 tokens), so `search_figures` must truncate or condense long queries.
- **Docling models** are loaded from a local artifacts path so Docling never tries to download weights.
- The **vision model for extraction** (Qwen-VL or similar) is served by LM Studio through its OpenAI-compatible API. Record which vision model and version was used for every ingestion run.
- **Device planning:** LM Studio occupies GPU memory for the user's chat model. Make the embedding and reranker device configurable (`cpu` / `cuda`) and load SigLIP lazily (only when `search_figures` is first called).

---

## 3. Key decisions

| Decision | Choice | Reason |
|---|---|---|
| Python environment | uv workspace (3 packages) | LM Studio launches the MCP server as a local process |
| Offline Python packaging | Wheelhouse + uv-managed Python + models, `uv sync --offline` | Venv folders are not portable |
| Database | PostgreSQL 16 + pgvector in Docker | Vectors, metadata, and full-text in one engine |
| Page source data | Per-book, per-page folders on disk | Easy to hand the user a path; images served from disk |
| Retrieval | Hybrid (dense + full-text/trigram), RRF fusion, then reranker | Exact numbers match lexically far better than semantically |
| Image retrieval | SigLIP embeddings in a separate table | Find figures from a text query |
| MCP database access | Read-only Postgres role | Only ingestion writes |
| Schema management | Numbered SQL migrations + `schema_version` + Pydantic models | Data will change in production |
| Dev vs production data | Separate DB name, Docker volume, and data folder for development | Makes the final purge clean and verifiable |

**Docker scope:** only the database container. The Docker engine must exist on the target machine. Confirm this early. If it is not allowed, the fallback is a native PostgreSQL install with the pgvector extension.

---

## 4. Project structure

```
rag-project/
├── pyproject.toml                # uv workspace root
├── uv.lock
├── .python-version
├── .env.example
├── docker/
│   ├── compose.yaml              # postgres + pgvector only
│   ├── initdb/
│   │   ├── 000_extensions.sql    # vector, pg_trgm
│   │   └── 001_roles.sql         # ingest (rw) and mcp_ro (read-only)
│   └── images/                   # exported image tarball (docker save)
├── packages/
│   ├── core/                     # shared, light
│   │   └── src/ragcore/
│   │       ├── config.py
│   │       ├── schema.py
│   │       ├── paths.py          # page/region/figure path conventions
│   │       ├── embeddings.py     # bge-m3 + siglip + reranker loaders (offline-only)
│   │       ├── logging.py        # IDs/counts only, never content
│   │       └── db/
│   │           ├── connection.py
│   │           ├── repository.py     # all SQL lives here
│   │           ├── migrate.py
│   │           └── migrations/001_init.sql
│   ├── ingestion/                # heavy, run rarely
│   │   └── src/ingestion/
│   │       ├── cli.py            # split / ingest / reindex / status / report
│   │       ├── split_pages.py
│   │       ├── pipeline.py       # orchestration, per-page checkpoints
│   │       ├── extract/          # layout.py, vlm_client.py, number_check.py
│   │       ├── chunking/         # text.py, table.py, formula.py, figure.py
│   │       ├── indexer.py
│   │       └── report.py
│   └── mcp_server/               # light, always running
│       └── src/mcp_server/
│           ├── server.py         # stdio entry point
│           ├── tools.py
│           ├── formatting.py
│           ├── images.py
│           └── retrieval/        # dense.py, fulltext.py, fusion.py, rerank.py, figures.py
├── offline_bundle/
│   ├── models/
│   │   ├── BAAI_bge-m3/
│   │   ├── BAAI_bge-reranker-v2-m3/
│   │   ├── docling-project_docling-models/
│   │   └── google_siglip-so400m-patch14-384/
│   ├── wheelhouse/
│   ├── python/
│   └── MANIFEST.sha256
├── scripts/
│   ├── build_bundle.sh
│   ├── install_offline.sh
│   ├── verify_offline.sh
│   ├── db_up.sh / db_backup.sh / db_restore.sh
│   ├── purge_dev_data.sh         # wipes all development data (Phase 6)
│   ├── verify_clean.sh           # confirms nothing is left (Phase 6)
│   └── make_mcp_json.py
├── tools/                        # viewer/, eval/
├── tests/                        # schema, chunking, smoke tests
└── data/                         # gitignored; never copied into the bundle
    ├── dev/                      # YOUR development data lives only here
    │   ├── input/                # development PDFs
    │   ├── books/                # per-page folders
    │   ├── samples/              # small subset for the smoke test
    │   ├── questions/            # development question set
    │   └── dumps/                # any dev database backups
    ├── prod/                     # production data (created on the target machine)
    │   ├── input/
    │   └── books/
    ├── pgdata/                   # Postgres volume (dev and prod use separate volumes)
    └── logs/
```

**Rules**

- `core` is the contract: schema, migrations, path conventions, and model loading live there only.
- All SQL stays in `repository.py`.
- `mcp_server` never imports docling, OCR libraries, or ingestion code.
- Models are loaded only through `core/embeddings.py`, which forces offline mode and checks the DB's recorded model names and dimensions.
- Logs contain IDs, counts, and timings, never document content.
- **Everything derived from development data stays under `data/dev/`** (including the smoke-test samples, question sets, and dumps). Nothing derived from it goes into `tests/`, `offline_bundle/`, or git. This is what makes the final purge complete.

---

## 5. Page folders (source data layout)

```
data/dev/books/            (or data/prod/books/ in production)
└── <book_slug>/
    ├── book.json                  # title, source file hash, page count
    └── pages/
        ├── p0001/
        │   ├── page.png           # full page render (200-300 dpi)
        │   ├── page.json          # regions, reading order, flags, hashes
        │   ├── page.md            # extracted content in reading order
        │   └── regions/
        │       ├── r001_text.png
        │       ├── r002_table.png
        │       ├── r003_formula.png
        │       └── r004_figure.png
        ├── p0002/
        └── ...
```

**Conventions**

- Zero-padded names (`p0001`); 4 digits covers the 900-page book.
- The database stores paths **relative to `DATA_ROOT`**, never absolute, so moving the folder only needs one `.env` change.
- Each page carries its own hash in `page.json` for incremental ingestion.
- The MCP server can return the path of any page or region so the user can open the source directly.
- Images sent to the model are resized at read time, not on disk.

---

## 6. Database design (PostgreSQL + pgvector)

**Extensions:** `vector`, `pg_trgm`. Use the pgvector Docker image, pinned by version.

| Table | Purpose | Key columns |
|---|---|---|
| `meta` | Versions and provenance | `schema_version`, text and image embedding model names and dimensions |
| `documents` | One row per book | `id`, `slug`, `title`, `source_hash`, `page_count`, `root_path` |
| `pages` | One row per page | `document_id`, `page_number`, `page_hash`, `folder_path`, `image_path`, `status` |
| `regions` | Detected regions | `page_id`, `kind`, `bbox`, `image_path`, `reading_order`, `flags` |
| `chunks` | Searchable units | `id`, `region_id`, `document_id`, `page_number`, `content_type`, `content`, `search_text`, `section`, `embedding vector(1024)`, `tsv tsvector`, `is_deleted` |
| `figures` | Figure images | `id`, `region_id`, `caption`, `description`, `image_path`, `embedding vector(1152)` |
| `run_log` | Per-page ingestion status | `run_id`, `page_id`, `step`, `status`, `error_code`, `timings` |

**Indexes**

- HNSW (cosine) on `chunks.embedding` and `figures.embedding`.
- GIN on `chunks.tsv`, and a GIN trigram index on `chunks.search_text` for exact and partial number matches.
- Regular indexes on `(document_id, page_number)` and `content_type`.

**Full-text and numbers:** use the `simple` configuration (no stemming, no stop words) so numbers, units, and symbols survive. Keep a normalized `search_text` column (for example `1,200` and `1200` both searchable). Test decimals, negatives, units, and scientific notation on your development data.

**Roles and access**

- `ingest` role: read/write, used only by ingestion.
- `mcp_ro` role: `SELECT` only, used by the MCP server.
- Bind the port to `127.0.0.1`. Passwords come from `.env`, never committed.

**Containers and volumes**

- Development uses its own compose project name, database name, and volume (for example `rag_dev`). Production uses a different one. This lets the purge remove the whole development volume instead of deleting rows one table at a time.
- `restart: unless-stopped`, a healthcheck, and backup/restore scripts.
- The MCP server fails with a clear message if the database is down or the schema version is wrong.

**Re-ingestion**

- Document and page hashes decide what changed. Changed pages: soft-delete old chunks, insert new ones, clean up later.
- If an embedding model changes, `meta` detects the mismatch and the operator runs `reindex`.

---

## 7. Phases

### Phase 0: Setup and discovery

- [ ] Create the uv workspace and three packages; pin Python; commit `uv.lock`.
- [ ] Define `.env.example` (DB settings, `DATA_ROOT`, model paths, LM Studio endpoint, device settings, dev vs prod profile).
- [ ] Collect target machine facts: OS, CPU architecture, GPU and VRAM, disk space, whether Docker is available.
- [ ] Confirm the books' language(s).
- [ ] Confirm which vision model serves extraction in LM Studio.
- [ ] Confirm the LM Studio version and whether the user's models will receive tool-returned images.

**Exit criteria:** workspace installs cleanly; target facts documented.

---

### Phase 1: Core package and database

- [ ] `docker/compose.yaml` for Postgres + pgvector with initdb scripts (extensions, roles), with separate dev and prod profiles.
- [ ] Migration runner and `001_init.sql` with all tables and indexes.
- [ ] Pydantic models, `paths.py`, `config.py`.
- [ ] `embeddings.py`: offline loaders for bge-m3, SigLIP, and the reranker; provenance check against `meta`.
- [ ] `repository.py`: upsert, soft-delete, hybrid search, figure search.
- [ ] Content-safe logging.
- [ ] Tests against a throwaway Postgres container.

**Exit criteria:** fresh DB builds from migrations; re-running is safe; model mismatch is detected; the read-only role cannot write.

---

### Phase 2: Development data

- [ ] Place your development PDFs in `data/dev/input/`.
- [ ] Pick a small subset (5 to 10 pages) into `data/dev/samples/` for the smoke test.
- [ ] Write a development question set in `data/dev/questions/` with known answers, including exact-number questions and figure-finding questions.
- [ ] Add a short checklist of the content types you want covered (two-column text, tables, formulas, figures) and confirm the development data includes each.

**Exit criteria:** development data and question set are in place under `data/dev/` only.

---

### Phase 3: Ingestion

- [ ] **`split_pages.py`:** PDF to per-page folders with `page.png` and `page.json`; hash each page.
- [ ] **Layout (Docling):** regions, reading order, two-column handling, using the local `docling-models` weights.
- [ ] **Region crops:** save every region image into `regions/`.
- [ ] **Vision client:** call the LM Studio vision model per region. Tables to HTML/Markdown, formulas to LaTeX, figures to a description.
- [ ] **Compare vision model options** on your development tables and formulas; record accuracy per model.
- [ ] **Number check:** second OCR pass on table and formula crops; flag numeric disagreements.
- [ ] **Chunking by structure:** a table is one chunk with caption and a short summary; a formula keeps its surrounding explanation; a figure chunk holds caption plus description; text uses paragraph-aware chunks.
- [ ] **Indexer:** bge-m3 embeddings for chunks; SigLIP embeddings for figure crops; write everything to Postgres.
- [ ] **Resumability:** per-page checkpoints in `run_log`.
- [ ] **Incremental updates** using page and document hashes.
- [ ] **CLI:** `split`, `ingest`, `reindex`, `status`, `report`.
- [ ] **Report:** flagged regions, per-page stats, timings (no content).

**Exit criteria:** end-to-end run on the development data; table and number accuracy measured by spot-checking against the source pages; an interrupted run resumes correctly.

---

### Phase 4: MCP server

**Start with a spike:** build a minimal MCP server whose only tool returns an image, and test it in LM Studio with a vision model. Whether tool-returned images reach the model depends on the LM Studio version and the chosen model. If they do not, the fallback is to return the figure's description, caption, and file path.

**Retrieval flow**

1. Embed the query with bge-m3.
2. Dense search (pgvector) and full-text/trigram search in parallel.
3. Fuse with Reciprocal Rank Fusion.
4. Rerank the top candidates with bge-reranker-v2-m3.
5. Return compact results with citations.

**Tools**

| Tool | Returns |
|---|---|
| `search(query, book?, content_type?, top_k)` | Compact snippets with book, page, chunk ID, content type |
| `search_figures(query, book?, top_k)` | Figure IDs with captions, pages, and thumbnails |
| `get_chunk(id)` | Full table, formula, or text chunk |
| `get_page(book, page)` | Page content in reading order, plus the page folder path |
| `get_image(id or book+page+region)` | The image (downscaled) plus its source path |
| `list_documents()` | Books, page counts, status |

**Behavior rules**

- Always include book and page citations.
- Tool descriptions tell the model to quote numbers exactly as returned.
- Cap output sizes so small local models are not overwhelmed.
- Images: load from `DATA_ROOT`, downscale (start around 1024 to 1568 px on the longest side), limit to 1 to 3 per call, return the source path, and give a clear error for missing files.
- Load SigLIP lazily; run bge-m3 and the reranker on the configured device.
- Connect with the `mcp_ro` role; fail clearly on schema or embedding mismatch.
- Test with several LM Studio models, including small and vision-capable ones.

**Exit criteria:** LM Studio calls every tool; retrieval hit rate on the development question set meets your target; images reach a vision model (or the fallback is implemented); outputs fit small context windows.

---

### Phase 5: Operator tools and offline bundle

**Operator tools**

- [ ] **Viewer:** page image beside extracted output, flagged regions highlighted.
- [ ] **Eval runner:** the operator's own question set; reports retrieval hit rate without exporting content.
- [ ] **Diagnostics export:** IDs, counts, and timings only.
- [ ] **Smoke test command:** starts the DB, ingests the sample pages, and runs a test query.

**Offline bundle**

- [ ] `build_bundle.sh`: wheels, the uv-managed Python, and full snapshots of the four models; write `MANIFEST.sha256`.
- [ ] **Postgres image:** `docker pull` the pinned pgvector image, `docker save` it to `docker/images/`; on the target use `docker load`.
- [ ] `install_offline.sh`: `uv sync --offline`, load the image, start the DB, run migrations.
- [ ] `verify_offline.sh`: run everything with the network disabled; set `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`.
- [ ] Hunt hidden runtime downloads: tokenizer files, Docling weights, OCR models, fonts.
- [ ] `make_mcp_json.py`: generate the LM Studio `mcp.json` entry with absolute paths.
- [ ] **Build the final bundle only after Phase 6 (purge)**, so it cannot contain development data.

**Exit criteria:** a fresh machine with no internet installs from the bundle and passes the smoke test.

---

### Phase 6: Purge development data (required before delivery)

When development is finished, **all development data is deleted** from the database and from disk.

**`scripts/purge_dev_data.sh` removes**

- [ ] The development database and its Docker volume (`docker compose down -v` for the dev project), so no rows, vectors, or indexes remain.
- [ ] `data/dev/` entirely: input PDFs, per-page folders, region crops, figure images, samples, question sets, and dumps.
- [ ] Any database backups or dumps made during development, wherever they were saved.
- [ ] Logs and reports created during development.
- [ ] Temporary and cache folders created by the pipeline (Docling and OCR temp files, image caches, `__pycache__`).
- [ ] Development container images or volumes that held data.

**`scripts/verify_clean.sh` confirms**

- [ ] The development volume and database no longer exist.
- [ ] `data/dev/` is absent or empty.
- [ ] Table row counts are zero in any remaining database (`documents`, `pages`, `regions`, `chunks`, `figures`, `run_log`).
- [ ] No page images, PDFs, or dumps are found in `data/`, `tests/`, `offline_bundle/`, or the repository (search by file type).
- [ ] Git history and the working tree contain no development data.

**Exit criteria:** `verify_clean.sh` passes; only code, schema, models, and the empty production configuration remain. Then build the final offline bundle.

---

### Phase 7: Dry run and production

- [ ] Walk the operator through installation from written instructions only.
- [ ] Run the smoke test inside the secure environment.
- [ ] Split and ingest the real books into `data/prod/` (long run; rely on checkpoints).
- [ ] Review flagged regions with the viewer; re-run or correct as needed.
- [ ] The operator runs the eval with their own questions, including figure and number questions.
- [ ] Connect LM Studio and test with the models the user plans to use.
- [ ] Document the update procedure: changed data (incremental re-ingestion), new software versions (new bundle transfer), and DB backup and restore.

**Exit criteria:** the user queries the books in LM Studio and receives cited, accurate answers with images when relevant.

---

## 8. Safeguards

- Everything is config-driven; no hard-coded paths. Paths in the DB are relative to `DATA_ROOT`.
- Development and production use separate databases, volumes, and folders.
- Content-free logs and diagnostics, so production problems can be debugged from IDs and error codes alone.
- Specific, readable error messages (the operator will relay them to you).
- Version stamps in the DB and reports: schema version, model names, package versions, vision model used.

---

## 9. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Wrong digits in tables or formulas | Dual-extraction check, flagged-region review, viewer |
| Development data left behind | Separate dev volume and folder; `purge_dev_data.sh` and `verify_clean.sh`; bundle built after the purge |
| LM Studio does not forward tool-returned images | Phase 4 spike first; fallback to description, caption, and path |
| Docker unavailable on target | Confirm in Phase 0; fallback to native PostgreSQL + pgvector |
| Target machine differs from build machine | Document facts early; wheelhouse built for the exact platform |
| Hidden downloads fail offline | `verify_offline.sh` with the network disabled; checksum manifest |
| GPU memory shared with LM Studio | Configurable devices; CPU option; lazy SigLIP |
| Slow MCP server startup | Lazy-load heavy models |
| Production scans differ from development data | Keep the vision model and OCR configurable; review flagged regions after the first run |
| SigLIP text query too long | Truncate or condense queries for `search_figures` |
| Images too large for model context | Downscale at read time; limit images per call |
| Schema changes break production DB | Numbered migrations, `schema_version`, tested upgrade path |
| Embedding model changes silently | Provenance in `meta`; refuse to run on mismatch |
| Model licenses | Check each license for your use case before bundling |

---

## 10. Open questions to resolve first

1. Target OS, CPU architecture, GPU model, and VRAM.
2. Is the Docker engine available and permitted on the target machine?
3. Language(s) of the books.
4. Which vision model serves extraction in LM Studio, and is it on the same machine as the MCP server?
5. Which LM Studio version will the user run, and will their chat models be vision-capable?
6. Accuracy targets (table cell accuracy, retrieval hit rate).

---

## 11. Suggested build order

1. Phase 0 and Phase 1 (workspace, core, Postgres)
2. Phase 2 (development data)
3. Phase 3 (ingestion)
4. Phase 4 (MCP server; image spike first)
5. Phase 5 (operator tools, then bundle)
6. Phase 6 (purge development data and verify)
7. Phase 7 (dry run and production)

Note: Phase 5's final bundle is built after Phase 6.
