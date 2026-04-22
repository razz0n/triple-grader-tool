// ReviewStep.jsx — Pre-grading review and cleaning step.
// Lets the user inspect every parsed sentence group, select which version
// of triples to use, edit the sentence text, and toggle individual triples
// on/off before proceeding to grading.

import { useState, useCallback } from "react";

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

function TripleRow({ triple, included, onToggle }) {
  return (
    <div
      className={`flex items-start gap-2 px-3 py-1.5 rounded mb-1 text-sm transition-opacity ${
        included ? "bg-gray-50" : "bg-gray-50 opacity-40"
      }`}
    >
      <input
        type="checkbox"
        checked={included}
        onChange={() => onToggle(triple.id)}
        className="mt-1 shrink-0 accent-blue-600 cursor-pointer"
      />
      <span className="flex flex-wrap gap-1.5 leading-relaxed">
        <Badge color="blue">{triple.subject}</Badge>
        <span className="text-gray-400">→</span>
        <Badge color="green">{triple.predicate}</Badge>
        <span className="text-gray-400">→</span>
        <Badge color="purple">{triple.object}</Badge>
      </span>
    </div>
  );
}

// ── single sentence-group card ─────────────────────────────────────────────

function GroupCard({ group, onChange }) {
  const [expanded, setExpanded] = useState(false);

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
      className={`border rounded-xl mb-3 overflow-hidden transition-all ${
        group.included ? "border-gray-200" : "border-gray-200 opacity-60"
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

        {/* status dot */}
        <span className={`shrink-0 w-2.5 h-2.5 rounded-full ${dot}`} />

        {/* sentence text preview */}
        <span
          className="flex-1 text-sm text-gray-800 truncate cursor-pointer"
          onClick={() => setExpanded((x) => !x)}
          title={group.editedText || "(no sentence text detected)"}
        >
          <span className="text-gray-400 mr-2 font-mono text-xs">#{group.groupId}</span>
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
                    />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── main export ────────────────────────────────────────────────────────────

export default function ReviewStep({ uploadData, onConfirm, onReset }) {
  const { session_id, source_filename, uploaded_at, sentence_groups } = uploadData;

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

  // ── build final sentences array and proceed ──
  const handleProceed = () => {
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
        triples,
      });
      sentId++;
    });

    if (sentences.length === 0) {
      alert("No sentences selected. Please include at least one sentence with triples.");
      return;
    }

    onConfirm({
      session_id,
      source_filename,
      uploaded_at,
      total_sentences: sentences.length,
      sentences,
    });
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
          <h1 className="text-lg font-bold text-gray-900">Review & Clean</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {source_filename} — {groups.length} groups found
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={onReset}
            className="text-sm text-gray-500 hover:text-gray-800 border border-gray-300 rounded-lg px-3 py-1.5"
          >
            ← Upload different file
          </button>
          <button
            onClick={handleProceed}
            className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold px-5 py-2 rounded-lg transition-colors"
          >
            Start Grading ({included} sentences, {totalTriples} triples) →
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
        <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 mb-5 text-sm text-blue-800">
          <strong>How to use:</strong> Check each sentence group below. Use the checkbox to include/exclude it.
          Click <strong>▼</strong> to expand and edit the sentence text, choose a version (if multiple were detected),
          and toggle individual triples on/off. When ready, click <strong>Start Grading</strong>.
        </div>

        {/* group cards */}
        {groups.map((g) => (
          <GroupCard key={g.groupId} group={g} onChange={handleGroupChange} />
        ))}

        {/* bottom proceed button */}
        <div className="mt-6 flex justify-end">
          <button
            onClick={handleProceed}
            className="bg-blue-600 hover:bg-blue-700 text-white font-semibold px-8 py-3 rounded-xl text-sm transition-colors"
          >
            Start Grading ({included} sentences) →
          </button>
        </div>
      </div>
    </div>
  );
}
