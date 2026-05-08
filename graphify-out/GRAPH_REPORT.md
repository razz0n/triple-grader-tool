# Graph Report - c:\\ObsidianRajan\\RajanBrains\\09 ATTACHMENTS\\CSU\\Ontology tool  (2026-05-08)

## Corpus Check
- Corpus is ~31,277 words - fits in a single context window. You may not need a graph.

## Summary
- 339 nodes · 621 edges · 12 communities detected
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 37 edges (avg confidence: 0.77)
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
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]

## God Nodes (most connected - your core abstractions)
1. `_load_session_for_access()` - 17 edges
2. `use_database_storage()` - 16 edges
3. `save_session()` - 16 edges
4. `_display_name()` - 13 edges
5. `_save_loaded_session()` - 13 edges
6. `download_session()` - 13 edges
7. `list_sessions()` - 13 edges
8. `register()` - 12 edges
9. `_is_session_owner()` - 10 edges
10. `_normalize_grade_value()` - 10 edges

## Surprising Connections (you probably didn't know these)
- `_load_users()` --calls--> `load_users_db()`  [INFERRED]
  backend\main.py → backend\database.py
- `_load_tokens()` --calls--> `load_tokens_db()`  [INFERRED]
  backend\main.py → backend\database.py
- `storage_info()` --calls--> `use_database_storage()`  [INFERRED]
  backend\main.py → backend\database.py
- `_save_users()` --calls--> `save_users_db()`  [INFERRED]
  backend\main.py → backend\database.py
- `register()` --calls--> `upsert_user_db()`  [INFERRED]
  backend\main.py → backend\database.py

## Hyperedges (group relationships)
- **Frontend Technology Stack** — React, Vite, ReviewStep, TripleCard, TripleSuggestions [INFERRED]
- **Backend Technology Stack** — FastAPI, Uvicorn, SQLAlchemy, PostgreSQL, Stanza [INFERRED]
- **Triple Lifecycle Management** — Triple, Version, Suggestion, VotingSystem, GradeVoting, ApprovalWorkflow [INFERRED]
- **Sentence Processing Pipeline** — FileUpload, SentenceGroup, Version, Triple, ReviewStep [INFERRED]
- **Collaborative Features** — VotingSystem, Suggestion, ApprovalWorkflow, GradeVoting [INFERRED]

## Communities

### Community 0 - "Community 0"
Cohesion: 0.0
Nodes (82): list_sessions_db(), load_session_db(), use_database_storage(), add_suggestion(), approve_suggestion(), ApproveSuggestionRequest, AuthRequest, _can_approve_session() (+74 more)

### Community 1 - "Community 1"
Cohesion: 0.0
Nodes (23): Suggestion Approval Workflow, Badge Component, FileUpload Component, Grade Voting (0-10), Grading Form Component, GroupCard Component, Manual Entry Mode, Open IE Evaluation (+15 more)

### Community 2 - "Community 2"
Cohesion: 0.0
Nodes (36): _apply_word_aliases(), _collect_span(), _collect_subtree_ids(), compute_metrics(), evaluate_session(), _exact_match(), _expand_coordinated_object_spans(), _extract_triples_from_sentence() (+28 more)

### Community 3 - "Community 3"
Cohesion: 0.0
Nodes (26): add_token_db(), delete_session_db(), delete_sessions_db(), delete_token_db(), init_database(), load_tokens_db(), load_users_db(), database.py - Optional database-backed persistence for users and auth tokens. (+18 more)

### Community 4 - "Community 4"
Cohesion: 0.0
Nodes (25): API Client, AuthPanel Component, Authentication System, CORS Middleware, Database Module, Dependency Parser, DownloadPanel Component, EvaluationPanel Component (+17 more)

### Community 5 - "Community 5"
Cohesion: 0.0
Nodes (23): _build_sentence_groups(), _extract_triples(), _find_sentence_candidate(), _get_version_label(), _is_blank_row(), _is_equals_separator(), _looks_like_sentence(), parse_file() (+15 more)

### Community 6 - "Community 6"
Cohesion: 0.0
Nodes (18): _avg_str(), _grade_str(), _GradingPDF, _pdf_safe(), exporter.py — Convert a graded session JSON into PDF, CSV, Excel, Word, or JSON., Return a Latin-1-safe string (used when Arial is unavailable)., _sentence_metric(), _style_data_cell() (+10 more)

### Community 7 - "Community 7"
Cohesion: 0.0
Nodes (3): loginUser(), logoutUser(), setAuthToken()

### Community 8 - "Community 8"
Cohesion: 0.0
Nodes (20): _apply_collaborative_grades(), _avg_or_none(), _merge_existing_sentence_comments(), _merge_existing_suggestions(), _normalize_grade_value(), _normalize_grades_by_user(), _normalize_sentence_comments(), _normalize_sentence_metric_by_user() (+12 more)

### Community 9 - "Community 9"
Cohesion: 0.0
Nodes (10): FastAPI Backend, PostgreSQL Database, SQLAlchemy ORM, Stanza NLP Library, Uvicorn Server, Run migrations in 'offline' mode (no live DB connection needed)., Run migrations in 'online' mode (live DB connection)., run_migrations_offline() (+2 more)

### Community 10 - "Community 10"
Cohesion: 0.0
Nodes (4): GradingForm(), metricEntries(), normalizeSentenceComments(), stableTextHash()

### Community 11 - "Community 11"
Cohesion: 0.0
Nodes (6): _load_session(), main(), _print_summary(), evaluate.py — CLI for evaluating a graded session against OpenIE.  Usage ----, _write_csv(), _write_json()

## Knowledge Gaps
- **58 isolated node(s):** `database.py - Optional database-backed persistence for users and auth tokens.`, `Create DB tables and optionally bootstrap from existing JSON files.`, `Bulk-upsert all users from a dict; rows for IDs not in the list are deleted.`, `Upsert a single user record (used for registration / profile updates).`, `Bulk-upsert all tokens from a dict; tokens not in the list are deleted.` (+53 more)
  These have ≤1 connection - possible missing edges or undocumented components.