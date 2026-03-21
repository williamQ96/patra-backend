## [v0.3.0] - 2026-03-21

### Added
- PATRA agent-tool backend endpoints for:
  - paper-to-schema search
  - missing-column feasibility analysis
  - synthesized dataset generation
  - generated artifact download
  - generated artifact admin-review submission
- Generated-artifact persistence via `generated_dataset_artifacts`
- Support for datasheet review payloads that include `dataset_schema_blob`

### Changed
- Promoted the PATRA schema-search workflow from analysis-only to a full bounded synthesis workflow.
- Added optional local LLM-assisted plan generation while preserving deterministic execution and validation boundaries.
- Routed synthesized dataset admission through the existing PATRA admin review queue instead of direct publication.

## [v0.2.0] - 2025-06-10

### Added
- API Endpoints:
  - `/get_github_credentials` (GET): Retrieve GitHub username and token.
  - `/get_huggingface_credentials` (GET): Retrieve Hugging Face username and token.
  - `/modelcard_linkset` (HEAD): Provides model card linkset relations in the HTTP Link header for improved discoverability and interoperability.
- New Project Logo

### Changed
  - Integration guides for OpenAI, Hugging Face, and GitHub.
