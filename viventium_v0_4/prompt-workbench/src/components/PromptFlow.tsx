import { useEffect, useMemo, useRef } from 'react';
import { Controls, ReactFlow, ReactFlowProvider, useReactFlow, type Edge, type Node } from '@xyflow/react';
import type { FlowGraph, PromptRow } from '../types';

interface Props {
  prompts: PromptRow[];
  flow?: FlowGraph;
  selectedPromptId: string;
  onSelect: (id: string) => void;
}

export function PromptFlow({ prompts, flow, selectedPromptId, onSelect }: Props) {
  const { nodes, edges } = useMemo(() => buildFlow(prompts, flow, selectedPromptId), [prompts, flow, selectedPromptId]);
  const promptIds = useMemo(() => new Set(prompts.map((prompt) => prompt.id)), [prompts]);
  return (
    <div className="flow-shell">
      <ReactFlowProvider>
        <PromptFlowCanvas nodes={nodes} edges={edges} promptIds={promptIds} onSelect={onSelect} />
      </ReactFlowProvider>
    </div>
  );
}

function PromptFlowCanvas({ nodes, edges, promptIds, onSelect }: { nodes: Node[]; edges: Edge[]; promptIds: Set<string>; onSelect: (id: string) => void }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const { fitView } = useReactFlow();

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    let timer = 0;
    const observer = new ResizeObserver(() => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => fitView({ padding: 0.16, duration: 0 }), 90);
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
        fitViewOptions={{ padding: 0.16 }}
        minZoom={0.18}
        nodesDraggable={false}
        nodesConnectable={false}
        onNodeClick={(_, node) => {
          if (promptIds.has(node.id)) onSelect(node.id);
        }}
      >
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

function buildFlow(prompts: PromptRow[], flow: FlowGraph | undefined, selectedPromptId: string): { nodes: Node[]; edges: Edge[] } {
  const selected = prompts.find((prompt) => prompt.id === selectedPromptId) ?? prompts[0];
  const sourceId = selected?.id ?? selectedPromptId;
  const allIncludeEdges = (flow?.edges ?? []).filter((edge) => edge.source === sourceId);
  const allDependentEdges = (flow?.edges ?? []).filter((edge) => edge.target === sourceId);
  const includeEdges = allIncludeEdges.slice(0, 5);
  const dependentEdges = allDependentEdges.slice(0, 3);
  const includeOverflow = allIncludeEdges.length - includeEdges.length;
  const dependentOverflow = allDependentEdges.length - dependentEdges.length;
  const includeIds = includeEdges.map((edge) => edge.target);
  const dependentIds = dependentEdges.map((edge) => edge.source);
  const promptById = new Map(prompts.map((prompt) => [prompt.id, prompt]));
  const laneWidth = 190;
  const nodes: Node[] = [
    {
      id: sourceId,
      position: { x: 58, y: 96 },
      data: { label: `Source\n${humanPromptName(sourceId)}\nmarkdown` },
      className: 'flow-node selected source',
    },
    {
      id: 'rendered-prompt',
      position: { x: 288, y: 96 },
      data: { label: `Rendered Prompt\nregistry preview\nready to compare` },
      className: 'flow-node rendered',
    },
    {
      id: 'live-agent',
      position: { x: 518, y: 96 },
      data: { label: `Live Agent\nLibreChat managed\nreview before push` },
      className: 'flow-node live',
    },
    {
      id: 'eval-bank',
      position: { x: 288, y: 212 },
      data: { label: `Eval Bank\nsynthetic cases\npublic-safe` },
      className: 'flow-node eval',
    },
    {
      id: 'eval-results',
      position: { x: 518, y: 212 },
      data: { label: `Eval Results\nrun history\nlocal evidence` },
      className: 'flow-node results',
    },
    ...includeIds.map((id, index) => {
      const prompt = promptById.get(id);
      return {
        id,
        position: { x: 58 + (index % 3) * laneWidth, y: 338 + Math.floor(index / 3) * 78 },
        data: { label: `Included\n${humanPromptName(id)}\n${prompt?.family ?? 'prompt'}` },
        className: 'flow-node include',
      };
    }),
    ...(includeOverflow > 0 ? [{
      id: 'included-overflow',
      position: { x: 58 + (includeIds.length % 3) * laneWidth, y: 338 + Math.floor(includeIds.length / 3) * 78 },
      data: { label: `Included\n+${includeOverflow} more\nsee Atlas` },
      className: 'flow-node include muted',
    }] : []),
    ...dependentIds.map((id, index) => ({
      id,
      position: { x: 58 + index * laneWidth, y: 0 },
      data: { label: `Used By\n${humanPromptName(id)}\n${promptById.get(id)?.family ?? 'prompt'}` },
      className: 'flow-node dependent',
    })),
    ...(dependentOverflow > 0 ? [{
      id: 'dependent-overflow',
      position: { x: 58 + dependentIds.length * laneWidth, y: 0 },
      data: { label: `Used By\n+${dependentOverflow} more\nsee Atlas` },
      className: 'flow-node dependent muted',
    }] : []),
  ];
  const edges: Edge[] = [
    { id: 'source-rendered', source: sourceId, target: 'rendered-prompt', type: 'smoothstep', animated: false },
    { id: 'rendered-live', source: 'rendered-prompt', target: 'live-agent', type: 'smoothstep', animated: false },
    { id: 'rendered-eval', source: 'rendered-prompt', target: 'eval-bank', type: 'smoothstep', animated: false },
    { id: 'eval-results', source: 'eval-bank', target: 'eval-results', type: 'smoothstep', animated: false },
    ...includeEdges.map((edge) => ({ id: `include-${edge.source}-${edge.target}`, source: edge.source, target: edge.target, type: 'smoothstep' as const })),
    ...(includeOverflow > 0 ? [{ id: `include-overflow-${sourceId}`, source: sourceId, target: 'included-overflow', type: 'smoothstep' as const }] : []),
    ...dependentEdges.map((edge) => ({ id: `dependent-${edge.source}-${edge.target}`, source: edge.source, target: edge.target, type: 'smoothstep' as const })),
    ...(dependentOverflow > 0 ? [{ id: `dependent-overflow-${sourceId}`, source: 'dependent-overflow', target: sourceId, type: 'smoothstep' as const }] : []),
  ];
  return { nodes, edges };
}

function humanPromptName(id: string) {
  const label = id.split('.').slice(1).join(' ') || id;
  return label.replace(/[._-]+/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}
