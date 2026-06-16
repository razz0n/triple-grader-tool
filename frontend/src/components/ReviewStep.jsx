import { useState, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowLeft,
  Check,
  ChevronDown,
  ChevronUp,
  MoveUp,
  MoveDown,
  Plus,
  Trash2,
  Play,
  Info,
  GripVertical,
  Edit2,
  X,
  AlertCircle,
  HelpCircle,
  FolderOpen
} from "lucide-react";

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

function Badge({ color, children }) {
  const colors = {
    blue:   "bg-indigo-50/70 border border-indigo-100 text-indigo-700 dark:bg-indigo-950/40 dark:border-indigo-900/50 dark:text-indigo-300",
    green:  "bg-emerald-50/70 border border-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:border-emerald-900/50 dark:text-emerald-300",
    purple: "bg-purple-50/70 border border-purple-100 text-purple-700 dark:bg-purple-950/40 dark:border-purple-900/50 dark:text-purple-300",
    gray:   "bg-slate-100 border border-slate-200 text-slate-700 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-400",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-lg text-xs font-semibold tracking-wide ${colors[color] ?? colors.gray}`}>
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
      className={`flex flex-col md:flex-row md:items-center justify-between gap-3 p-3 rounded-xl border mb-2 transition-all ${
        included
          ? "bg-slate-50 dark:bg-slate-900/50 border-slate-200 dark:border-slate-800"
          : "bg-slate-50 dark:bg-slate-900/50 border-slate-200 dark:border-slate-800 opacity-40"
      }`}
    >
      <div className="flex items-start gap-2.5 flex-1 min-w-0">
        <input
          type="checkbox"
          checked={included}
          onChange={() => onToggle(triple.id)}
          className="mt-1 shrink-0 accent-indigo-600 dark:accent-indigo-500 cursor-pointer w-4 h-4"
        />
        <div className="flex-1 min-w-0">
          {isEditing ? (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <input
                type="text"
                value={draft.subject}
                onChange={(e) => setDraft((prev) => ({ ...prev, subject: e.target.value }))}
                placeholder="Subject"
                className="w-full text-xs border border-slate-200 dark:border-slate-800 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:bg-slate-950 dark:text-white"
              />
              <input
                type="text"
                value={draft.predicate}
                onChange={(e) => setDraft((prev) => ({ ...prev, predicate: e.target.value }))}
                placeholder="Predicate"
                className="w-full text-xs border border-slate-200 dark:border-slate-800 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:bg-slate-950 dark:text-white"
              />
              <input
                type="text"
                value={draft.object}
                onChange={(e) => setDraft((prev) => ({ ...prev, object: e.target.value }))}
                placeholder="Object"
                className="w-full text-xs border border-slate-200 dark:border-slate-800 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:bg-slate-950 dark:text-white"
              />
            </div>
          ) : (
            <span className="flex flex-wrap items-center gap-1.5 leading-relaxed">
              <Badge color="blue">{triple.subject}</Badge>
              <span className="text-slate-400 font-semibold">&rarr;</span>
              <Badge color="green">{triple.predicate}</Badge>
              <span className="text-slate-400 font-semibold">&rarr;</span>
              <Badge color="purple">{triple.object}</Badge>
            </span>
          )}
        </div>
      </div>

      <div className="shrink-0 flex items-center justify-end gap-2 pl-6 sm:pl-0">
        {isEditing ? (
          <>
            <button
              onClick={handleSave}
              className="text-xs font-bold text-indigo-600 dark:text-indigo-400 hover:underline cursor-pointer"
            >
              Save
            </button>
            <button
              onClick={handleCancel}
              className="text-xs font-bold text-slate-500 hover:underline cursor-pointer"
            >
              Cancel
            </button>
          </>
        ) : (
          <>
            <button
              onClick={() => setIsEditing(true)}
              className="p-1 rounded-lg text-slate-450 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
              title="Edit Triple"
            >
              <Edit2 size={13} />
            </button>
            <button
              onClick={() => onDelete(triple.id)}
              className="p-1 rounded-lg text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/20 transition-colors cursor-pointer"
              title="Delete Triple"
            >
              <Trash2 size={13} />
            </button>
          </>
        )}
      </div>
    </div>
  );
}

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

  const handleInclude = () => onChange({ ...group, included: !group.included });
  const handleTextChange = (e) => onChange({ ...group, editedText: e.target.value });

  const handleVersionChange = (versionId) => {
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

  const handleDeselectAll = () => onChange({ ...group, includedTripleIds: new Set() });

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
              { id: tripleId, subject, predicate, object },
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

    onChange({ ...group, rawVersions: updatedVersions });
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

  const dot = group.included
    ? includedCount === totalTriples
      ? "bg-emerald-500"
      : includedCount === 0
      ? "bg-rose-500"
      : "bg-amber-500"
    : "bg-slate-350 dark:bg-slate-700";

  return (
    <div
      draggable
      onDragStart={handleCardDragStart}
      onDragEnd={onDragEnd}
      onDragOver={onDragOver}
      onDrop={onDrop}
      className={`border rounded-2xl mb-4 overflow-hidden transition-all duration-200 bg-white dark:bg-slate-900 ${
        group.included
          ? "border-slate-200 dark:border-slate-800 shadow-sm"
          : "border-slate-200 dark:border-slate-800 opacity-60"
      } ${
        isDropTarget ? "ring-2 ring-indigo-500 border-indigo-500 dark:ring-indigo-400" : ""
      } ${
        isDragging ? "opacity-30 scale-98" : ""
      }`}
    >
      {/* Header Row */}
      <div className="flex items-center gap-3.5 px-4.5 py-4 bg-white dark:bg-slate-900 select-none">
        <input
          type="checkbox"
          checked={group.included}
          onChange={handleInclude}
          title={group.included ? "Exclude this sentence" : "Include this sentence"}
          className="shrink-0 w-4.5 h-4.5 accent-indigo-650 dark:accent-indigo-500 cursor-pointer rounded-lg"
        />

        <div
          title="Drag to reorder sentence"
          className="shrink-0 cursor-grab active:cursor-grabbing p-1.5 rounded-lg border border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-400"
        >
          <GripVertical size={14} />
        </div>

        <span className={`shrink-0 w-2.5 h-2.5 rounded-full ${dot}`} />

        <span
          className="flex-1 text-xs sm:text-sm font-semibold text-slate-700 dark:text-slate-200 truncate cursor-pointer"
          onClick={() => setExpanded((x) => !x)}
          title={group.editedText || "(no sentence text detected)"}
        >
          <span className="text-slate-400 dark:text-slate-500 mr-2 font-mono text-[10px]">#{orderIndex + 1}</span>
          {group.editedText ? (
            group.editedText
          ) : (
            <span className="italic text-slate-450">No sentence text — click to expand and write</span>
          )}
        </span>

        <span className="shrink-0 text-[10px] font-bold text-slate-500 flex items-center gap-2">
          {group.rawVersions.length > 1 && (
            <span className="bg-amber-50 dark:bg-amber-950/20 text-amber-700 dark:text-amber-400 border border-amber-100 dark:border-amber-900/30 px-2 py-0.5 rounded-lg">
              {group.rawVersions.length} Versions
            </span>
          )}
          <span className="bg-indigo-50 dark:bg-indigo-950/20 text-indigo-700 dark:text-indigo-400 border border-indigo-100 dark:border-indigo-900/30 px-2 py-0.5 rounded-lg">
            {includedCount}/{totalTriples} Triples
          </span>
        </span>

        <button
          onClick={() => setExpanded((x) => !x)}
          className="shrink-0 p-1.5 rounded-lg border border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-850 text-slate-450 transition-colors"
          aria-label={expanded ? "Collapse" : "Expand"}
        >
          {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>
      </div>

      {/* Expanded Card Body */}
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="border-t border-slate-100 dark:border-slate-800/80 bg-slate-50/50 dark:bg-slate-950/30 p-5 space-y-5"
          >
            {/* Sentence text area */}
            <div className="space-y-1">
              <label className="block text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
                Sentence text
              </label>
              <textarea
                value={group.editedText}
                onChange={handleTextChange}
                rows={3}
                placeholder="Write the natural-language sentence representing this group..."
                className="w-full text-xs border border-slate-200 dark:border-slate-800 rounded-xl px-3.5 py-2.5 resize-y focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:bg-slate-900 dark:text-white leading-relaxed"
              />
              <div className="flex flex-wrap gap-2 pt-1">
                <button
                  onClick={onInsertAbove}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-350 text-[10px] font-bold transition-all cursor-pointer"
                >
                  <Plus size={11} /> Insert Above
                </button>
                <button
                  onClick={onInsertBelow}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-350 text-[10px] font-bold transition-all cursor-pointer"
                >
                  <Plus size={11} /> Insert Below
                </button>
                <button
                  onClick={onMoveUp}
                  disabled={!canMoveUp}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-350 text-[10px] font-bold transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <MoveUp size={11} /> Move Up
                </button>
                <button
                  onClick={onMoveDown}
                  disabled={!canMoveDown}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-350 text-[10px] font-bold transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <MoveDown size={11} /> Move Down
                </button>
              </div>
            </div>

            {/* Version picker (only shown when multiple versions exist) */}
            {group.rawVersions.length > 1 && (
              <div className="space-y-1">
                <label className="block text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider mb-2">
                  Choose Triples Generation Source Version
                </label>
                <div className="flex flex-wrap gap-2">
                  {group.rawVersions.map((v) => (
                    <button
                      key={v.version_id}
                      onClick={() => handleVersionChange(v.version_id)}
                      className={`px-3.5 py-2 rounded-xl text-xs font-bold border transition-all cursor-pointer ${
                        group.selectedVersionId === v.version_id
                          ? "bg-indigo-600 text-white border-indigo-650 shadow-sm"
                          : "bg-white dark:bg-slate-900 text-slate-650 dark:text-slate-300 border-slate-200 dark:border-slate-800 hover:border-indigo-400"
                      }`}
                    >
                      {v.version_label}
                      <span className="ml-1 text-[10px] opacity-75 font-semibold">({v.triples.length})</span>
                    </button>
                  ))}
                </div>
                {selectedVersion?.sentence_candidate && (
                  <p className="text-[10px] text-slate-400 dark:text-slate-500 italic mt-1.5">
                    Original Source sentence text: "{selectedVersion.sentence_candidate.slice(0, 110)}
                    {selectedVersion.sentence_candidate.length > 110 ? "..." : ""}"
                  </p>
                )}
              </div>
            )}

            {/* Triples workspace list */}
            {selectedVersion && (
              <div className="space-y-2">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <label className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
                    Triples Selected ({includedCount} of {totalTriples})
                  </label>
                  <div className="flex gap-2 text-[10px] font-bold">
                    <button
                      onClick={handleSelectAll}
                      className="text-indigo-600 dark:text-indigo-450 hover:underline cursor-pointer"
                    >
                      Select All
                    </button>
                    <span className="text-slate-200 dark:text-slate-800">|</span>
                    <button
                      onClick={handleDeselectAll}
                      className="text-rose-600 dark:text-rose-455 hover:underline cursor-pointer"
                    >
                      Deselect All
                    </button>
                  </div>
                </div>

                {selectedVersion.triples.length === 0 ? (
                  <p className="text-xs italic text-slate-400 dark:text-slate-500 py-3">No triples in this version.</p>
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

                {/* Add new manual triple drawer */}
                <div className="rounded-xl border border-indigo-100 dark:border-indigo-900/30 bg-indigo-50/20 dark:bg-indigo-950/10 p-4 space-y-3 mt-4">
                  <label className="block text-[10px] font-bold text-indigo-750 dark:text-indigo-400 uppercase tracking-wider">
                    Add Manual Triple
                  </label>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                    <input
                      type="text"
                      value={newTriple.subject}
                      onChange={(e) => setNewTriple((prev) => ({ ...prev, subject: e.target.value }))}
                      placeholder="Subject"
                      className="w-full text-xs border border-indigo-150 dark:border-indigo-900/40 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:bg-slate-900 dark:text-white"
                    />
                    <input
                      type="text"
                      value={newTriple.predicate}
                      onChange={(e) => setNewTriple((prev) => ({ ...prev, predicate: e.target.value }))}
                      placeholder="Predicate"
                      className="w-full text-xs border border-indigo-150 dark:border-indigo-900/40 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:bg-slate-900 dark:text-white"
                    />
                    <input
                      type="text"
                      value={newTriple.object}
                      onChange={(e) => setNewTriple((prev) => ({ ...prev, object: e.target.value }))}
                      placeholder="Object"
                      className="w-full text-xs border border-indigo-150 dark:border-indigo-900/40 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:bg-slate-900 dark:text-white"
                    />
                  </div>
                  <div className="flex justify-end pt-1">
                    <button
                      onClick={handleAddManualTriple}
                      className="px-3.5 py-1.5 rounded-lg text-xs font-bold bg-indigo-650 hover:bg-indigo-700 text-white shadow-sm transition-all cursor-pointer flex items-center gap-1 active:scale-95"
                    >
                      <Plus size={12} /> Add Triple
                    </button>
                  </div>
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function ReviewStep({ uploadData, onConfirm, onReset }) {
  const { session_id, source_filename, uploaded_at, sentence_groups, manual_mode } = uploadData;
  const isManualMode = !!manual_mode;
  const [draggingGroupId, setDraggingGroupId] = useState(null);
  const [dragOverGroupId, setDragOverGroupId] = useState(null);
  const [publishing, setPublishing] = useState(false);
  const [publishError, setPublishError] = useState("");

  const [groups, setGroups] = useState(() =>
    sentence_groups.map((g) => {
      const firstVersion = g.versions[0];
      return {
        groupId: g.group_id,
        included: true,
        editedText: g.sentence_text,
        selectedVersionId: g.selected_version_id,
        includedTripleIds: new Set(firstVersion?.triples.map((t) => t.id) ?? []),
        rawVersions: g.versions,
      };
    })
  );

  const handleIncludeAll = () => setGroups((prev) => prev.map((g) => ({ ...g, included: true })));
  const handleExcludeAll = () => setGroups((prev) => prev.map((g) => ({ ...g, included: false })));

  const handleGroupChange = useCallback((updated) => {
    setGroups((prev) => prev.map((g) => (g.groupId === updated.groupId ? updated : g)));
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
    if (draggingGroupId == null || draggingGroupId === groupId) return;
    setDragOverGroupId(groupId);
  }, [draggingGroupId]);

  const handleDropOnGroup = useCallback((groupId, e) => {
    e.preventDefault();
    if (draggingGroupId == null) return;
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

  const handleAddSentenceGroup = () => insertSentenceGroupAt(groups.length);

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
      alert("Please select or add at least one sentence with triples before publishing.");
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
      const msg = e?.response?.data?.detail || e?.message || "Failed to publish session.";
      setPublishError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setPublishing(false);
    }
  };

  const included = groups.filter((g) => g.included).length;
  const totalTriples = groups
    .filter((g) => g.included)
    .reduce((sum, g) => {
      const ver = g.rawVersions.find((v) => v.version_id === g.selectedVersionId);
      return sum + (ver ? [...g.includedTripleIds].filter((id) => ver.triples.some((t) => t.id === id)).length : 0);
    }, 0);

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 transition-colors duration-300">
      {/* Top sticky bar */}
      <div className="bg-white/95 dark:bg-slate-900/95 backdrop-blur border-b border-slate-200 dark:border-slate-800 px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between sticky top-0 z-30 shadow-sm gap-4">
        <div>
          <h1 className="text-base sm:text-lg font-bold text-slate-800 dark:text-white flex items-center gap-2">
            <FolderOpen size={18} className="text-indigo-600 dark:text-indigo-400" />
            {isManualMode ? "Manual Entry Builder" : "Review & Publish Session"}
          </h1>
          <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5 max-w-[280px] sm:max-w-md truncate">
            {source_filename || "Manual Entry Workspace"} &bull; {groups.length} sentence group{groups.length === 1 ? "" : "s"}
          </p>
        </div>
        <div className="flex items-center gap-2.5 justify-end">
          <button
            onClick={onReset}
            className="inline-flex items-center gap-1 text-xs font-bold text-slate-500 dark:text-slate-300 hover:text-slate-800 dark:hover:text-white border border-slate-200 dark:border-slate-800 rounded-xl px-4 py-2 hover:bg-slate-50 dark:hover:bg-slate-800 cursor-pointer transition-all"
          >
            <ArrowLeft size={13} /> {isManualMode ? "Back" : "Re-upload File"}
          </button>
          <button
            onClick={handleProceed}
            disabled={publishing}
            className="inline-flex items-center gap-1.5 bg-indigo-650 hover:bg-indigo-700 disabled:bg-indigo-800/50 text-white text-xs font-bold px-4.5 py-2.5 rounded-xl transition-all shadow-sm active:scale-95 cursor-pointer disabled:cursor-not-allowed"
          >
            {publishing ? (
              <>
                <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Publishing...</span>
              </>
            ) : (
              <>
                <Play size={13} />
                <span>Publish ({included} Sentences)</span>
              </>
            )}
          </button>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-6 py-6">
        {/* Bulk Action Controls */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl px-5 py-3 mb-5 flex flex-wrap items-center gap-4 text-xs">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-slate-500 dark:text-slate-400 font-semibold">
              <strong className="text-slate-800 dark:text-white">{groups.length}</strong> Groups parsed
            </span>
            <span className="text-slate-300 dark:text-slate-800">|</span>
            <span className="text-slate-500 dark:text-slate-400 font-semibold">
              <strong className="text-slate-800 dark:text-white">{included}</strong> Included
            </span>
            <span className="text-slate-300 dark:text-slate-800">|</span>
            <span className="text-slate-500 dark:text-slate-400 font-semibold">
              <strong className="text-slate-800 dark:text-white">{totalTriples}</strong> Triples Selected
            </span>
          </div>

          <div className="sm:ml-auto flex gap-2 flex-wrap pt-2 sm:pt-0">
            <button
              onClick={handleAddSentenceGroup}
              className="px-2.5 py-1 text-[10px] font-bold border border-indigo-200 dark:border-indigo-900 bg-indigo-50/50 dark:bg-indigo-950/20 text-indigo-700 dark:text-indigo-400 rounded-lg hover:bg-indigo-100/60 dark:hover:bg-indigo-900/40 cursor-pointer transition-all"
            >
              + Add Sentence
            </button>
            <button
              onClick={handleIncludeAll}
              className="px-2.5 py-1 text-[10px] font-bold border border-emerald-250 dark:border-emerald-900 bg-emerald-50/50 dark:bg-emerald-950/20 text-emerald-700 dark:text-emerald-400 rounded-lg hover:bg-emerald-100/60 dark:hover:bg-emerald-900/40 cursor-pointer transition-all"
            >
              ✓ Include All
            </button>
            <button
              onClick={handleExcludeAll}
              className="px-2.5 py-1 text-[10px] font-bold border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-slate-600 dark:text-slate-400 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 cursor-pointer transition-all"
            >
              ✗ Exclude All
            </button>
          </div>
        </div>

        {/* Structured Instructions Panel */}
        <div className="bg-white dark:bg-slate-900 border border-indigo-100 dark:border-indigo-950 rounded-2xl p-5 mb-5 shadow-sm space-y-4">
          <div className="flex items-center gap-2">
            <div className="inline-flex items-center justify-center w-6 h-6 rounded-xl bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400">
              <HelpCircle size={15} />
            </div>
            <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200">How to Prepare Your Worksheet</h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
            {[
              { num: 1, text: "Review parsed sentence lists and select which items to include in grading." },
              { num: 2, text: "Expand individual sentences to edit text or choose alternative NLP triple models." },
              { num: 3, text: "Fine-tune triples: edit parts of speech, toggle items, or delete redundant relations." },
              { num: 4, text: "Insert custom sentences/triples manually and use drag handles to reorder." },
              { num: 5, text: "Click Publish to compile the final session and share it for grading." }
            ].map((step, idx) => (
              <div key={idx} className="flex gap-2.5 border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/20 rounded-xl p-3">
                <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-indigo-600 dark:bg-indigo-500 text-white text-[9px] font-bold shrink-0">
                  {step.num}
                </span>
                <p className="text-[10px] sm:text-xs text-slate-500 dark:text-slate-400 leading-normal">{step.text}</p>
              </div>
            ))}
          </div>

          <div className="p-3 bg-emerald-50/50 dark:bg-emerald-950/20 border border-emerald-250 dark:border-emerald-900/30 text-[10px] sm:text-xs text-emerald-800 dark:text-emerald-400 rounded-xl font-medium">
            Note: Publishing saves the structured layout to the database. All graders will work from this master version.
          </div>
        </div>

        {/* Empty state alert */}
        {groups.length === 0 && (
          <div className="bg-white dark:bg-slate-900 border border-dashed border-slate-300 dark:border-slate-800 rounded-2xl p-8 mb-5 text-center flex flex-col items-center justify-center gap-2">
            <FolderOpen size={28} className="text-slate-350" />
            <p className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wide">No sentences added yet</p>
            <p className="text-[11px] text-slate-450 dark:text-slate-500">
              Click <strong className="text-indigo-600 dark:text-indigo-400 cursor-pointer" onClick={handleAddSentenceGroup}>+ Add Sentence</strong> to start build manual entry triples.
            </p>
          </div>
        )}

        {/* Groups Cards List */}
        <div className="space-y-1">
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
        </div>

        {/* Bottom actions */}
        <div className="mt-6 flex justify-end">
          <button
            onClick={handleProceed}
            disabled={publishing}
            className="bg-indigo-650 hover:bg-indigo-700 disabled:bg-indigo-850 text-white font-bold px-6 py-2.5 rounded-xl text-xs shadow-sm transition-all cursor-pointer inline-flex items-center gap-1 active:scale-95"
          >
            <Play size={13} /> Publish Session
          </button>
        </div>

        {publishError && (
          <div className="mt-4 p-3 bg-rose-50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-900/30 rounded-xl text-xs text-rose-800 dark:text-rose-350 flex items-start gap-2">
            <AlertCircle size={15} className="shrink-0 mt-0.5" />
            <span>{publishError}</span>
          </div>
        )}
      </div>
    </div>
  );
}
