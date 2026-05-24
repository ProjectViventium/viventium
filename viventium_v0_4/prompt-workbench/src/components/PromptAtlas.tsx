import { useEffect, useMemo, useRef, useState, type RefObject } from 'react';
import { Tree, type NodeRendererProps } from 'react-arborist';
import { ChevronRight, Clock3, FileText, Folder, Plus, ShieldAlert } from 'lucide-react';
import type { FlowGraph, PromptRow, ScheduledPrompt, SyncStatus } from '../types';

interface Props {
  prompts: PromptRow[];
  scheduledPrompts: ScheduledPrompt[];
  flow?: FlowGraph;
  searchTerm: string;
  selectedPromptId: string;
  onSelect: (id: string) => void;
  onNewScheduledPrompt: () => void;
  onToggleScheduledPrompt: (id: string, active: boolean) => void;
  syncStatus?: SyncStatus;
}

interface AtlasNode {
  id: string;
  name: string;
  kind: 'prompt' | 'group' | 'scheduled';
  promptId?: string;
  scheduledPromptId?: string;
  sourceKind?: string;
  active?: boolean;
  subtitle?: string;
  syncState?: string;
  safetyClass?: string;
  children?: AtlasNode[];
}

const familyOrder = ['Main', 'Surface', 'Cortex', 'MCP', 'Memory', 'Follow-up', 'Eval', 'Other'];

export function PromptAtlas({ prompts, scheduledPrompts, flow, searchTerm, selectedPromptId, onSelect, onNewScheduledPrompt, onToggleScheduledPrompt, syncStatus }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const treeHeight = useContainerHeight(containerRef);
  const treeData = useMemo(() => buildPromptTree(prompts, scheduledPrompts, flow, syncStatus), [prompts, scheduledPrompts, flow, syncStatus]);

  const renderNode = (props: NodeRendererProps<AtlasNode>) => (
    <AtlasTreeNode {...props} onSelect={onSelect} onToggleScheduledPrompt={onToggleScheduledPrompt} />
  );

  return (
    <div className="atlas flow-atlas" ref={containerRef}>
      <div className="pane-heading atlas-heading">
        <span className="pane-heading-title">Prompt Flow</span>
        <button
          className="toolbar-button icon-button small atlas-add-button"
          onClick={onNewScheduledPrompt}
          title="Add scheduled prompt"
          aria-label="Add scheduled prompt"
        >
          <Plus size={14} />
        </button>
        <span className="pane-heading-count" title={`${prompts.length + scheduledPrompts.length} prompt objects`}>
          {prompts.length + scheduledPrompts.length}
        </span>
      </div>
      <Tree<AtlasNode>
        data={treeData}
        selection={selectedPromptId}
        searchTerm={searchTerm}
        searchMatch={(node, term) => {
          const query = term.toLowerCase();
          return [node.data.name, node.data.promptId, node.data.subtitle]
            .filter(Boolean)
            .some((value) => String(value).toLowerCase().includes(query));
        }}
        height={treeHeight}
        rowHeight={44}
        indent={18}
        overscanCount={8}
        openByDefault
        disableDrag
        disableEdit
        disableMultiSelection
        onActivate={(node) => {
          if (node.data.promptId) onSelect(node.data.promptId);
        }}
        className="atlas-tree"
      >
        {renderNode}
      </Tree>
    </div>
  );
}

function AtlasTreeNode({
  node,
  style,
  dragHandle,
  onSelect,
  onToggleScheduledPrompt,
}: NodeRendererProps<AtlasNode> & { onSelect: (id: string) => void; onToggleScheduledPrompt: (id: string, active: boolean) => void }) {
  const data = node.data;
  const isPrompt = data.kind === 'prompt';
  const isScheduled = data.kind === 'scheduled';
  return (
    <div
      className={`atlas-tree-row ${node.isSelected ? 'active' : ''} ${isPrompt ? 'prompt' : isScheduled ? 'scheduled' : 'group'}`}
      style={style}
      ref={dragHandle}
      onClick={() => {
        if (node.isInternal) node.toggle();
        if (data.promptId) onSelect(data.promptId);
      }}
      title={[data.name, data.subtitle].filter(Boolean).join(' - ')}
      data-node-kind={data.kind}
      data-scheduled-prompt-id={data.scheduledPromptId}
      data-source-kind={data.sourceKind}
    >
      <span className="tree-chevron">
        {node.isInternal && <ChevronRight size={13} className={node.isOpen ? 'open' : ''} />}
      </span>
      {isScheduled ? <Clock3 size={14} /> : isPrompt ? <FileText size={14} /> : <Folder size={14} />}
      {isScheduled && data.promptId ? (
        <button
          type="button"
          className="tree-label tree-label-button"
          aria-label={`Open ${data.name} schedule`}
          onClick={(event) => {
            event.stopPropagation();
            onSelect(data.promptId!);
          }}
        >
          {data.name}
        </button>
      ) : (
        <span className="tree-label">{data.name}</span>
      )}
      {isScheduled && data.scheduledPromptId && (
        <button
          className={`schedule-inline-switch ${data.active ? 'enabled' : ''}`}
          aria-label={`${data.active ? 'Disable' : 'Enable'} ${data.name}`}
          title={`${data.active ? 'Disable' : 'Enable'} schedule`}
          onClick={(event) => {
            event.stopPropagation();
            onToggleScheduledPrompt(data.scheduledPromptId!, !data.active);
          }}
        >
          <span />
        </button>
      )}
      {data.syncState && <span className={`tree-status ${data.syncState}`} title={data.syncState} />}
      {data.safetyClass && data.safetyClass !== 'public_product' && <ShieldAlert size={13} className="tree-warning" />}
      {data.subtitle && <small>{data.subtitle}</small>}
    </div>
  );
}

function buildPromptTree(prompts: PromptRow[], scheduledPrompts: ScheduledPrompt[], flow: FlowGraph | undefined, syncStatus: SyncStatus | undefined): AtlasNode[] {
  const promptById = new Map(prompts.map((prompt) => [prompt.id, prompt]));
  const syncByPromptId = new Map((syncStatus?.agents ?? []).map((row) => [row.sourcePromptId, row.state]));
  const childrenByPromptId = new Map<string, string[]>();
  for (const edge of flow?.edges ?? []) {
    const list = childrenByPromptId.get(edge.source) ?? [];
    list.push(edge.target);
    childrenByPromptId.set(edge.source, list);
  }

  const used = new Set<string>();
  const makePromptNode = (id: string, ancestors = new Set<string>()): AtlasNode | null => {
    const prompt = promptById.get(id);
    if (!prompt) return null;
    used.add(id);
    const nextAncestors = new Set(ancestors);
    nextAncestors.add(id);
    const children = (childrenByPromptId.get(id) ?? [])
      .filter((childId) => !nextAncestors.has(childId))
      .map((childId) => makePromptNode(childId, nextAncestors))
      .filter((node): node is AtlasNode => Boolean(node));

    return {
      id,
      name: humanPromptName(id),
      kind: 'prompt',
      promptId: id,
      subtitle: prompt.target ? humanTarget(prompt.target) : prompt.family,
      syncState: syncByPromptId.get(id),
      safetyClass: prompt.safetyClass,
      children: children.length ? children : undefined,
    };
  };

  const roots: AtlasNode[] = [];
  if (scheduledPrompts.length) {
    roots.push({
      id: 'scheduled-prompt-objects',
      name: 'Scheduled Prompts',
      kind: 'group',
      subtitle: `${scheduledPrompts.length} prompt object${scheduledPrompts.length === 1 ? '' : 's'}`,
      children: scheduledPrompts.map((prompt) => ({
        id: scheduledPromptSelectionId(prompt.id),
        name: prompt.title,
        kind: 'scheduled',
        promptId: scheduledPromptSelectionId(prompt.id),
        scheduledPromptId: prompt.id,
        sourceKind: prompt.sourceKind,
        active: prompt.active,
        subtitle: scheduledPromptSubtitle(prompt),
      })),
    });
  }

  const mainRoot = makePromptNode('main.conscious_agent');
  if (mainRoot) {
    mainRoot.name = 'Main agent instruction';
    mainRoot.subtitle = 'what the LLM sees first';
    roots.push(mainRoot);
  }

  const otherFamilyGroups: AtlasNode[] = [];
  for (const family of familyOrder) {
    const rows = prompts.filter((prompt) => !used.has(prompt.id) && (prompt.family || 'Other') === family);
    if (!rows.length) continue;
    otherFamilyGroups.push({
      id: `family:${family}`,
      name: family,
      kind: 'group',
      subtitle: `${rows.length} prompts`,
      children: rows.map((prompt) => ({
        id: prompt.id,
        name: humanPromptName(prompt.id),
        kind: 'prompt',
        promptId: prompt.id,
        subtitle: prompt.target ? humanTarget(prompt.target) : prompt.family,
        syncState: syncByPromptId.get(prompt.id),
        safetyClass: prompt.safetyClass,
      })),
    });
  }

  if (otherFamilyGroups.length) {
    roots.push({
      id: 'not-in-main-path',
      name: 'Not in main path',
      kind: 'group',
      subtitle: 'supporting prompt families',
      children: otherFamilyGroups,
    });
  }

  return roots;
}

function scheduledPromptSelectionId(id: string) {
  return `scheduled-prompt:${id}`;
}

function scheduledPromptSubtitle(prompt: ScheduledPrompt) {
  const source = prompt.sourceLabel || (prompt.sourceKind === 'user_schedule' ? 'User-level schedule' : 'Workbench private prompt');
  const state = prompt.active ? 'enabled' : 'paused';
  const next = prompt.nextRunAt ? `next ${formatCompactDate(prompt.nextRunAt)}` : 'not scheduled';
  return `${source} · ${state} · ${next}`;
}

function formatCompactDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

function humanPromptName(id: string) {
  const [, ...rest] = id.split('.');
  const label = (rest.join('.') || id).replace(/[._-]+/g, ' ');
  return label.replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function humanTarget(target: string) {
  if (target.includes('meeting_transcript')) return 'transcript ingest';
  if (target.includes('memory_hardening')) return 'nightly memory';
  if (target.includes('instructions')) return 'instruction layer';
  if (target.includes('activation')) return 'activation check';
  if (target.includes('execution')) return 'execution prompt';
  if (target.includes('server')) return 'tool server';
  return target.replace(/[._-]+/g, ' ');
}

function useContainerHeight(ref: RefObject<HTMLElement | null>) {
  const [height, setHeight] = useState(520);
  useEffect(() => {
    if (!ref.current) return;
    const observer = new ResizeObserver(([entry]) => {
      setHeight(Math.max(240, Math.floor(entry.contentRect.height - 44)));
    });
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, [ref]);
  return height;
}
