import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen,
  Clock3,
  Eye,
  FileClock,
  HardDrive,
  Play,
  Plus,
  RefreshCw,
  Save,
  ServerCog,
  Trash2,
} from "lucide-react";
import {
  applyScheduledPromptMemoryProposal,
  createScheduledPrompt,
  deleteScheduledPrompt,
  getAuthStatus,
  getNightlyScheduledPromptTemplate,
  getScheduledPromptMemoryProposals,
  getScheduledPromptPeripheryArtifact,
  getScheduledPromptPeripheryArtifacts,
  getScheduledPromptPeripherySnapshot,
  getScheduledPrompts,
  getVariables,
  manualRunScheduledPrompt,
  renderVariables,
  refreshScheduledPromptPeripherySnapshot,
  updateScheduledPrompt,
} from "../api";
import type {
  ScheduledPrompt,
  ScheduledPromptMemoryProposal,
  ScheduledPromptTemplate,
} from "../types";

export function ScheduledPromptsPanel({
  onLog,
  selectedScheduledPromptId = "",
  scheduledPrompts,
  newRequestNonce = 0,
  objectMode = false,
  onSelectScheduledPrompt,
}: {
  onLog: (message: string) => void;
  selectedScheduledPromptId?: string;
  scheduledPrompts?: ScheduledPrompt[];
  newRequestNonce?: number;
  objectMode?: boolean;
  onSelectScheduledPrompt?: (id: string) => void;
}) {
  const queryClient = useQueryClient();
  const authQuery = useQuery({
    queryKey: ["authStatus"],
    queryFn: getAuthStatus,
  });
  const variablesQuery = useQuery({
    queryKey: ["variables"],
    queryFn: getVariables,
    enabled: Boolean(authQuery.data?.admin),
  });
  const templateQuery = useQuery({
    queryKey: ["scheduledPromptTemplate", "nightly-subconscious"],
    queryFn: getNightlyScheduledPromptTemplate,
    enabled: Boolean(authQuery.data?.admin),
  });
  const schedulesQuery = useQuery({
    queryKey: ["scheduledPrompts"],
    queryFn: getScheduledPrompts,
    enabled: Boolean(authQuery.data?.admin),
    refetchInterval: 10_000,
  });
  const schedules =
    scheduledPrompts ?? schedulesQuery.data?.scheduledPrompts ?? [];
  const [selectedId, setSelectedId] = useState<string>("");
  const selected =
    schedules.find((item) => item.id === selectedId) ??
    (objectMode ? undefined : schedules[0]);
  const isUserLevelSchedule = selected?.sourceKind === "user_schedule";
  const supportsWorkbenchVariables = !isUserLevelSchedule;
  const [draft, setDraft] = useState<EditorDraft>(() =>
    draftFromPrompt(selected),
  );
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const handledNewRequestNonce = useRef(0);
  const [cursor, setCursor] = useState(0);
  const [scheduleTouched, setScheduleTouched] = useState(false);
  const [artifactDetailId, setArtifactDetailId] = useState("");

  useEffect(() => {
    if (selectedId && !selected) return;
    const next = draftFromPrompt(selected, templateQuery.data);
    setDraft((current) => {
      if (selected && current.id === selected.id) {
        return {
          ...current,
          scheduleType: next.scheduleType,
          time: next.time,
          timezone: next.timezone,
          active: next.active,
          memoryWriteMode: next.memoryWriteMode,
          executor: next.executor,
          conversationPolicy: next.conversationPolicy,
          glasshiveWorkerStrategy: next.glasshiveWorkerStrategy,
        };
      }
      return next;
    });
  }, [
    selected?.id,
    selected?.active,
    selected?.memoryWriteMode,
    selected?.executor,
    selected?.conversationPolicy,
    selected?.glasshiveWorkerStrategy,
    selected?.schedule?.type,
    selected?.schedule?.time,
    selected?.schedule?.timezone,
    selectedId,
    templateQuery.data?.promptText,
  ]);

  useEffect(() => {
    if (selectedScheduledPromptId) {
      setSelectedId(selectedScheduledPromptId);
    }
  }, [selectedScheduledPromptId]);

  useEffect(() => {
    setScheduleTouched(false);
    setArtifactDetailId("");
  }, [selected?.id]);

  useEffect(() => {
    if (!newRequestNonce || newRequestNonce === handledNewRequestNonce.current)
      return;
    handledNewRequestNonce.current = newRequestNonce;
    setSelectedId("");
    setDraft(draftFromPrompt(undefined, templateQuery.data));
    setScheduleTouched(false);
  }, [newRequestNonce]);

  const previewQuery = useQuery({
    queryKey: [
      "scheduledPromptPreview",
      supportsWorkbenchVariables,
      draft.promptText,
    ],
    queryFn: () => renderVariables(draft.promptText),
    enabled: Boolean(
      authQuery.data?.admin &&
      supportsWorkbenchVariables &&
      draft.promptText.trim(),
    ),
  });
  const proposalsQuery = useQuery({
    queryKey: ["scheduledPromptMemoryProposals", selected?.id],
    queryFn: () => getScheduledPromptMemoryProposals(selected!.id),
    enabled: Boolean(
      authQuery.data?.admin &&
      selected?.id &&
      selected?.sourceKind === "workbench_definition",
    ),
    refetchInterval: 10_000,
  });
  const peripheryQuery = useQuery({
    queryKey: ["scheduledPromptPeripheryArtifacts", selected?.id],
    queryFn: () => getScheduledPromptPeripheryArtifacts(selected!.id),
    enabled: Boolean(
      authQuery.data?.admin &&
      selected?.id &&
      selected?.sourceKind === "workbench_definition",
    ),
    refetchInterval: 10_000,
  });
  const snapshotQuery = useQuery({
    queryKey: ["scheduledPromptPeripherySnapshot", selected?.id],
    queryFn: () => getScheduledPromptPeripherySnapshot(selected!.id),
    enabled: Boolean(
      authQuery.data?.admin &&
      selected?.id &&
      selected?.sourceKind === "workbench_definition",
    ),
    refetchInterval: 10_000,
  });
  const artifactDetailQuery = useQuery({
    queryKey: [
      "scheduledPromptPeripheryArtifact",
      selected?.id,
      artifactDetailId,
    ],
    queryFn: () =>
      getScheduledPromptPeripheryArtifact(selected!.id, artifactDetailId),
    enabled: Boolean(authQuery.data?.admin && selected?.id && artifactDetailId),
  });

  const saveMutation = useMutation({
    mutationFn: () => {
      const payload = draftPayload(draft, {
        includeSchedule: !isUserLevelSchedule || scheduleTouched,
        includeMemoryWriteMode: !isUserLevelSchedule,
      });
      return draft.id
        ? updateScheduledPrompt(draft.id, payload)
        : createScheduledPrompt(payload);
    },
    onSuccess: (item) => {
      setSelectedId(item.id);
      setDraft(draftFromPrompt(item, templateQuery.data));
      setScheduleTouched(false);
      onSelectScheduledPrompt?.(item.id);
      onLog(`Scheduled prompt ${item.title} saved.`);
      queryClient.invalidateQueries({ queryKey: ["scheduledPrompts"] });
      queryClient.invalidateQueries({ queryKey: ["scheduledPromptPreview"] });
    },
    onError: (error) => onLog(String(error)),
  });

  const toggleMutation = useMutation({
    mutationFn: (item: ScheduledPrompt) =>
      updateScheduledPrompt(item.id, { active: !item.active }),
    onSuccess: (item) => {
      onLog(`${item.title} is now ${item.active ? "enabled" : "disabled"}.`);
      queryClient.invalidateQueries({ queryKey: ["scheduledPrompts"] });
      queryClient.invalidateQueries({
        queryKey: ["scheduledPromptPeripheryArtifacts"],
      });
    },
    onError: (error) => onLog(String(error)),
  });

  const runMutation = useMutation({
    mutationFn: (item: ScheduledPrompt) =>
      manualRunScheduledPrompt(item.id, item.sourceKind === "user_schedule"),
    onSuccess: (_result, item) => {
      onLog(
        item.sourceKind === "user_schedule"
          ? "Manual Viventium schedule run started."
          : "Manual GlassHive run queued.",
      );
      queryClient.invalidateQueries({ queryKey: ["scheduledPrompts"] });
    },
    onError: (error) => onLog(String(error)),
  });
  const proposalMutation = useMutation({
    mutationFn: ({
      proposal,
      apply,
    }: {
      proposal: ScheduledPromptMemoryProposal;
      apply: boolean;
    }) =>
      applyScheduledPromptMemoryProposal(
        selected!.id,
        proposal.proposalId,
        apply,
      ),
    onSuccess: (result) => {
      onLog(
        result.applied
          ? "Governed memory proposal applied."
          : "Governed memory proposal dry-run completed.",
      );
      queryClient.invalidateQueries({
        queryKey: ["scheduledPromptMemoryProposals"],
      });
      queryClient.invalidateQueries({ queryKey: ["scheduledPrompts"] });
    },
    onError: (error) => onLog(String(error)),
  });
  const snapshotMutation = useMutation({
    mutationFn: () => refreshScheduledPromptPeripherySnapshot(selected!.id),
    onSuccess: () => {
      onLog("Private evidence snapshot refreshed.");
      queryClient.invalidateQueries({
        queryKey: ["scheduledPromptPeripherySnapshot"],
      });
      queryClient.invalidateQueries({ queryKey: ["scheduledPromptPreview"] });
    },
    onError: (error) => onLog(String(error)),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteScheduledPrompt(id),
    onSuccess: () => {
      setSelectedId("");
      setDraft(draftFromPrompt(undefined, templateQuery.data));
      onSelectScheduledPrompt?.("");
      onLog("Scheduled prompt deleted.");
      queryClient.invalidateQueries({ queryKey: ["scheduledPrompts"] });
    },
    onError: (error) => onLog(String(error)),
  });

  const tags = useMemo(
    () => [
      ...(variablesQuery.data?.variables ?? []).map((item) => item.name),
      ...(variablesQuery.data?.functions ?? []).map((item) => item.name),
    ],
    [variablesQuery.data],
  );
  const autocomplete = useMemo(
    () => variableAutocomplete(draft.promptText, cursor, tags),
    [draft.promptText, cursor, tags],
  );
  const previewError =
    previewQuery.error instanceof Error ? previewQuery.error.message : "";
  const updateDraft = (patch: Partial<EditorDraft>) =>
    setDraft((current) => ({ ...current, ...patch }));

  const insertVariable = (tag: string) => {
    const inserted = insertVariableAtCursor(
      draft.promptText,
      cursor,
      tag,
      autocomplete?.start,
    );
    updateDraft({ promptText: inserted.text });
    requestAnimationFrame(() => {
      textareaRef.current?.focus();
      textareaRef.current?.setSelectionRange(inserted.cursor, inserted.cursor);
      setCursor(inserted.cursor);
    });
  };
  const requestManualRun = () => {
    if (!selected) return;
    if (selected.sourceKind === "user_schedule") {
      const channel = Array.isArray(selected.channel)
        ? selected.channel.join(", ")
        : (selected.channel ?? "scheduler");
      const confirmed = window.confirm(
        `Run this Viventium-agent schedule now? It may deliver through ${channel}.`,
      );
      if (!confirmed) return;
    }
    runMutation.mutate(selected);
  };
  const currentExecutor =
    draft.executor || selected?.executor || "glasshive_host";

  if (authQuery.data && !authQuery.data.admin) {
    return (
      <div className="schedule-panel auth-locked">
        <FileClock size={28} />
        <strong>Admin authentication required</strong>
        <span>
          Open Workbench from the Viventium helper or sign in as a LibreChat
          admin.
        </span>
      </div>
    );
  }

  return (
    <div className={`schedule-panel ${objectMode ? "object-mode" : ""}`}>
      {!objectMode && (
        <div className="schedule-list-pane">
          <div className="schedule-panel-header">
            <div>
              <strong>Scheduled Prompts</strong>
              <span>GlassHive host runs via Scheduling Cortex</span>
            </div>
            <button
              className="toolbar-button compact"
              onClick={() => {
                setSelectedId("");
                setDraft(draftFromPrompt(undefined, templateQuery.data));
              }}
            >
              <Plus size={15} />
              New
            </button>
          </div>
          <div className="schedule-list">
            {schedules.map((item) => (
              <button
                key={item.id}
                className={`schedule-row ${item.id === draft.id ? "active" : ""}`}
                onClick={() => setSelectedId(item.id)}
              >
                <span
                  className={`schedule-toggle ${item.active ? "enabled" : ""}`}
                  onClick={(event) => {
                    event.stopPropagation();
                    toggleMutation.mutate(item);
                  }}
                />
                <span>
                  <strong>{item.title}</strong>
                  <small>
                    {item.nextRunAt
                      ? `Next ${formatDate(item.nextRunAt)}`
                      : "No next run"}{" "}
                    · {item.sourceLabel ?? "Scheduled prompt"}
                  </small>
                </span>
                <Clock3 size={15} />
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="schedule-editor-pane">
        {objectMode && (
          <div className="schedule-object-header">
            <div>
              <strong>
                {draft.id ? "Scheduled Prompt Object" : "New Scheduled Prompt"}
              </strong>
              <span>
                {draft.id
                  ? (selected?.sourceLabel ?? "Selected from Prompt Flow")
                  : "Private prompt stored in App Support state"}
              </span>
            </div>
            <button
              className="toolbar-button compact"
              onClick={() => {
                setSelectedId("");
                setDraft(draftFromPrompt(undefined, templateQuery.data));
              }}
            >
              <Plus size={15} />
              New
            </button>
          </div>
        )}
        {selected && (
          <div
            className="schedule-execution-card"
            data-executor={selected.executor ?? "viventium_agent"}
          >
            <div className="schedule-execution-heading">
              <ServerCog size={16} />
              <div>
                <strong>Execution</strong>
                <span>{executionLabel(selected)}</span>
              </div>
            </div>
            <div
              className="execution-route-toggle"
              aria-label="Execution route"
            >
              <span
                className={
                  selected.executor === "glasshive_host" ? "active" : ""
                }
              >
                GlassHive host
              </span>
              <span
                className={
                  (selected.executor ?? "viventium_agent") === "viventium_agent"
                    ? "active"
                    : ""
                }
              >
                Viventium agent
              </span>
            </div>
            <div className="execution-config-grid">
              <div>
                <span>Executor</span>
                <code>{selected.executor ?? "viventium_agent"}</code>
              </div>
              <div>
                <span>Channel</span>
                <code>
                  {Array.isArray(selected.channel)
                    ? selected.channel.join(", ")
                    : (selected.channel ?? "workbench")}
                </code>
              </div>
              <div>
                <span>Profile</span>
                <code>
                  {selected.executionProfile ??
                    (selected.executor === "glasshive_host"
                      ? "codex-cli"
                      : "main Viventium")}
                </code>
              </div>
              <div>
                <span>Mode</span>
                <code>
                  {selected.executionMode ??
                    (selected.executor === "glasshive_host"
                      ? "host local machine"
                      : "scheduler delivery")}
                </code>
              </div>
              {selected.executionModel && (
                <div>
                  <span>Model</span>
                  <code>{selected.executionModel}</code>
                </div>
              )}
              {selected.reasoningEffort && (
                <div>
                  <span>Requested effort</span>
                  <code>{selected.reasoningEffort}</code>
                </div>
              )}
              {selected.workspaceRoot && (
                <div className="wide">
                  <span>Workspace</span>
                  <code>{selected.workspaceRoot}</code>
                </div>
              )}
              {selected.myFolder && (
                <div className="wide">
                  <span>
                    <HardDrive size={12} /> Private my_folder
                  </span>
                  <code>{selected.myFolder}</code>
                </div>
              )}
            </div>
          </div>
        )}
        <div className="schedule-form-grid">
          {selected && (
            <div className="schedule-source-strip">
              <span>{selected.sourceLabel ?? "Scheduled prompt"}</span>
              <code>{selected.executor ?? "viventium_agent"}</code>
              <code>
                {Array.isArray(selected.channel)
                  ? selected.channel.join(", ")
                  : (selected.channel ?? "workbench")}
              </code>
            </div>
          )}
          <label>
            <span>Title</span>
            <input
              value={draft.title}
              onInput={(event) =>
                updateDraft({ title: event.currentTarget.value })
              }
              onChange={(event) => updateDraft({ title: event.target.value })}
            />
          </label>
          <label>
            <span>Executor</span>
            <select
              value={draft.executor}
              disabled={isUserLevelSchedule}
              onChange={(event) =>
                updateDraft({
                  executor: event.target.value as EditorDraft["executor"],
                })
              }
            >
              <option value="glasshive_host">GlassHive host</option>
              <option value="viventium_agent">Viventium agent</option>
            </select>
            {isUserLevelSchedule && <small>Existing route</small>}
          </label>
          {currentExecutor === "glasshive_host" ? (
            <label>
              <span>Worker</span>
              <select
                value={draft.glasshiveWorkerStrategy}
                disabled={isUserLevelSchedule}
                onChange={(event) =>
                  updateDraft({
                    glasshiveWorkerStrategy: event.target
                      .value as EditorDraft["glasshiveWorkerStrategy"],
                  })
                }
              >
                <option value="same_worker">Same worker</option>
                <option value="new_worker_each_run">New worker each run</option>
              </select>
            </label>
          ) : (
            <label>
              <span>Conversation</span>
              <select
                value={draft.conversationPolicy}
                disabled={isUserLevelSchedule}
                onChange={(event) =>
                  updateDraft({
                    conversationPolicy: event.target
                      .value as EditorDraft["conversationPolicy"],
                  })
                }
              >
                <option value="new">New conversation</option>
                <option value="same">Same conversation</option>
              </select>
            </label>
          )}
          <label>
            <span>Schedule</span>
            <select
              value={draft.scheduleType}
              onChange={(event) => {
                setScheduleTouched(true);
                updateDraft({
                  scheduleType: event.target
                    .value as EditorDraft["scheduleType"],
                });
              }}
            >
              <option value="daily">Daily</option>
              <option value="weekdays">Weekdays</option>
              <option value="weekly">Weekly</option>
              <option value="cron">Cron</option>
            </select>
          </label>
          <label>
            <span>Time</span>
            <input
              type="time"
              value={draft.time}
              onInput={(event) => {
                setScheduleTouched(true);
                updateDraft({ time: event.currentTarget.value });
              }}
              onChange={(event) => {
                setScheduleTouched(true);
                updateDraft({ time: event.target.value });
              }}
            />
          </label>
          <label>
            <span>Timezone</span>
            <input
              value={draft.timezone}
              onInput={(event) => {
                setScheduleTouched(true);
                updateDraft({ timezone: event.currentTarget.value });
              }}
              onChange={(event) => {
                setScheduleTouched(true);
                updateDraft({ timezone: event.target.value });
              }}
            />
          </label>
          <label>
            <span>Memory</span>
            <select
              value={draft.memoryWriteMode}
              disabled={isUserLevelSchedule}
              title={
                isUserLevelSchedule
                  ? "User-level schedules use the existing Viventium scheduler memory policy."
                  : "Memory write mode for Workbench GlassHive schedules."
              }
              onChange={(event) =>
                updateDraft({ memoryWriteMode: event.target.value })
              }
            >
              <option value="off">Off</option>
              <option value="propose">Propose</option>
              <option value="apply_governed">Apply governed proposals</option>
            </select>
            {isUserLevelSchedule && <small>User-level scheduler policy</small>}
          </label>
          <label className="schedule-enable-line">
            <input
              type="checkbox"
              checked={draft.active}
              onChange={(event) =>
                updateDraft({ active: event.target.checked })
              }
            />
            <span>Enabled</span>
          </label>
        </div>

        {supportsWorkbenchVariables ? (
          <div className="tag-cloud" aria-label="Supported variables">
            {tags.map((tag) => (
              <button
                key={tag}
                className={tag.includes("get_list") ? "function-tag" : ""}
                onClick={() => insertVariable(tag)}
              >
                {tag}
              </button>
            ))}
          </div>
        ) : (
          <div className="schedule-route-note">
            Existing user-level schedules run through the Viventium scheduler as
            stored. Workbench variable chips and rendered snapshots apply only
            to Workbench-private GlassHive prompts.
          </div>
        )}

        <div className="schedule-prompt-editor-wrap">
          <textarea
            ref={textareaRef}
            className="schedule-prompt-textarea"
            value={draft.promptText}
            onChange={(event) => {
              updateDraft({ promptText: event.target.value });
              setCursor(event.target.selectionStart ?? 0);
            }}
            onClick={(event) =>
              setCursor(event.currentTarget.selectionStart ?? 0)
            }
            onKeyUp={(event) =>
              setCursor(event.currentTarget.selectionStart ?? 0)
            }
            spellCheck={false}
            placeholder={
              templateQuery.isLoading
                ? "Loading built-in nightly template..."
                : "Write a private scheduled prompt..."
            }
          />
          {autocomplete && autocomplete.options.length > 0 && (
            <div
              className="variable-autocomplete"
              role="listbox"
              aria-label="Variable autocomplete"
            >
              {autocomplete.options.map((tag) => (
                <button
                  key={tag}
                  onClick={() => insertVariable(tag)}
                  className={tag.includes("get_list") ? "function-tag" : ""}
                >
                  <code>{`{{${tag}}}`}</code>
                  <span>
                    {tag.includes("get_list")
                      ? "function resolver"
                      : "live variable"}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="schedule-action-row">
          <button
            className="toolbar-button primary"
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending || Boolean(previewError)}
            title={previewError || "Save scheduled prompt"}
          >
            <Save size={15} />
            Save
          </button>
          <button
            className="toolbar-button"
            onClick={requestManualRun}
            disabled={!selected || runMutation.isPending}
            title={
              isUserLevelSchedule
                ? "Confirm before running this Viventium-agent schedule now."
                : "Run this GlassHive scheduled prompt now."
            }
          >
            <Play size={15} />
            {isUserLevelSchedule || currentExecutor === "viventium_agent"
              ? "Run Viventium"
              : "Run GlassHive"}
          </button>
          <button
            className="toolbar-button danger"
            onClick={() => draft.id && deleteMutation.mutate(draft.id)}
            disabled={!draft.id || deleteMutation.isPending}
          >
            <Trash2 size={15} />
            Delete
          </button>
        </div>
      </div>

      <div className="schedule-preview-pane">
        <div className="schedule-preview-header">
          <Eye size={15} />
          <strong>Rendered Variables</strong>
          <span>{previewQuery.data?.renderedHash ?? "pending"}</span>
        </div>
        <div className="rendered-variable-list">
          {!supportsWorkbenchVariables && (
            <div className="schedule-preview-empty">
              This user-level schedule does not use Workbench variable
              rendering.
            </div>
          )}
          {supportsWorkbenchVariables && previewError && (
            <div className="schedule-preview-error" role="alert">
              {previewError}
            </div>
          )}
          {supportsWorkbenchVariables &&
            !previewError &&
            !previewQuery.data?.variableSnapshot.items.length && (
              <div className="schedule-preview-empty">
                No supported variables in this prompt yet.
              </div>
            )}
          {supportsWorkbenchVariables &&
            (previewQuery.data?.variableSnapshot.items ?? []).map((item) => (
              <details key={`${item.placeholder}-${item.hash}`} open>
                <summary>
                  <span>{item.placeholder}</span>
                  <code>{item.hash}</code>
                </summary>
                <pre>{item.rendered}</pre>
              </details>
            ))}
        </div>
        <div className="run-history">
          <strong>Recent Runs</strong>
          {(selected?.recentRuns ?? []).map((run) => (
            <div key={run.runId} className="run-row">
              <span className={`run-state ${run.status}`}>{run.status}</span>
              <small>
                {run.startedAt ? formatDate(run.startedAt) : run.runId}
              </small>
              {run.effectiveReasoningEffort && (
                <small>
                  Effort{" "}
                  {run.requestedReasoningEffort ??
                    selected?.reasoningEffort ??
                    "default"}
                  {" -> "}
                  {run.effectiveReasoningEffort}
                  {run.reasoningFallbackReason
                    ? ` (${labelize(run.reasoningFallbackReason)})`
                    : ""}
                </small>
              )}
              {run.resultSummary && <p>{run.resultSummary}</p>}
            </div>
          ))}
        </div>
        {selected?.sourceKind === "workbench_definition" && (
          <>
            <div className="periphery-snapshot-panel">
              <div className="periphery-panel-heading">
                <div>
                  <strong>Evidence Snapshot</strong>
                  <span>
                    {snapshotQuery.data?.snapshot.status ?? "loading"}
                  </span>
                </div>
                <button
                  className="toolbar-button compact"
                  title="Refresh private evidence snapshot"
                  disabled={snapshotMutation.isPending}
                  onClick={() => snapshotMutation.mutate()}
                >
                  <RefreshCw size={14} />
                  Refresh
                </button>
              </div>
              {snapshotQuery.error instanceof Error && (
                <p>{snapshotQuery.error.message}</p>
              )}
              {snapshotQuery.data?.snapshot.generatedAt && (
                <div className="periphery-snapshot-meta">
                  <div>
                    <span>Generated</span>
                    <code>
                      {formatDate(snapshotQuery.data.snapshot.generatedAt)}
                    </code>
                  </div>
                  <div>
                    <span>Sources</span>
                    <code>{snapshotQuery.data.snapshot.sourceRefCount}</code>
                  </div>
                  {Object.entries(snapshotQuery.data.snapshot.counts).map(
                    ([key, value]) => (
                      <div key={key}>
                        <span>{labelize(key)}</span>
                        <code>{value}</code>
                      </div>
                    ),
                  )}
                </div>
              )}
              {Boolean(
                snapshotQuery.data?.snapshot.missingPrerequisites.length,
              ) && (
                <div className="periphery-snapshot-warning">
                  Missing:{" "}
                  {snapshotQuery.data?.snapshot.missingPrerequisites.join(", ")}
                </div>
              )}
            </div>
            <div className="periphery-artifact-panel">
              <div className="periphery-panel-heading">
                <div>
                  <strong>Periphery Artifacts</strong>
                  <span>
                    {peripheryQuery.data?.index.artifactCount ?? 0} indexed
                  </span>
                </div>
                <div className="periphery-quality-summary">
                  {Object.entries(
                    peripheryQuery.data?.index.qualityCounts ?? {},
                  ).map(([key, value]) => (
                    <span key={key} data-quality={key}>
                      {value} {key}
                    </span>
                  ))}
                </div>
              </div>
              {peripheryQuery.isLoading && (
                <p>Loading periphery artifacts...</p>
              )}
              {peripheryQuery.error instanceof Error && (
                <p>{peripheryQuery.error.message}</p>
              )}
              {!peripheryQuery.isLoading &&
                !peripheryQuery.data?.artifacts.length &&
                !peripheryQuery.data?.invalidArtifacts.length && (
                  <p>No private periphery artifacts found yet.</p>
                )}
              {(peripheryQuery.data?.artifacts ?? []).map((artifact, index) => (
                <details
                  key={artifact.artifactId}
                  className="periphery-artifact-card"
                  data-quality={artifact.qualityStatus}
                  open={index === 0}
                >
                  <summary>
                    <span>{artifact.moduleId}</span>
                    <code>{artifact.qualityStatus}</code>
                  </summary>
                  <div className="periphery-artifact-meta">
                    <div>
                      <span>Generated</span>
                      <code>{formatDate(artifact.generatedAt)}</code>
                    </div>
                    <div>
                      <span>Confidence</span>
                      <code>{artifact.confidence || "unknown"}</code>
                    </div>
                    <div>
                      <span>Severity</span>
                      <code>{artifact.severity || "unknown"}</code>
                    </div>
                    <div>
                      <span>Sources</span>
                      <code>{artifact.sourceRefCount}</code>
                    </div>
                    <div>
                      <span>Resolved</span>
                      <code>
                        {artifact.sourceRefsResolvedCount}/
                        {artifact.sourceRefCount}
                      </code>
                    </div>
                    <div>
                      <span>Markdown</span>
                      <code>
                        {artifact.markdownExists ? "present" : "missing"}
                      </code>
                    </div>
                    <div>
                      <span>Stale after</span>
                      <code>{formatDate(artifact.staleAfter)}</code>
                    </div>
                  </div>
                  <div className="periphery-artifact-paths">
                    <span>{artifact.relativePath}</span>
                    <span>{artifact.markdownRelativePath}</span>
                  </div>
                  <div
                    className="periphery-content-counts"
                    aria-label={`Content counts for ${artifact.moduleId}`}
                  >
                    {Object.entries(artifact.contentCounts).map(
                      ([key, value]) => (
                        <span key={key}>
                          <strong>{value}</strong>
                          {labelize(key)}
                        </span>
                      ),
                    )}
                  </div>
                  <div className="periphery-artifact-actions">
                    <button
                      className="toolbar-button compact"
                      onClick={() =>
                        setArtifactDetailId((current) =>
                          current === artifact.artifactId
                            ? ""
                            : artifact.artifactId,
                        )
                      }
                    >
                      <BookOpen size={14} />
                      {artifactDetailId === artifact.artifactId
                        ? "Hide"
                        : "Read"}
                    </button>
                  </div>
                  {artifactDetailId === artifact.artifactId &&
                    artifactDetailQuery.isLoading && (
                      <p className="periphery-detail-state">
                        Loading private artifact...
                      </p>
                    )}
                  {artifactDetailId === artifact.artifactId &&
                    artifactDetailQuery.error instanceof Error && (
                      <p className="periphery-detail-state">
                        {artifactDetailQuery.error.message}
                      </p>
                    )}
                  {artifactDetailId === artifact.artifactId &&
                    artifactDetailQuery.data && (
                      <div className="periphery-artifact-detail">
                        <pre>{artifactDetailQuery.data.markdown}</pre>
                        <details>
                          <summary>JSON sidecar</summary>
                          <pre>
                            {JSON.stringify(
                              artifactDetailQuery.data.sidecar,
                              null,
                              2,
                            )}
                          </pre>
                        </details>
                      </div>
                    )}
                </details>
              ))}
              {(peripheryQuery.data?.invalidArtifacts ?? []).map((artifact) => (
                <div
                  key={`${artifact.relativePath}-${artifact.reason}`}
                  className="periphery-invalid-card"
                >
                  <strong>{artifact.fileName}</strong>
                  <span>
                    {artifact.reason}
                    {artifact.missingFields?.length
                      ? `: ${artifact.missingFields.join(", ")}`
                      : ""}
                    {artifact.invalidFields?.length
                      ? `: ${artifact.invalidFields.join(", ")}`
                      : ""}
                  </span>
                </div>
              ))}
            </div>
            <div className="memory-proposal-panel">
              <strong>Memory Proposals</strong>
              <span>
                {proposalsQuery.data?.contract ??
                  "Structured proposal files appear here after runs."}
              </span>
              {proposalsQuery.isLoading && <p>Loading proposals...</p>}
              {proposalsQuery.error instanceof Error && (
                <p>{proposalsQuery.error.message}</p>
              )}
              {!proposalsQuery.isLoading &&
                !proposalsQuery.data?.proposals.length && (
                  <p>No structured memory proposals found yet.</p>
                )}
              {(proposalsQuery.data?.proposals ?? []).map((proposal) => (
                <details
                  key={proposal.proposalId}
                  className="memory-proposal-card"
                >
                  <summary>
                    <span>{proposal.fileName}</span>
                    <code>{proposal.actionCount} actions</code>
                  </summary>
                  <div className="proposal-actions">
                    {proposal.actions.map((action, index) => (
                      <div
                        key={`${action.key}-${index}`}
                        className="proposal-action-row"
                      >
                        <code>{action.action}</code>
                        <strong>{action.key}</strong>
                        {action.valueHash && <span>{action.valueHash}</span>}
                        {action.valuePreview && <p>{action.valuePreview}</p>}
                      </div>
                    ))}
                  </div>
                  <div className="proposal-button-row">
                    <button
                      className="toolbar-button compact"
                      disabled={proposalMutation.isPending}
                      onClick={() =>
                        proposalMutation.mutate({ proposal, apply: false })
                      }
                    >
                      Dry run
                    </button>
                    <button
                      className="toolbar-button primary compact"
                      disabled={proposalMutation.isPending}
                      onClick={() =>
                        proposalMutation.mutate({ proposal, apply: true })
                      }
                    >
                      Apply governed
                    </button>
                  </div>
                </details>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

interface EditorDraft {
  id: string;
  title: string;
  promptText: string;
  scheduleType: "daily" | "weekdays" | "weekly" | "cron";
  time: string;
  timezone: string;
  active: boolean;
  memoryWriteMode: string;
  executor: "glasshive_host" | "viventium_agent";
  conversationPolicy: "new" | "same";
  glasshiveWorkerStrategy: "same_worker" | "new_worker_each_run";
}

function draftFromPrompt(
  prompt?: ScheduledPrompt,
  template?: ScheduledPromptTemplate,
): EditorDraft {
  const schedule = prompt?.schedule ?? template?.schedule ?? {};
  return {
    id: prompt?.id ?? "",
    title:
      prompt?.title ??
      template?.title ??
      "Nightly subconscious thought formation",
    promptText: prompt?.promptText ?? template?.promptText ?? "",
    scheduleType: (schedule.type as EditorDraft["scheduleType"]) || "daily",
    time: String(schedule.time || "03:00"),
    timezone: String(
      schedule.timezone ||
        Intl.DateTimeFormat().resolvedOptions().timeZone ||
        "UTC",
    ),
    active: Boolean(prompt?.active),
    memoryWriteMode:
      prompt?.memoryWriteMode ?? template?.memoryWriteMode ?? "off",
    executor: (prompt?.executor as EditorDraft["executor"]) ?? "glasshive_host",
    conversationPolicy:
      (prompt?.conversationPolicy as EditorDraft["conversationPolicy"]) ??
      "new",
    glasshiveWorkerStrategy:
      (prompt?.glasshiveWorkerStrategy as EditorDraft["glasshiveWorkerStrategy"]) ??
      "same_worker",
  };
}

function draftPayload(
  draft: EditorDraft,
  options: { includeSchedule?: boolean; includeMemoryWriteMode?: boolean } = {},
): Partial<ScheduledPrompt> & { title: string; promptText: string } {
  const includeSchedule = options.includeSchedule ?? true;
  const includeMemoryWriteMode = options.includeMemoryWriteMode ?? true;
  const schedule: Record<string, unknown> = {
    type: draft.scheduleType,
    time: draft.time || "03:00",
    timezone: draft.timezone || "UTC",
  };
  if (draft.scheduleType === "weekly") {
    schedule.days_of_week = ["monday"];
  }
  if (draft.scheduleType === "cron") {
    schedule.cron = `0 ${Number((draft.time || "03:00").split(":")[0] || 3)} * * *`;
  }
  const payload: Partial<ScheduledPrompt> & {
    title: string;
    promptText: string;
  } = {
    title: draft.title,
    promptText: draft.promptText,
    active: draft.active,
  };
  if (includeSchedule) payload.schedule = schedule;
  if (includeMemoryWriteMode) payload.memoryWriteMode = draft.memoryWriteMode;
  payload.executor = draft.executor;
  payload.conversationPolicy = draft.conversationPolicy;
  payload.glasshiveWorkerStrategy = draft.glasshiveWorkerStrategy;
  payload.channel =
    draft.executor === "glasshive_host" ? "workbench" : "librechat";
  return payload;
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function labelize(value: string) {
  return value
    .replace(/([A-Z])/g, " $1")
    .replace(/_/g, " ")
    .toLowerCase();
}

function executionLabel(prompt: ScheduledPrompt) {
  if (prompt.executor === "glasshive_host") {
    return prompt.glasshiveWorkerStrategy === "new_worker_each_run"
      ? "Direct GlassHive Codex host worker, fresh worker per run."
      : "Direct GlassHive Codex host worker, same worker continuity.";
  }
  return prompt.sourceKind === "user_schedule"
    ? "Existing user-level schedule delivered by the Viventium agent scheduler."
    : `Workbench prompt delivered by the Viventium agent scheduler in a ${prompt.conversationPolicy ?? "new"} conversation.`;
}

function variableAutocomplete(
  promptText: string,
  cursor: number,
  tags: string[],
) {
  const before = promptText.slice(0, cursor);
  const open = before.lastIndexOf("{{");
  const close = before.lastIndexOf("}}");
  if (open < 0 || close > open) return null;
  const query = before
    .slice(open + 2)
    .trim()
    .toLowerCase();
  const options = tags
    .filter((tag) => tag.toLowerCase().includes(query))
    .slice(0, 8);
  return { start: open, options };
}

function insertVariableAtCursor(
  promptText: string,
  cursor: number,
  tag: string,
  autocompleteStart?: number,
) {
  const token = `{{${tag}}}`;
  const start =
    typeof autocompleteStart === "number" ? autocompleteStart : cursor;
  const prefix = promptText.slice(0, start);
  const suffix = promptText.slice(cursor);
  const spacer =
    prefix && !prefix.endsWith("\n") && !prefix.endsWith(" ") ? " " : "";
  const next = `${prefix}${spacer}${token}${suffix}`;
  return { text: next, cursor: prefix.length + spacer.length + token.length };
}
