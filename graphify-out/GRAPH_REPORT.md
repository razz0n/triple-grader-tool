# Graph Report - .  (2026-04-30)

## Corpus Check
- Corpus is ~18,343 words - fits in a single context window. You may not need a graph.

## Summary
- 266 nodes · 460 edges · 13 communities detected
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 35 edges (avg confidence: 0.76)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 24|Community 24]]

## God Nodes (most connected - your core abstractions)
1. `use_database_storage()` - 15 edges
2. `_load_session_for_access()` - 13 edges
3. `register()` - 12 edges
4. `_display_name()` - 11 edges
5. `_save_loaded_session()` - 11 edges
6. `_load_users()` - 9 edges
7. `save_session()` - 9 edges
8. `_build_sentence_groups()` - 9 edges
9. `parse_file_rich()` - 9 edges
10. `_norm_username()` - 8 edges

## Surprising Connections (you probably didn't know these)
- `_load_users()` --calls--> `load_users_db()`  [INFERRED]
  backend\main.py → backend\database.py
- `_load_tokens()` --calls--> `load_tokens_db()`  [INFERRED]
  backend\main.py → backend\database.py
- `list_sessions()` --calls--> `list_sessions_db()`  [INFERRED]
  backend\main.py → backend\database.py
- `storage_info()` --calls--> `use_database_storage()`  [INFERRED]
  backend\main.py → backend\database.py
- `_save_users()` --calls--> `save_users_db()`  [INFERRED]
  backend\main.py → backend\database.py

## Hyperedges (group relationships)
- **** — upload_endpoint, parser_py, graded_session, dual_storage_mode [EXTRACTED]
- **** — download_endpoint, to_csv, to_excel, to_pdf, to_word, to_json [EXTRACTED]
- **** — user_record, token_record, session_record, sqlite_db, json_storage [EXTRACTED]
- **** — parse_file_rich, build_sentence_groups, extract_triples, looks_like_sentence, ontology_triple [EXTRACTED]
- **** — grading_form, triple_card, triple_suggestions [EXTRACTED]
- **** — domain_triple, domain_grade, domain_sentence_grade [EXTRACTED]
- **** — domain_suggestion, domain_user, domain_triple [EXTRACTED]
- **** — auth_panel, file_upload, review_step, grading_form [EXTRACTED]
- **** — download_panel, save_endpoint_fe, export_formats [EXTRACTED]

## Communities

### Community 0 - "Community 0"
Cohesion: 0.0
Nodes (60): load_session_db(), use_database_storage(), add_suggestion(), approve_suggestion(), _current_user(), _current_user_from_bearer_or_query(), delete_suggestion(), _display_name() (+52 more)

### Community 1 - "Community 1"
Cohesion: 0.0
Nodes (33): Alembic Migration Tool, Auth Endpoints (login/register/logout), Bearer Auth Token, CORS Middleware, database.py - DB Persistence Module, GET /api/download/{id}/{fmt}, Dual Storage Mode (json vs database), exporter.py - Session Exporter (+25 more)

### Community 2 - "Community 2"
Cohesion: 0.0
Nodes (27): api.js (API Layer), App (Root Component), Auth Endpoints (/api/auth/*), AuthPanel (Login/Register UI), Sentence Completeness Metric, External Relation Metric, Triple Quality Grade (0-10), Sentence (Natural Language Unit) (+19 more)

### Community 3 - "Community 3"
Cohesion: 0.0
Nodes (25): Parse an uploaded CSV or Excel file and return structured sentence-group data fo, upload_file(), _build_sentence_groups(), _extract_triples(), _find_sentence_candidate(), _get_version_label(), _is_blank_row(), _is_equals_separator() (+17 more)

### Community 4 - "Community 4"
Cohesion: 0.0
Nodes (23): add_token_db(), delete_token_db(), init_database(), list_sessions_db(), load_tokens_db(), load_users_db(), database.py - Optional database-backed persistence for users and auth tokens., Bulk-upsert all users from a dict; rows for IDs not in the list are deleted. (+15 more)

### Community 5 - "Community 5"
Cohesion: 0.0
Nodes (17): _avg_str(), _grade_str(), _GradingPDF, _pdf_safe(), exporter.py — Convert a graded session JSON into PDF, CSV, Excel, Word, or JSON., Return a Latin-1-safe string (used when Arial is unavailable)., _sentence_metric(), _style_data_cell() (+9 more)

### Community 6 - "Community 6"
Cohesion: 0.0
Nodes (3): loginUser(), logoutUser(), setAuthToken()

### Community 7 - "Community 7"
Cohesion: 0.0
Nodes (10): _build_sentence_groups() - Group Builder, _extract_triples() - Triple Extractor, Golden Dataset CSV (ontology triples), _looks_like_sentence() - Sentence Heuristic, Ontology Triple (Subject-Predicate-Object), parse_file() - Legacy Flat Parser, parse_file_rich() - Enhanced Parser, parser.py - Ontology Triple Parser (+2 more)

### Community 8 - "Community 8"
Cohesion: 0.0
Nodes (8): ApproveSuggestionRequest, AuthRequest, EditSuggestionRequest, RegisterRequest, SaveRequest, TripleSuggestionRequest, VoteRequest, BaseModel

### Community 9 - "Community 9"
Cohesion: 0.0
Nodes (4): Run migrations in 'offline' mode (no live DB connection needed)., Run migrations in 'online' mode (live DB connection)., run_migrations_offline(), run_migrations_online()

### Community 11 - "Community 11"
Cohesion: 0.0
Nodes (1): initial_tables  Revision ID: a761e4495192 Revises:  Create Date: 2026-04-30

### Community 12 - "Community 12"
Cohesion: 0.0
Nodes (3): Backend REST API, vite.config.js (Build Config), Vite Dev Proxy (/api to localhost:8001)

### Community 24 - "Community 24"
Cohesion: 0.0
Nodes (1): eslint.config.js (Lint Config)

## Knowledge Gaps
- **38 isolated node(s):** `database.py - Optional database-backed persistence for users and auth tokens.`, `Create DB tables and optionally bootstrap from existing JSON files.`, `Bulk-upsert all users from a dict; rows for IDs not in the list are deleted.`, `Upsert a single user record (used for registration / profile updates).`, `Bulk-upsert all tokens from a dict; tokens not in the list are deleted.` (+33 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 11`** (4 nodes): `a761e4495192_initial_tables.py`, `downgrade()`, `initial_tables  Revision ID: a761e4495192 Revises:  Create Date: 2026-04-30`, `upgrade()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (1 nodes): `eslint.config.js (Lint Config)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.