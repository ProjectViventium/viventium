import { useEffect, useMemo, useRef, type ReactNode } from 'react';
import { Controls, ReactFlow, ReactFlowProvider, useReactFlow, type Edge, type Node } from '@xyflow/react';
import type { EvalBank, FlowGraph, PromptRow } from '../types';

interface Props {
  prompts: PromptRow[];
  flow?: FlowGraph;
  evalBank?: EvalBank;
  selectedPromptId: string;
  onSelect: (id: string) => void;
  onOpenPrompt?: (id: string) => void;
  onOpenTab?: (tab: 'live' | 'evals') => void;
}

type StageId = 'surfaces' | 'conscious' | 'memory' | 'cortex' | 'delivery';
type FlowNodeKind = 'stage' | 'prompt' | 'artifact' | 'eval';

type FlowNodeData = {
  label: ReactNode;
  kind: FlowNodeKind;
  promptId?: string;
  openTab?: 'live' | 'evals';
};

type PromptFlowNode = Node<FlowNodeData>;

type StageDefinition = {
  id: StageId;
  title: string;
  subtitle: string;
};

type StageLayout = StageDefinition & {
  x: number;
  y: number;
  width: number;
  columns: number;
  height: number;
};

const STAGES: StageDefinition[] = [
  { id: 'surfaces', title: 'Interaction Surfaces', subtitle: 'web, voice, Telegram, scheduler, transcript ingress' },
  { id: 'conscious', title: 'Conscious Agent', subtitle: 'identity, behavior, memory policy, boundaries' },
  { id: 'memory', title: 'Memory and Recall', subtitle: 'conversation recall, archivist, transcript hardening' },
  { id: 'cortex', title: 'Background Cortex and Tools', subtitle: 'background analysis, MCP servers, delegated work' },
  { id: 'delivery', title: 'Delivery and Evaluation', subtitle: 'surface output, eval bank, traces, live drift' },
];

const NODE_WIDTH = 216;
const NODE_GAP_X = 18;
const NODE_GAP_Y = 62;
const STAGE_GAP = 34;
const MAP_X = 40;
const STAGE_WIDTH = 520;

export function PromptFlow({ prompts, flow, evalBank, selectedPromptId, onSelect, onOpenPrompt, onOpenTab }: Props) {
  const { nodes, edges } = useMemo(() => buildSourceMap(prompts, flow, evalBank, selectedPromptId), [prompts, flow, evalBank, selectedPromptId]);
  const promptIds = useMemo(() => new Set(prompts.map((prompt) => prompt.id)), [prompts]);
  return (
    <div className="flow-shell source-map-shell">
      <ReactFlowProvider>
        <PromptFlowCanvas
          nodes={nodes}
          edges={edges}
          promptIds={promptIds}
          onSelect={onSelect}
          onOpenPrompt={onOpenPrompt}
          onOpenTab={onOpenTab}
        />
      </ReactFlowProvider>
    </div>
  );
}

function PromptFlowCanvas({
  nodes,
  edges,
  promptIds,
  onSelect,
  onOpenPrompt,
  onOpenTab,
}: {
  nodes: PromptFlowNode[];
  edges: Edge[];
  promptIds: Set<string>;
  onSelect: (id: string) => void;
  onOpenPrompt?: (id: string) => void;
  onOpenTab?: (tab: 'live' | 'evals') => void;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const { fitView } = useReactFlow();

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    let timer = 0;
    const observer = new ResizeObserver(() => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => fitView({ padding: 0.12, duration: 0 }), 90);
    });
    observer.observe(element);
    return () => {
      window.clearTimeout(timer);
      observer.disconnect();
    };
  }, [fitView, nodes.length, edges.length]);

  return (
    <div className="flow-canvas" ref={containerRef}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        fitViewOptions={{ padding: 0.12 }}
        minZoom={0.2}
        maxZoom={1.35}
        nodesDraggable={false}
        nodesConnectable={false}
        onNodeClick={(event, node) => {
          const promptId = node.data.promptId;
          if (promptId && promptIds.has(promptId)) {
            if (event.detail >= 2) {
              (onOpenPrompt ?? onSelect)(promptId);
              return;
            }
            onSelect(promptId);
          }
        }}
        onNodeDoubleClick={(_, node) => {
          const promptId = node.data.promptId;
          if (promptId && promptIds.has(promptId)) {
            (onOpenPrompt ?? onSelect)(promptId);
            return;
          }
          if (node.data.openTab) onOpenTab?.(node.data.openTab);
        }}
      >
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

function buildSourceMap(prompts: PromptRow[], flow: FlowGraph | undefined, evalBank: EvalBank | undefined, selectedPromptId: string): { nodes: PromptFlowNode[]; edges: Edge[] } {
  const promptById = new Map(prompts.map((prompt) => [prompt.id, prompt]));
  const selected = promptById.get(selectedPromptId) ?? prompts[0];
  const selectedId = selected?.id ?? selectedPromptId;
  const flowEdges = (flow?.edges ?? []).filter((edge) => promptById.has(edge.source) && promptById.has(edge.target));
  const promptStage = new Map(prompts.map((prompt) => [prompt.id, stageForPrompt(prompt)]));
  const lineage = collectLineage(selectedId, flowEdges);
  const evalLinks = collectEvalLinks(evalBank, selectedId, lineage.activePromptIds);
  const contextPromptIds = new Set<string>();
  if (selected) {
    for (const prompt of prompts) {
      if (prompt.family === selected.family || promptStage.get(prompt.id) === promptStage.get(selected.id)) {
        contextPromptIds.add(prompt.id);
      }
    }
  }
  for (const promptId of evalLinks.promptIds) contextPromptIds.add(promptId);

  const visiblePromptIds = selectVisiblePromptIds(prompts, selectedId, lineage.activePromptIds, contextPromptIds, evalLinks.promptIds);
  const allPromptsByStage = new Map<StageId, PromptRow[]>();
  const promptsByStage = new Map<StageId, PromptRow[]>();
  for (const prompt of prompts) {
    const stage = promptStage.get(prompt.id) ?? 'delivery';
    const allRows = allPromptsByStage.get(stage) ?? [];
    allRows.push(prompt);
    allPromptsByStage.set(stage, allRows);
    if (visiblePromptIds.has(prompt.id)) {
      const rows = promptsByStage.get(stage) ?? [];
      rows.push(prompt);
      promptsByStage.set(stage, rows);
    }
  }
  for (const rows of promptsByStage.values()) {
    rows.sort((a, b) => promptSortWeight(a.id, selectedId, lineage.activePromptIds, contextPromptIds) - promptSortWeight(b.id, selectedId, lineage.activePromptIds, contextPromptIds) || a.id.localeCompare(b.id));
  }

  const stageLayouts = buildStageLayouts(promptsByStage, allPromptsByStage);
  const nodes: PromptFlowNode[] = [];
  for (const stage of stageLayouts) {
    const allStagePromptIds = new Set((allPromptsByStage.get(stage.id) ?? []).map((prompt) => prompt.id));
    const stagePromptIds = new Set((promptsByStage.get(stage.id) ?? []).map((prompt) => prompt.id));
    const activeCount = Array.from(stagePromptIds).filter((id) => lineage.activePromptIds.has(id) || contextPromptIds.has(id)).length;
    nodes.push({
      id: `stage:${stage.id}`,
      position: { x: stage.x, y: stage.y },
      data: {
        kind: 'stage',
        label: <StageLabel title={stage.title} subtitle={stage.subtitle} promptCount={allStagePromptIds.size} activeCount={activeCount} />,
      },
      selectable: false,
      className: `flow-node source-map-node source-map-stage ${activeCount ? 'active' : 'dimmed'}`,
      style: { width: stage.width },
    });

    const stagePrompts = promptsByStage.get(stage.id) ?? [];
    for (const [index, prompt] of stagePrompts.entries()) {
      const column = index % stage.columns;
      const row = Math.floor(index / stage.columns);
      const relation = relationForPrompt(prompt.id, selectedId, lineage.activePromptIds, contextPromptIds);
      nodes.push({
        id: prompt.id,
        position: { x: stage.x + column * (NODE_WIDTH + NODE_GAP_X), y: stage.y + 106 + row * NODE_GAP_Y },
        data: {
          kind: 'prompt',
          promptId: prompt.id,
          label: <PromptNodeLabel prompt={prompt} relation={relation.label} />,
        },
        className: `flow-node source-map-node prompt-map-node ${relation.className}`,
        style: { width: NODE_WIDTH },
      });
    }
    const hiddenCount = Math.max(0, allStagePromptIds.size - stagePromptIds.size);
    if (hiddenCount) {
      const index = stagePrompts.length;
      const column = index % stage.columns;
      const row = Math.floor(index / stage.columns);
      nodes.push({
        id: `stage-overflow:${stage.id}`,
        position: { x: stage.x + column * (NODE_WIDTH + NODE_GAP_X), y: stage.y + 106 + row * NODE_GAP_Y },
        data: {
          kind: 'stage',
          label: <OverflowLabel title={`${hiddenCount} other prompt${hiddenCount === 1 ? '' : 's'}`} meta={stage.title} />,
        },
        selectable: false,
        className: 'flow-node source-map-node overflow-map-node dimmed',
        style: { width: NODE_WIDTH },
      });
    }
  }

  const deliveryStage = stageLayouts.find((stage) => stage.id === 'delivery') ?? stageLayouts[stageLayouts.length - 1];
  const deliveryVisibleRows = (promptsByStage.get('delivery')?.length ?? 0) + (Math.max(0, (allPromptsByStage.get('delivery')?.length ?? 0) - (promptsByStage.get('delivery')?.length ?? 0)) ? 1 : 0);
  const artifactY = deliveryStage.y + 106 + Math.ceil(deliveryVisibleRows / deliveryStage.columns) * NODE_GAP_Y + 28;
  const artifacts = [
    { id: 'artifact:rendered', title: 'Rendered Registry', eyebrow: 'source output', meta: 'same text Prompt tab reads' },
    { id: 'artifact:runtime', title: 'Local Runtime', eyebrow: 'installed state', meta: 'live drift and guarded push', openTab: 'live' as const },
    { id: 'artifact:eval-bank', title: 'Eval Bank', eyebrow: 'promptRefs', meta: `${evalBank?.familyCount ?? 0} families`, openTab: 'evals' as const },
    { id: 'artifact:eval-results', title: 'Eval Results', eyebrow: 'local evidence', meta: 'preview and exact-model runs', openTab: 'evals' as const },
  ];
  artifacts.forEach((artifact, index) => {
    nodes.push({
      id: artifact.id,
      position: {
        x: deliveryStage.x + (index % Math.max(2, deliveryStage.columns)) * (NODE_WIDTH + NODE_GAP_X),
        y: artifactY + Math.floor(index / Math.max(2, deliveryStage.columns)) * NODE_GAP_Y,
      },
      data: {
        kind: 'artifact',
        openTab: artifact.openTab,
        label: <ArtifactLabel eyebrow={artifact.eyebrow} title={artifact.title} meta={artifact.meta} />,
      },
      className: 'flow-node source-map-node artifact-map-node active',
      style: { width: NODE_WIDTH },
    });
  });

  const allEvalFamilies = evalBank?.families ?? [];
  const linkedEvalFamilies = allEvalFamilies.filter((family) => evalLinks.familyIds.has(family.id));
  const dimmedEvalFamilies = allEvalFamilies.filter((family) => !evalLinks.familyIds.has(family.id));
  const visibleEvalFamilies = [...linkedEvalFamilies, ...dimmedEvalFamilies].slice(0, 8);
  const hiddenEvalCount = Math.max(0, allEvalFamilies.length - visibleEvalFamilies.length);
  const evalStartY = artifactY + Math.ceil(artifacts.length / Math.max(2, deliveryStage.columns)) * NODE_GAP_Y + 28;
  for (const [index, family] of visibleEvalFamilies.entries()) {
    const promptRefs = promptRefsForFamily(family);
    const linked = promptRefs.has(selectedId) || Array.from(promptRefs).some((id) => lineage.activePromptIds.has(id));
    nodes.push({
      id: `eval:${family.id}`,
      position: {
        x: deliveryStage.x + (index % Math.max(2, deliveryStage.columns)) * (NODE_WIDTH + NODE_GAP_X),
        y: evalStartY + Math.floor(index / Math.max(2, deliveryStage.columns)) * NODE_GAP_Y,
      },
      data: {
        kind: 'eval',
        openTab: 'evals',
        label: <EvalLabel familyId={family.id} caseCount={family.cases.length} linked={linked} />,
      },
      className: `flow-node source-map-node eval-map-node ${linked ? 'active' : 'dimmed'}`,
      style: { width: NODE_WIDTH },
    });
  }
  if (hiddenEvalCount) {
    const index = visibleEvalFamilies.length;
    nodes.push({
      id: 'eval-overflow',
      position: {
        x: deliveryStage.x + (index % Math.max(2, deliveryStage.columns)) * (NODE_WIDTH + NODE_GAP_X),
        y: evalStartY + Math.floor(index / Math.max(2, deliveryStage.columns)) * NODE_GAP_Y,
      },
      data: {
        kind: 'eval',
        openTab: 'evals',
        label: <OverflowLabel title={`${hiddenEvalCount} other eval families`} meta="Eval bank" />,
      },
      className: 'flow-node source-map-node overflow-map-node dimmed',
      style: { width: NODE_WIDTH },
    });
  }

  const edges: Edge[] = [];
  const visibleNodeIds = new Set(nodes.map((node) => node.id));
  for (const edge of flowEdges) {
    if (!visibleNodeIds.has(edge.source) || !visibleNodeIds.has(edge.target)) continue;
    edges.push({
      id: `include:${edge.source}:${edge.target}`,
      source: edge.source,
      target: edge.target,
      type: 'smoothstep',
      className: edgeClass(edge.source, edge.target, lineage.activePromptIds, contextPromptIds),
    });
  }
  if (promptById.has(selectedId)) {
    edges.push(
      { id: 'selected-rendered', source: selectedId, target: 'artifact:rendered', type: 'smoothstep', animated: true, className: 'source-map-edge active' },
      { id: 'rendered-runtime', source: 'artifact:rendered', target: 'artifact:runtime', type: 'smoothstep', className: 'source-map-edge active' },
      { id: 'rendered-eval-bank', source: 'artifact:rendered', target: 'artifact:eval-bank', type: 'smoothstep', className: 'source-map-edge active' },
      { id: 'eval-bank-results', source: 'artifact:eval-bank', target: 'artifact:eval-results', type: 'smoothstep', className: 'source-map-edge active' },
    );
  }
  for (const family of evalBank?.families ?? []) {
    const evalNodeId = `eval:${family.id}`;
    if (!visibleNodeIds.has(evalNodeId)) continue;
    const promptRefs = promptRefsForFamily(family);
    for (const promptId of promptRefs) {
      if (!promptById.has(promptId) || !visibleNodeIds.has(promptId)) continue;
      const linked = evalLinks.familyIds.has(family.id) || lineage.activePromptIds.has(promptId) || promptId === selectedId;
      edges.push({
        id: `eval-link:${promptId}:${family.id}`,
        source: promptId,
        target: evalNodeId,
        type: 'smoothstep',
        className: `source-map-edge eval-link ${linked ? 'active' : 'dimmed'}`,
      });
    }
  }

  return { nodes, edges };
}

function selectVisiblePromptIds(prompts: PromptRow[], selectedId: string, activePromptIds: Set<string>, contextPromptIds: Set<string>, evalPromptIds: Set<string>) {
  const visible = new Set(activePromptIds);
  visible.add(selectedId);
  const selected = prompts.find((prompt) => prompt.id === selectedId);
  const sameFamily = prompts.filter((prompt) => selected && prompt.family === selected.family);
  for (const prompt of sameFamily.slice(0, selectedId === 'main.conscious_agent' ? 12 : 8)) {
    visible.add(prompt.id);
  }
  if (selectedId !== 'main.conscious_agent') {
    for (const promptId of Array.from(evalPromptIds).slice(0, 12)) visible.add(promptId);
  }
  if (selectedId !== 'main.conscious_agent') {
    for (const prompt of prompts) {
      if (contextPromptIds.has(prompt.id) && visible.size < 30) visible.add(prompt.id);
    }
  }
  return visible;
}

function buildStageLayouts(promptsByStage: Map<StageId, PromptRow[]>, allPromptsByStage: Map<StageId, PromptRow[]>): StageLayout[] {
  let y = 30;
  return STAGES.map((stage) => {
    const visibleCount = promptsByStage.get(stage.id)?.length ?? 0;
    const hiddenCount = Math.max(0, (allPromptsByStage.get(stage.id)?.length ?? 0) - visibleCount);
    const count = visibleCount + (hiddenCount ? 1 : 0);
    const columns = count > 2 ? 2 : 1;
    const height = 106 + Math.max(1, Math.ceil(count / columns)) * NODE_GAP_Y;
    const layout = { ...stage, x: MAP_X, y, width: STAGE_WIDTH, columns, height };
    y += height + STAGE_GAP;
    return layout;
  });
}

function collectLineage(selectedId: string, flowEdges: FlowGraph['edges']) {
  const childrenBySource = new Map<string, string[]>();
  const parentsByTarget = new Map<string, string[]>();
  for (const edge of flowEdges) {
    const children = childrenBySource.get(edge.source) ?? [];
    children.push(edge.target);
    childrenBySource.set(edge.source, children);
    const parents = parentsByTarget.get(edge.target) ?? [];
    parents.push(edge.source);
    parentsByTarget.set(edge.target, parents);
  }

  const activePromptIds = new Set([selectedId]);
  const walk = (id: string, graph: Map<string, string[]>) => {
    for (const next of graph.get(id) ?? []) {
      if (activePromptIds.has(next)) continue;
      activePromptIds.add(next);
      walk(next, graph);
    }
  };
  walk(selectedId, childrenBySource);
  walk(selectedId, parentsByTarget);
  return { activePromptIds };
}

function collectEvalLinks(evalBank: EvalBank | undefined, selectedId: string, activePromptIds: Set<string>) {
  const familyIds = new Set<string>();
  const promptIds = new Set<string>();
  for (const family of evalBank?.families ?? []) {
    const refs = promptRefsForFamily(family);
    if (refs.has(selectedId) || Array.from(refs).some((id) => activePromptIds.has(id))) {
      familyIds.add(family.id);
      for (const ref of refs) promptIds.add(ref);
    }
  }
  return { familyIds, promptIds };
}

function promptRefsForFamily(family: EvalBank['families'][number]) {
  const refs = new Set<string>((family.promptRefs ?? []).map(String));
  for (const testCase of family.cases) {
    for (const ref of testCase.promptRefs ?? []) refs.add(String(ref));
  }
  return refs;
}

function stageForPrompt(prompt: PromptRow): StageId {
  const id = prompt.id;
  const target = prompt.target.toLowerCase();
  if (id.startsWith('memory.') || target.includes('memory')) return 'memory';
  if (id.startsWith('surface.cortex_output')) return 'delivery';
  if (id.startsWith('cortex.') || id.startsWith('mcp.') || id.includes('background') || target.includes('cortex') || target.includes('mcp')) return 'cortex';
  if (id.startsWith('surface.') || target.includes('voice') || target.includes('telegram') || target.includes('scheduler') || target.includes('transcript')) return 'surfaces';
  if (id.startsWith('main.')) return 'conscious';
  return 'delivery';
}

function relationForPrompt(promptId: string, selectedId: string, activePromptIds: Set<string>, contextPromptIds: Set<string>) {
  if (promptId === selectedId) return { label: 'selected prompt', className: 'selected' };
  if (activePromptIds.has(promptId)) return { label: 'selected path', className: 'active' };
  if (contextPromptIds.has(promptId)) return { label: 'related context', className: 'context' };
  return { label: 'other flow', className: 'dimmed' };
}

function promptSortWeight(promptId: string, selectedId: string, activePromptIds: Set<string>, contextPromptIds: Set<string>) {
  if (promptId === selectedId) return 0;
  if (activePromptIds.has(promptId)) return 1;
  if (contextPromptIds.has(promptId)) return 2;
  return 3;
}

function edgeClass(source: string, target: string, activePromptIds: Set<string>, contextPromptIds: Set<string>) {
  if (activePromptIds.has(source) && activePromptIds.has(target)) return 'source-map-edge active';
  if (contextPromptIds.has(source) || contextPromptIds.has(target)) return 'source-map-edge context';
  return 'source-map-edge dimmed';
}

function StageLabel({ title, subtitle, promptCount, activeCount }: { title: string; subtitle: string; promptCount: number; activeCount: number }) {
  return (
    <div className="source-map-label stage-label">
      <strong>{title}</strong>
      <span>{subtitle}</span>
      <small>{activeCount ? `${activeCount} in view / ${promptCount} prompts` : `${promptCount} prompts`}</small>
    </div>
  );
}

function PromptNodeLabel({ prompt, relation }: { prompt: PromptRow; relation: string }) {
  return (
    <div className="source-map-label prompt-label">
      <span>{prompt.family} · {humanTarget(prompt.target)}</span>
      <strong>{humanPromptName(prompt.id)}</strong>
      <small>{relation}</small>
    </div>
  );
}

function ArtifactLabel({ eyebrow, title, meta }: { eyebrow: string; title: string; meta: string }) {
  return (
    <div className="source-map-label artifact-label">
      <span>{eyebrow}</span>
      <strong>{title}</strong>
      <small>{meta}</small>
    </div>
  );
}

function EvalLabel({ familyId, caseCount, linked }: { familyId: string; caseCount: number; linked: boolean }) {
  return (
    <div className="source-map-label eval-label">
      <span>{linked ? 'linked eval' : 'eval family'}</span>
      <strong>{humanPromptName(familyId)}</strong>
      <small>{caseCount} case{caseCount === 1 ? '' : 's'}</small>
    </div>
  );
}

function OverflowLabel({ title, meta }: { title: string; meta: string }) {
  return (
    <div className="source-map-label overflow-label">
      <span>greyed flow</span>
      <strong>{title}</strong>
      <small>{meta}</small>
    </div>
  );
}

function humanPromptName(id: string) {
  const label = id.split('.').slice(1).join(' ') || id;
  return label.replace(/[._-]+/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function humanTarget(target: string) {
  if (!target) return 'prompt';
  if (target.includes('meeting_transcript')) return 'transcript ingest';
  if (target.includes('memory_hardening')) return 'nightly memory';
  if (target.includes('instructions')) return 'instruction layer';
  if (target.includes('activation')) return 'activation';
  if (target.includes('execution')) return 'execution';
  if (target.includes('server')) return 'tool server';
  if (target.includes('surface')) return 'surface';
  return target.replace(/[._-]+/g, ' ');
}
