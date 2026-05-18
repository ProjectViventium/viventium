import { useEffect, useMemo, useRef, useState, type RefObject } from 'react';
import { Tree, type NodeRendererProps } from 'react-arborist';
import { ChevronRight, FileText, Folder, ShieldAlert } from 'lucide-react';
import type { FlowGraph, PromptRow, SyncStatus } from '../types';

interface Props {
  prompts: PromptRow[];
  flow?: FlowGraph;
  searchTerm: string;
  selectedPromptId: string;
  onSelect: (id: string) => void;
  syncStatus?: SyncStatus;
}

interface AtlasNode {
  id: string;
  name: string;
  kind: 'prompt' | 'group';
  promptId?: string;
  subtitle?: string;
  syncState?: string;
  safetyClass?: string;
  children?: AtlasNode[];
}

const familyOrder = ['Main', 'Surface', 'Cortex', 'MCP', 'Memory', 'Follow-up', 'Eval', 'Other'];

export function PromptAtlas({ prompts, flow, searchTerm, selectedPromptId, onSelect, syncStatus }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const treeHeight = useContainerHeight(containerRef);
  const treeData = useMemo(() => buildPromptTree(prompts, flow, syncStatus), [prompts, flow, syncStatus]);

  return (
    <div className="atlas flow-atlas" ref={containerRef}>
      <div className="pane-heading">
        <span>Prompt Flow</span>
        <span>{prompts.length}</span>
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
        rowHeight={40}
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
        {AtlasTreeNode}
      </Tree>
      <div className="atlas-foot">
        <span className="small-copy">Main flow first. Other prompt families stay tucked below.</span>
      </div>
    </div>
  );
}

function AtlasTreeNode({ node, style, dragHandle }: NodeRendererProps<AtlasNode>) {
  const data = node.data;
  const isPrompt = data.kind === 'prompt';
  return (
    <div
      className={`atlas-tree-row ${node.isSelected ? 'active' : ''} ${isPrompt ? 'prompt' : 'group'}`}
      style={style}
      ref={dragHandle}
      onClick={(event) => {
        event.stopPropagation();
        if (node.isInternal) node.toggle();
        if (data.promptId) node.activate();
      }}
      title={[data.name, data.subtitle].filter(Boolean).join(' - ')}
    >
      <span className="tree-chevron">
        {node.isInternal && <ChevronRight size={13} className={node.isOpen ? 'open' : ''} />}
      </span>
      {isPrompt ? <FileText size={14} /> : <Folder size={14} />}
      <span className="tree-label">{data.name}</span>
      {data.syncState && <span className={`tree-status ${data.syncState}`} title={data.syncState} />}
      {data.safetyClass && data.safetyClass !== 'public_product' && <ShieldAlert size={13} className="tree-warning" />}
      {data.subtitle && <small>{data.subtitle}</small>}
    </div>
  );
}

function buildPromptTree(prompts: PromptRow[], flow: FlowGraph | undefined, syncStatus: SyncStatus | undefined): AtlasNode[] {
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

function humanPromptName(id: string) {
  const [, ...rest] = id.split('.');
  const label = (rest.join('.') || id).replace(/[._-]+/g, ' ');
  return label.replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function humanTarget(target: string) {
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
      setHeight(Math.max(240, Math.floor(entry.contentRect.height - 96)));
    });
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, [ref]);
  return height;
}
