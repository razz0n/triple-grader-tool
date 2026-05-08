// ReviewStep.jsx — Pre-grading review and cleaning step.
// Lets the user inspect every parsed sentence group, select which version
// of triples to use, edit the sentence text, and toggle individual triples
// on/off before proceeding to grading.

import { useState, useCallback, useEffect } from "react";

function createEmptyManualGroup(nextGroupId) {
  const manualVersionId = `manual_${nextGroupId}_v1`;
  return {
    groupId: nextGroupId,
    included: true,
    editedText: "",
    selectedVersionId: manualVersionId,
    includedTripleIds: new Set(),
    rawVersions: [
      {
        version_id: manualVersionId,
        version_label: "Manual",
        sentence_candidate: "",
        triples: [],
      },
    ],
  };
}

// ── small helpers ──────────────────────────────────────────────────────────

function Badge({ color, children }) {
  const colors = {
    blue:   "bg-blue-100 text-blue-800",
    green:  "bg-green-100 text-green-800",
    purple: "bg-purple-100 text-purple-800",
    gray:   "bg-gray-100 text-gray-700",
  };
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-mono font-semibold ${colors[color] ?? colors.gray}`}>
      {children}
    </span>
  );
}

function TripleRow({ triple, included, onToggle, onSaveEdit, onDelete }) {
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState({
    subject: triple.subject || "",
    predicate: triple.predicate || "",
    object: triple.object || "",
  });

  useEffect(() => {
    setDraft({
      subject: triple.subject || "",
      predicate: triple.predicate || "",
      object: triple.object || "",
    });
  }, [triple.id, triple.subject, triple.predicate, triple.object]);

  const handleSave = () => {
    const subject = draft.subject.trim();
    const predicate = draft.predicate.trim();
    const object = draft.object.trim();

    if (!subject || !predicate || !object) {
      alert("Subject, predicate, and object are required.");
      return;
    }

    onSaveEdit(triple.id, { subject, predicate, object });
    setIsEditing(false);
  };

  const handleCancel = () => {
    setDraft({
      subject: triple.subject || "",
      predicate: triple.predicate || "",
      object: triple.object || "",
    });
    setIsEditing(false);
  };

  return (
    <div
      className={`flex items-start gap-2 px-3 py-2 rounded mb-1 text-sm transition-opacity ${
        included ? "bg-gray-50" : "bg-gray-50 opacity-40"
      }`}
    >
      <input
        type="checkbox"
        checked={included}
        onChange={() => onToggle(triple.id)}
        className="mt-1 shrink-0 accent-blue-600 cursor-pointer"
      />
      <div className="flex-1 min-w-0">
        {isEditing ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <input
              type="text"
              value={draft.subject}
              onChange={(e) => setDraft((prev) => ({ ...prev, subject: e.target.value }))}
              placeholder="Subject"
              className="w-full text-sm border border-slate-300 rounded px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-300"
            />
            <input
              type="text"
              value={draft.predicate}
              onChange={(e) => setDraft((prev) => ({ ...prev, predicate: e.target.value }))}
              placeholder="Predicate"
              className="w-full text-sm border border-slate-300 rounded px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-300"
            />
            <input
              type="text"
              value={draft.object}
              onChange={(e) => setDraft((prev) => ({ ...prev, object: e.target.value }))}
              placeholder="Object"
              className="w-full text-sm border border-slate-300 rounded px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-300"
            />
          </div>
        ) : (
          <span className="flex flex-wrap gap-1.5 leading-relaxed">
            <Badge color="blue">{triple.subject}</Badge>
            <span className="text-gray-400">→</span>
            <Badge color="green">{triple.predicate}</Badge>
            <span className="text-gray-400">→</span>
            <Badge color="purple">{triple.object}</Badge>
          </span>
        )}
      </div>
      <div className="shrink-0 flex items-center gap-2 ml-2">
        {isEditing ? (
          <>
            <button
              onClick={handleSave}
              className="text-xs font-semibold text-blue-700 hover:text-blue-900"
            >
              Save
            </button>
            <button
              onClick={handleCancel}
              className="text-xs font-semibold text-slate-500 hover:text-slate-700"
            >
              Cancel
            </button>
          </>
        ) : (
          <>
            <button
              onClick={() => setIsEditing(true)}
              className="text-xs font-semibold text-slate-600 hover:text-slate-900"
            >
              Edit
            </button>
            <button
              onClick={() => onDelete(triple.id)}
              className="text-xs font-semibold text-red-600 hover:text-red-800"
            >
              Delete
            </button>
          </>
        )}
      </div>
    </div>
  );
}

// ── single sentence-group card ─────────────────────────────────────────────

function GroupCard({
  group,
  onChange,
  orderIndex,
  onInsertAbove,
  onInsertBelow,
  onMoveUp,
  onMoveDown,
  canMoveUp,
  canMoveDown,
  isDragging,
  isDropTarget,
  onDragStart,
  onDragEnd,
  onDragOver,
  onDrop,
}) {
  const [expanded, setExpanded] = useState(false);
  const [newTriple, setNewTriple] = useState({ subject: "", predicate: "", object: "" });

  const selectedVersion = group.rawVersions.find(
    (v) => v.version_id === group.selectedVersionId
  );
  const totalTriples = selectedVersion?.triples.length ?? 0;
  const includedCount = selectedVersion
    ? selectedVersion.triples.filter((t) => group.includedTripleIds.has(t.id)).length
    : 0;

  // ── handlers ──
  const handleInclude = () =>
    onChange({ ...group, included: !group.included });

  const handleTextChange = (e) =>
    onChange({ ...group, editedText: e.target.value });

  const handleVersionChange = (versionId) => {
    // Reset included triples to all triples of the newly selected version
    const newVersion = group.rawVersions.find((v) => v.version_id === versionId);
    const newIds = new Set(newVersion?.triples.map((t) => t.id) ?? []);
    onChange({ ...group, selectedVersionId: versionId, includedTripleIds: newIds });
  };

  const handleTripleToggle = (tripleId) => {
    const next = new Set(group.includedTripleIds);
    if (next.has(tripleId)) next.delete(tripleId);
    else next.add(tripleId);
    onChange({ ...group, includedTripleIds: next });
  };

  const handleSelectAll = () => {
    const newIds = new Set(selectedVersion?.triples.map((t) => t.id) ?? []);
    onChange({ ...group, includedTripleIds: newIds });
  };

  const handleDeselectAll = () =>
    onChange({ ...group, includedTripleIds: new Set() });

  const handleAddManualTriple = () => {
    const subject = (newTriple.subject || "").trim();
    const predicate = (newTriple.predicate || "").trim();
    const object = (newTriple.object || "").trim();

    if (!subject || !predicate || !object) {
      alert("Please fill subject, predicate, and object before adding a triple.");
      return;
    }

    const tripleId = `manual_${group.groupId}_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    const updatedVersions = group.rawVersions.map((v) =>
      v.version_id === group.selectedVersionId
        ? {
            ...v,
            triples: [
              ...v.triples,
              {
                id: tripleId,
                subject,
                predicate,
                object,
              },
            ],
          }
        : v
    );

    const nextIncludedIds = new Set(group.includedTripleIds);
    nextIncludedIds.add(tripleId);

    onChange({
      ...group,
      rawVersions: updatedVersions,
      includedTripleIds: nextIncludedIds,
    });

    setNewTriple({ subject: "", predicate: "", object: "" });
  };

  const handleUpdateTriple = (tripleId, payload) => {
    const updatedVersions = group.rawVersions.map((v) =>
      v.version_id === group.selectedVersionId
        ? {
            ...v,
            triples: v.triples.map((t) =>
              t.id === tripleId ? { ...t, ...payload } : t
            ),
          }
        : v
    );

    onChange({
      ...group,
      rawVersions: updatedVersions,
    });
  };

  const handleDeleteTriple = (tripleId) => {
    const updatedVersions = group.rawVersions.map((v) =>
      v.version_id === group.selectedVersionId
        ? {
            ...v,
            triples: v.triples.filter((t) => t.id !== tripleId),
          }
        : v
    );

    const nextIncludedIds = new Set(group.includedTripleIds);
    nextIncludedIds.delete(tripleId);

    onChange({
      ...group,
      rawVersions: updatedVersions,
      includedTripleIds: nextIncludedIds,
    });
  };

  const handleCardDragStart = (e) => {
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", String(group.groupId));
    onDragStart?.();
  };

  // ── status dot color ──
  const dot = group.included
    ? includedCount === totalTriples
      ? "bg-green-500"
      : includedCount === 0
      ? "bg-red-400"
      : "bg-amber-400"
    : "bg-gray-300";

  return (
    <div
      draggable
      onDragStart={handleCardDragStart}
      onDragEnd={onDragEnd}
      onDragOver={onDragOver}
      onDrop={onDrop}
      className={`border rounded-xl mb-3 overflow-hidden transition-all ${
        group.included ? "border-gray-200" : "border-gray-200 opacity-60"
      } ${
        isDropTarget ? "ring-2 ring-blue-300 border-blue-300" : ""
      } ${
        isDragging ? "opacity-50" : ""
      }`}
    >
      {/* ── header row ── */}
      <div className="flex items-center gap-3 px-4 py-3 bg-white">
        {/* include toggle */}
        <input
          type="checkbox"
          checked={group.included}
          onChange={handleInclude}
          title={group.included ? "Exclude this sentence" : "Include this sentence"}
          className="shrink-0 w-4 h-4 accent-blue-600 cursor-pointer"
        />

        {/* drag handle */}
        <span
          title="Drag this card to reorder sentence"
          className="shrink-0 cursor-grab active:cursor-grabbing text-xs text-gray-500 border border-gray-200 bg-white rounded px-1.5 py-0.5 hover:text-gray-700"
        >
          ::
        </span>

        {/* status dot */}
        <span className={`shrink-0 w-2.5 h-2.5 rounded-full ${dot}`} />

        {/* sentence text preview */}
        <span
          className="flex-1 text-sm text-gray-800 truncate cursor-pointer"
          onClick={() => setExpanded((x) => !x)}
          title={group.editedText || "(no sentence text detected)"}
        >
          <span className="text-gray-400 mr-2 font-mono text-xs">#{orderIndex + 1}</span>
          {group.editedText
            ? group.editedText.length > 100
              ? group.editedText.slice(0, 100) + "…"
              : group.editedText
            : <span className="italic text-gray-400">No sentence text — click to add</span>}
        </span>

        {/* meta badges */}
        <span className="shrink-0 text-xs text-gray-400">
          {group.rawVersions.length > 1 && (
            <span className="mr-2 bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded font-semibold">
              {group.rawVersions.length} versions
            </span>
          )}
          <span className="bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded">
            {includedCount}/{totalTriples} triples
          </span>
        </span>

        {/* expand toggle */}
        <button
          onClick={() => setExpanded((x) => !x)}
          className="shrink-0 text-gray-400 hover:text-gray-700 text-xs px-1"
          aria-label={expanded ? "Collapse" : "Expand"}
        >
          {expanded ? "▲" : "▼"}
        </button>
      </div>

      {/* ── expanded body ── */}
      {expanded && (
        <div className="border-t border-gray-100 bg-gray-50 px-4 py-4 space-y-4">

          {/* sentence text editor */}
          <div>
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
              Sentence text
            </label>
            <textarea
              value={group.editedText}
              onChange={handleTextChange}
              rows={3}
              placeholder="Type or edit the natural-language sentence for this group…"
              className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 resize-y focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
            <div className="mt-2 flex flex-wrap gap-2">
              <button
                onClick={onInsertAbove}
                className="text-xs bg-white border border-slate-300 text-slate-700 rounded px-2.5 py-1 hover:bg-slate-50"
              >
                + Insert sentence above
              </button>
              <button
                onClick={onInsertBelow}
                className="text-xs bg-white border border-slate-300 text-slate-700 rounded px-2.5 py-1 hover:bg-slate-50"
              >
                + Insert sentence below
              </button>
              <button
                onClick={onMoveUp}
                disabled={!canMoveUp}
                className="text-xs bg-white border border-slate-300 text-slate-700 rounded px-2.5 py-1 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                ↑ Move up
              </button>
              <button
                onClick={onMoveDown}
                disabled={!canMoveDown}
                className="text-xs bg-white border border-slate-300 text-slate-700 rounded px-2.5 py-1 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                ↓ Move down
              </button>
            </div>
          </div>

          {/* version picker (only shown when > 1 version) */}
          {group.rawVersions.length > 1 && (
            <div>
              <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                Choose version
              </label>
              <div className="flex flex-wrap gap-2">
                {group.rawVersions.map((v) => (
                  <button
                    key={v.version_id}
                    onClick={() => handleVersionChange(v.version_id)}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-all ${
                      group.selectedVersionId === v.version_id
                        ? "bg-blue-600 text-white border-blue-600"
                        : "bg-white text-gray-700 border-gray-300 hover:border-blue-400"
                    }`}
                  >
                    {v.version_label}
                    <span className="ml-1.5 text-xs opacity-75">({v.triples.length})</span>
                  </button>
                ))}
              </div>
              {/* show sentence candidate of selected version */}
              {selectedVersion?.sentence_candidate && (
                <p className="mt-2 text-xs text-gray-500 italic">
                  Col-7 text for this version: "{selectedVersion.sentence_candidate.slice(0, 120)}{selectedVersion.sentence_candidate.length > 120 ? "…" : ""}"
                </p>
              )}
            </div>
          )}

          {/* triples list */}
          {selectedVersion && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Triples ({includedCount} of {totalTriples} selected)
                </label>
                <div className="flex gap-2">
                  <button
                    onClick={handleSelectAll}
                    className="text-xs text-blue-600 hover:underline"
                  >
                    Select all
                  </button>
                  <span className="text-gray-300">|</span>
                  <button
                    onClick={handleDeselectAll}
                    className="text-xs text-red-500 hover:underline"
                  >
                    Deselect all
                  </button>
                </div>
              </div>

              {selectedVersion.triples.length === 0 ? (
                <p className="text-sm italic text-gray-400">No triples in this version.</p>
              ) : (
                <div>
                  {selectedVersion.triples.map((t) => (
                    <TripleRow
                      key={t.id}
                      triple={t}
                      included={group.includedTripleIds.has(t.id)}
                      onToggle={handleTripleToggle}
                      onSaveEdit={handleUpdateTriple}
                      onDelete={handleDeleteTriple}
                    />
                  ))}
                </div>
              )}

              <div className="mt-3 rounded-lg border border-blue-200 bg-blue-50 p-3 space-y-2">
                <label className="block text-xs font-semibold text-blue-700 uppercase tracking-wide">
                  Add manual triple
                </label>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                  <input
                    type="text"
                    value={newTriple.subject}
                    onChange={(e) => setNewTriple((prev) => ({ ...prev, subject: e.target.value }))}
                    placeholder="Subject"
                    className="w-full text-sm border border-blue-200 rounded px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-300"
                  />
                  <input
                    type="text"
                    value={newTriple.predicate}
                    onChange={(e) => setNewTriple((prev) => ({ ...prev, predicate: e.target.value }))}
                    placeholder="Predicate"
                    className="w-full text-sm border border-blue-200 rounded px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-300"
                  />
                  <input
                    type="text"
                    value={newTriple.object}
                    onChange={(e) => setNewTriple((prev) => ({ ...prev, object: e.target.value }))}
                    placeholder="Object"
                    className="w-full text-sm border border-blue-200 rounded px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-300"
                  />
                </div>
                <div className="flex justify-end">
                  <button
                    onClick={handleAddManualTriple}
                    className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-blue-600 text-white hover:bg-blue-700 transition-colors"
                  >
                    + Add Triple
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── main export ────────────────────────────────────────────────────────────

export default function ReviewStep({ uploadData, onConfirm, onReset }) {
  const { session_id, source_filename, uploaded_at, sentence_groups, manual_mode } = uploadData;
  const isManualMode = !!manual_mode;
  const [draggingGroupId, setDraggingGroupId] = useState(null);
  const [dragOverGroupId, setDragOverGroupId] = useState(null);
  const [publishing, setPublishing] = useState(false);
  const [publishError, setPublishError] = useState("");

  // Initialise mutable group state from the upload payload
  const [groups, setGroups] = useState(() =>
    sentence_groups.map((g) => {
      const firstVersion = g.versions[0];
      return {
        groupId: g.group_id,
        included: true,
        editedText: g.sentence_text,
        selectedVersionId: g.selected_version_id,
        // Start with all triples of the first/default version selected
        includedTripleIds: new Set(firstVersion?.triples.map((t) => t.id) ?? []),
        rawVersions: g.versions,
      };
    })
  );

  // ── bulk actions ──
  const handleIncludeAll = () =>
    setGroups((prev) => prev.map((g) => ({ ...g, included: true })));

  const handleExcludeAll = () =>
    setGroups((prev) => prev.map((g) => ({ ...g, included: false })));

  const handleGroupChange = useCallback((updated) => {
    setGroups((prev) =>
      prev.map((g) => (g.groupId === updated.groupId ? updated : g))
    );
  }, []);

  const insertSentenceGroupAt = useCallback((targetIndex) => {
    setGroups((prev) => {
      const nextGroupId = prev.reduce((max, g) => Math.max(max, Number(g.groupId) || 0), 0) + 1;
      const index = Math.max(0, Math.min(targetIndex, prev.length));
      const next = [...prev];
      next.splice(index, 0, createEmptyManualGroup(nextGroupId));
      return next;
    });
  }, []);

  const moveSentenceGroup = useCallback((fromIndex, toIndex) => {
    setGroups((prev) => {
      if (
        fromIndex < 0 ||
        toIndex < 0 ||
        fromIndex >= prev.length ||
        toIndex >= prev.length ||
        fromIndex === toIndex
      ) {
        return prev;
      }
      const next = [...prev];
      const [moved] = next.splice(fromIndex, 1);
      next.splice(toIndex, 0, moved);
      return next;
    });
  }, []);

  const reorderSentenceGroups = useCallback((fromGroupId, toGroupId) => {
    setGroups((prev) => {
      const fromIndex = prev.findIndex((g) => g.groupId === fromGroupId);
      const toIndex = prev.findIndex((g) => g.groupId === toGroupId);
      if (fromIndex < 0 || toIndex < 0 || fromIndex === toIndex) {
        return prev;
      }
      const next = [...prev];
      const [moved] = next.splice(fromIndex, 1);
      next.splice(toIndex, 0, moved);
      return next;
    });
  }, []);

  const handleDragStartGroup = useCallback((groupId) => {
    setDraggingGroupId(groupId);
    setDragOverGroupId(groupId);
  }, []);

  const handleDragOverGroup = useCallback((groupId, e) => {
    e.preventDefault();
    if (draggingGroupId == null || draggingGroupId === groupId) {
      return;
    }
    setDragOverGroupId(groupId);
  }, [draggingGroupId]);

  const handleDropOnGroup = useCallback((groupId, e) => {
    e.preventDefault();
    if (draggingGroupId == null) {
      return;
    }
    if (draggingGroupId !== groupId) {
      reorderSentenceGroups(draggingGroupId, groupId);
    }
    setDraggingGroupId(null);
    setDragOverGroupId(null);
  }, [draggingGroupId, reorderSentenceGroups]);

  const handleDragEndGroup = useCallback(() => {
    setDraggingGroupId(null);
    setDragOverGroupId(null);
  }, []);

  const handleAddSentenceGroup = () => {
    insertSentenceGroupAt(groups.length);
  };

  // ── build final sentences array and proceed ──
  const handleProceed = async () => {
    const sentences = [];
    let sentId = 1;

    groups.forEach((g) => {
      if (!g.included) return;

      const selectedVersion = g.rawVersions.find(
        (v) => v.version_id === g.selectedVersionId
      );
      if (!selectedVersion) return;

      const triples = selectedVersion.triples
        .filter((t) => g.includedTripleIds.has(t.id))
        .map((t, i) => ({
          id: `${sentId}_${i + 1}`,
          subject: t.subject,
          predicate: t.predicate,
          object: t.object,
          grade: null,
        }));

      if (triples.length === 0) return;

      sentences.push({
        id: sentId,
        text: g.editedText || "(no sentence text)",
        suggestion: "",
        sentence_grade: null,
        completeness: null,
        external_relation: null,
        triples,
      });
      sentId++;
    });

    if (sentences.length === 0) {
      alert("No sentences selected. Please include at least one sentence with triples.");
      return;
    }

    setPublishError("");
    setPublishing(true);
    try {
      await onConfirm({
        session_id,
        source_filename,
        uploaded_at,
        manual_mode: isManualMode,
        total_sentences: sentences.length,
        sentences,
      });
    } catch (e) {
      const msg = e?.response?.data?.detail || e?.message || "Failed to publish file.";
      setPublishError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setPublishing(false);
    }
  };

  // ── stats ──
  const included = groups.filter((g) => g.included).length;
  const totalTriples = groups
    .filter((g) => g.included)
    .reduce((sum, g) => {
      const ver = g.rawVersions.find((v) => v.version_id === g.selectedVersionId);
      return sum + (ver ? [...g.includedTripleIds].filter((id) => ver.triples.some((t) => t.id === id)).length : 0);
    }, 0);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* ── top bar ── */}
      <div className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between sticky top-0 z-10 shadow-sm">
        <div>
          <h1 className="text-lg font-bold text-gray-900">{isManualMode ? "Manual Entry" : "Review & Publish"}</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {isManualMode
              ? `${source_filename || "Manual Entry"} — ${groups.length} sentence groups in your manual workspace`
              : `${source_filename} — ${groups.length} groups found`}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={onReset}
            className="text-sm text-gray-500 hover:text-gray-800 border border-gray-300 rounded-lg px-3 py-1.5"
          >
            {isManualMode ? "← Back" : "← Upload different file"}
          </button>
          <button
            onClick={handleProceed}
            disabled={publishing}
            className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold px-5 py-2 rounded-lg transition-colors"
          >
            {publishing
              ? "Publishing..."
              : `Publish (${included} sentences, ${totalTriples} triples)`}
          </button>
        </div>
      </div>

      {/* ── body ── */}
      <div className="max-w-4xl mx-auto px-6 py-6">

        {/* summary bar */}
        <div className="bg-white border border-gray-200 rounded-xl px-5 py-3 mb-5 flex flex-wrap items-center gap-4 text-sm">
          <span className="text-gray-600">
            <strong className="text-gray-900">{groups.length}</strong> sentence groups parsed
          </span>
          <span className="text-gray-600">
            <strong className="text-gray-900">{included}</strong> included
          </span>
          <span className="text-gray-600">
            <strong className="text-gray-900">{totalTriples}</strong> triples selected
          </span>
          <div className="ml-auto flex gap-2">
            <button
              onClick={handleAddSentenceGroup}
              className="text-xs bg-blue-50 text-blue-700 border border-blue-200 rounded px-2.5 py-1 hover:bg-blue-100"
            >
              + Add sentence
            </button>
            <button
              onClick={handleIncludeAll}
              className="text-xs bg-green-50 text-green-700 border border-green-200 rounded px-2.5 py-1 hover:bg-green-100"
            >
              ✓ Include all
            </button>
            <button
              onClick={handleExcludeAll}
              className="text-xs bg-red-50 text-red-600 border border-red-200 rounded px-2.5 py-1 hover:bg-red-100"
            >
              ✗ Exclude all
            </button>
          </div>
        </div>

        {/* instructions */}
        <div className="bg-white border border-blue-200 rounded-2xl px-4 sm:px-5 py-4 sm:py-5 mb-5 shadow-sm">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-blue-100 text-blue-700 text-xs font-bold">
              i
            </span>
            <p className="text-sm font-semibold text-slate-800">How to use this step</p>
          </div>
          <p className="mt-1 text-xs sm:text-sm text-slate-600 leading-relaxed">
            Follow this quick workflow to prepare your file before publishing.
          </p>

          <ol className="mt-3 space-y-2.5">
            <li className="flex items-start gap-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5">
              <span className="mt-0.5 inline-flex items-center justify-center w-5 h-5 rounded-full bg-blue-600 text-white text-[11px] font-bold">1</span>
              <p className="text-sm text-slate-700 leading-relaxed">Review each sentence group and include or exclude it with the checkbox.</p>
            </li>
            <li className="flex items-start gap-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5">
              <span className="mt-0.5 inline-flex items-center justify-center w-5 h-5 rounded-full bg-blue-600 text-white text-[11px] font-bold">2</span>
              <p className="text-sm text-slate-700 leading-relaxed">Click <strong>▼</strong> to expand, edit sentence text, and choose the best version.</p>
            </li>
            <li className="flex items-start gap-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5">
              <span className="mt-0.5 inline-flex items-center justify-center w-5 h-5 rounded-full bg-blue-600 text-white text-[11px] font-bold">3</span>
              <p className="text-sm text-slate-700 leading-relaxed">Toggle triples on or off, then add manual sentences or triples where needed.</p>
            </li>
            <li className="flex items-start gap-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5">
              <span className="mt-0.5 inline-flex items-center justify-center w-5 h-5 rounded-full bg-blue-600 text-white text-[11px] font-bold">4</span>
              <p className="text-sm text-slate-700 leading-relaxed">Use <strong>Insert sentence above/below</strong> or drag with <strong>::</strong> to reorder quickly.</p>
            </li>
            <li className="flex items-start gap-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5">
              <span className="mt-0.5 inline-flex items-center justify-center w-5 h-5 rounded-full bg-blue-600 text-white text-[11px] font-bold">5</span>
              <p className="text-sm text-slate-700 leading-relaxed">Click <strong>Publish</strong> when ready.</p>
            </li>
          </ol>

          <div className="mt-3 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs sm:text-sm text-emerald-800 leading-relaxed">
            Publishing returns you to the dashboard, and collaborators can grade this same shared file.
          </div>
        </div>

        {groups.length === 0 && (
          <div className="bg-white border border-dashed border-slate-300 rounded-xl p-5 mb-5 text-center">
            <p className="text-sm font-semibold text-slate-700">No sentences yet</p>
            <p className="text-xs text-slate-500 mt-1">
              Click <strong>+ Add sentence</strong> to create your first sentence group, then add triples.
            </p>
          </div>
        )}

        {/* group cards */}
        {groups.map((g, index) => (
          <GroupCard
            key={g.groupId}
            group={g}
            orderIndex={index}
            onChange={handleGroupChange}
            onInsertAbove={() => insertSentenceGroupAt(index)}
            onInsertBelow={() => insertSentenceGroupAt(index + 1)}
            onMoveUp={() => moveSentenceGroup(index, index - 1)}
            onMoveDown={() => moveSentenceGroup(index, index + 1)}
            canMoveUp={index > 0}
            canMoveDown={index < groups.length - 1}
            isDragging={draggingGroupId === g.groupId}
            isDropTarget={
              draggingGroupId != null &&
              dragOverGroupId === g.groupId &&
              draggingGroupId !== g.groupId
            }
            onDragStart={() => handleDragStartGroup(g.groupId)}
            onDragEnd={handleDragEndGroup}
            onDragOver={(e) => handleDragOverGroup(g.groupId, e)}
            onDrop={(e) => handleDropOnGroup(g.groupId, e)}
          />
        ))}

        {/* bottom proceed button */}
        <div className="mt-6 flex justify-end">
          <button
            onClick={handleProceed}
            disabled={publishing}
            className="bg-blue-600 hover:bg-blue-700 text-white font-semibold px-8 py-3 rounded-xl text-sm transition-colors"
          >
            {publishing
              ? "Publishing..."
              : "Publish"}
          </button>
        </div>
        {publishError && (
          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
            ⚠ {publishError}
          </div>
        )}
      </div>
    </div>
  );
}
