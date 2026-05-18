import { createColumnHelper, flexRender, getCoreRowModel, useReactTable } from '@tanstack/react-table';
import { FileDiff, FlaskConical, ListChecks, PlusCircle, Play, TrendingUp } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { EvalBank, EvalFamily, EvalRun } from '../types';

interface Props {
  evalBank?: EvalBank;
  selectedPromptId: string;
  runs: EvalRun[];
  running: boolean;
  blockedReason?: string;
  onRun: (options: { maxCases: number; live: boolean; family?: string; surface?: string; promptId: string }) => void;
  onSaveCase: (options: { familyId: string; caseId: string; updatedCase: Record<string, unknown>; create?: boolean }) => void;
}

type EvalRow = {
  family: string;
  caseId: string;
  surface: string;
  expected: string;
  rubric: number;
  prompt: string;
  rubricItems: string[];
  promptRefs: string[];
  expectedDecision?: string;
  expectedSurface?: string;
  expectedKey?: 'expected_decision' | 'expected_surface';
};

const columnHelper = createColumnHelper<EvalRow>();
const columns = [
  columnHelper.accessor('family', { header: 'Eval Family' }),
  columnHelper.accessor('caseId', { header: 'Case' }),
  columnHelper.accessor('surface', { header: 'Surface' }),
  columnHelper.accessor('expected', { header: 'Expected' }),
  columnHelper.accessor('rubric', { header: 'Rubric Items' }),
];

export function EvalPanel({ evalBank, selectedPromptId, runs, running, blockedReason, onRun, onSaveCase }: Props) {
  const rows = useMemo(() => flattenEvalRows(evalBank?.families ?? []), [evalBank]);
  const families = Array.from(new Set(rows.map((row) => row.family)));
  const linkedRows = rows.filter((row) => row.promptRefs.includes(selectedPromptId) || selectedPromptId === 'main.conscious_agent');
  const [family, setFamily] = useState('');
  const [surface, setSurface] = useState('');
  const [maxCases, setMaxCases] = useState(1);
  const [live, setLive] = useState(false);
  const [linkedOnly, setLinkedOnly] = useState(true);
  const [selectedCaseKey, setSelectedCaseKey] = useState('');
  const [creatingCase, setCreatingCase] = useState(false);
  const sourceRows = linkedOnly ? linkedRows : rows;
  const sourceFamilies = Array.from(new Set(sourceRows.map((row) => row.family)));
  const selectedFamily = family;
  const targetFamily = selectedFamily || sourceFamilies[0] || families[0] || '';
  const visibleRows = sourceRows.filter((row) => (!selectedFamily || row.family === selectedFamily) && (!surface || row.surface === surface));
  const selectedCase = creatingCase
    ? undefined
    : visibleRows.find((row) => `${row.family}/${row.caseId}` === selectedCaseKey) ?? visibleRows[0];
  const [casePrompt, setCasePrompt] = useState('');
  const [caseExpected, setCaseExpected] = useState('');
  const [caseRubric, setCaseRubric] = useState('');
  const [caseSurface, setCaseSurface] = useState('web');
  const [caseIdDraft, setCaseIdDraft] = useState('');
  const newCaseIdRef = useRef<HTMLInputElement | null>(null);
  const newCaseSurfaceRef = useRef<HTMLSelectElement | null>(null);
  const newCasePromptRef = useRef<HTMLTextAreaElement | null>(null);
  const newCaseExpectedRef = useRef<HTMLInputElement | null>(null);
  const newCaseRubricRef = useRef<HTMLTextAreaElement | null>(null);
  const table = useReactTable({ data: visibleRows, columns, getCoreRowModel: getCoreRowModel() });
  const promptRuns = runs.filter((run) => run.promptId === selectedPromptId || selectedPromptId === 'main.conscious_agent');

  useEffect(() => {
    if (creatingCase) return;
    if (!selectedCase) return;
    setSelectedCaseKey(`${selectedCase.family}/${selectedCase.caseId}`);
    setCaseIdDraft(selectedCase.caseId);
    setCaseSurface(selectedCase.surface || 'web');
    setCasePrompt(selectedCase.prompt);
    setCaseExpected(selectedCase.expectedDecision ?? selectedCase.expectedSurface ?? '');
    setCaseRubric(selectedCase.rubricItems.join('\n'));
  }, [creatingCase, selectedCase?.family, selectedCase?.caseId]);

  const beginNewCase = () => {
    const suffix = new Date().toISOString().slice(0, 10).replace(/-/g, '');
    setCreatingCase(true);
    setSelectedCaseKey('');
    setCaseIdDraft(`new_eval_case_${suffix}`);
    setCaseSurface(surface || 'web');
    setCasePrompt('');
    setCaseExpected('');
    setCaseRubric('checks the target behavior clearly');
  };

  const cancelNewCase = () => {
    setCreatingCase(false);
    if (selectedCase) {
      setSelectedCaseKey(`${selectedCase.family}/${selectedCase.caseId}`);
    }
  };

  return (
    <div className="eval-panel">
      <div className="section-title">
        <FlaskConical size={16} />
        <span>Eval Designer and Results</span>
      </div>
      <div className="eval-summary">
        <div><strong>{evalBank?.familyCount ?? 0}</strong><span>families</span></div>
        <div><strong>{linkedRows.length}</strong><span>linked cases</span></div>
        <div><strong>{humanPromptName(selectedPromptId)}</strong><span>linked prompt</span></div>
        <div><strong>{promptRuns.length}</strong><span>runs for prompt</span></div>
      </div>
      {blockedReason && (
        <div className="workflow-callout eval-block">
          <strong>Eval is waiting on draft review</strong>
          <span>{blockedReason}</span>
        </div>
      )}
      <div className="eval-layout">
        <div className="eval-designer">
          <h3><ListChecks size={15} /> Run Eval Cases</h3>
          <label className="inline-toggle">
            <input type="checkbox" checked={linkedOnly} onChange={(event) => setLinkedOnly(event.target.checked)} />
            <span>show only cases linked to this prompt</span>
          </label>
          <label>
            Family
            <select value={selectedFamily} onChange={(event) => setFamily(event.target.value)}>
              <option value="">all linked families</option>
              {sourceFamilies.map((family) => <option key={family}>{family}</option>)}
            </select>
          </label>
          <label>
            Surface
            <select value={surface} onChange={(event) => setSurface(event.target.value)}>
              <option value="">all</option>
              <option>web</option>
              <option>voice</option>
              <option>telegram</option>
              <option>scheduler</option>
              <option>wing</option>
            </select>
          </label>
          <label>
            Cases
            <input type="number" min={1} max={25} value={maxCases} onChange={(event) => setMaxCases(Number(event.target.value || 1))} />
          </label>
          <label className="inline-toggle">
            <input type="checkbox" checked={live} onChange={(event) => setLive(event.target.checked)} />
            <span>live exact-model run</span>
          </label>
          <textarea value={`${visibleRows.length} case(s) selected. ${live ? 'Live eval calls the exact-model harness and records performance.' : 'Preview validates selection only: no model call, no score.'}`} readOnly />
          <button
            className="toolbar-button primary compact"
            disabled={running}
            title={blockedReason || (live ? 'Run selected cases through the exact-model harness' : 'Preview selected cases without model calls')}
            onClick={() => {
              if (blockedReason) return;
              onRun({ maxCases, live, family: selectedFamily, surface, promptId: selectedPromptId });
            }}
          >
            <Play size={15} />
            {blockedReason ? 'Review draft first' : live ? 'Run live eval' : 'Run preview'}
          </button>
          <button className="toolbar-button compact" onClick={() => window.setTimeout(beginNewCase, 0)}>
            <PlusCircle size={15} />
            New eval case
          </button>
        </div>
        <div className="eval-table-wrap">
          <table className="eval-table">
            <thead>
              {table.getHeaderGroups().map((headerGroup) => (
                <tr key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <th key={header.id}>{flexRender(header.column.columnDef.header, header.getContext())}</th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.slice(0, 10).map((row) => (
                <tr
                  key={row.id}
                  className={`${selectedCase?.family === row.original.family && selectedCase?.caseId === row.original.caseId ? 'selected' : ''}`}
                  onClick={() => {
                    setCreatingCase(false);
                    setSelectedCaseKey(`${row.original.family}/${row.original.caseId}`);
                  }}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="eval-case-editor">
          <div className="editor-title-row">
            <h3><FileDiff size={15} /> {creatingCase ? 'Create Eval Case' : 'Edit Selected Eval'}</h3>
            {creatingCase && <button className="toolbar-button compact secondary-action" onClick={cancelNewCase}>Cancel</button>}
          </div>
          {selectedCase || creatingCase ? (
            <>
              <strong>{targetFamily}/{creatingCase ? caseIdDraft : selectedCase?.caseId}</strong>
              <label>
                Case ID
                {creatingCase ? (
                  <input key="create-case-id" ref={newCaseIdRef} defaultValue={caseIdDraft} />
                ) : (
                  <input key="edit-case-id" value={caseIdDraft} disabled onChange={(event) => setCaseIdDraft(event.target.value)} />
                )}
              </label>
              <label>
                Surface
                {creatingCase ? (
                  <select key="create-case-surface" ref={newCaseSurfaceRef} defaultValue={caseSurface}>
                    <option>web</option>
                    <option>voice</option>
                    <option>telegram</option>
                    <option>scheduler</option>
                    <option>wing</option>
                    <option>listen_only</option>
                  </select>
                ) : (
                  <select key="edit-case-surface" value={caseSurface} onChange={(event) => setCaseSurface(event.target.value)}>
                    <option>web</option>
                    <option>voice</option>
                    <option>telegram</option>
                    <option>scheduler</option>
                    <option>wing</option>
                    <option>listen_only</option>
                  </select>
                )}
              </label>
              <label>
                Prompt
                {creatingCase ? (
                  <textarea key="create-case-prompt" ref={newCasePromptRef} defaultValue={casePrompt} />
                ) : (
                  <textarea key="edit-case-prompt" value={casePrompt} onChange={(event) => setCasePrompt(event.target.value)} />
                )}
              </label>
              <label>
                {selectedCase?.expectedKey === 'expected_surface' ? 'Expected surface' : 'Expected decision'}
                {creatingCase ? (
                  <input key="create-case-expected" ref={newCaseExpectedRef} defaultValue={caseExpected} />
                ) : (
                  <input key="edit-case-expected" value={caseExpected} onChange={(event) => setCaseExpected(event.target.value)} />
                )}
              </label>
              <label>
                Rubric
                {creatingCase ? (
                  <textarea key="create-case-rubric" ref={newCaseRubricRef} defaultValue={caseRubric} />
                ) : (
                  <textarea key="edit-case-rubric" value={caseRubric} onChange={(event) => setCaseRubric(event.target.value)} />
                )}
              </label>
              <button
                className="toolbar-button compact"
                onClick={() => {
                  const formSurface = creatingCase ? newCaseSurfaceRef.current?.value ?? caseSurface : caseSurface;
                  const formPrompt = creatingCase ? newCasePromptRef.current?.value ?? casePrompt : casePrompt;
                  const formExpected = creatingCase ? newCaseExpectedRef.current?.value ?? caseExpected : caseExpected;
                  const formRubric = creatingCase ? newCaseRubricRef.current?.value ?? caseRubric : caseRubric;
                  const updatedCase = {
                    surface: formSurface,
                    prompt: formPrompt,
                    rubric: formRubric.split('\n').map((line) => line.trim()).filter(Boolean),
                    ...(formExpected
                      ? { [selectedCase?.expectedKey ?? 'expected_decision']: formExpected }
                      : {}),
                  };
                  if (creatingCase) {
                    onSaveCase({
                      familyId: targetFamily,
                      caseId: newCaseIdRef.current?.value.trim() || caseIdDraft.trim(),
                      updatedCase,
                      create: true,
                    });
                    return;
                  }
                  if (!selectedCase) return;
                  onSaveCase({
                    familyId: selectedCase.family,
                    caseId: selectedCase.caseId,
                    updatedCase,
                  });
                }}
              >
                <FileDiff size={15} />
                {creatingCase ? 'Save new eval draft' : 'Save eval draft'}
              </button>
            </>
          ) : <p className="small-copy">Select an eval case to edit.</p>}
        </div>
        <div className="trend-card">
          <TrendingUp size={16} />
          <strong>Results</strong>
          <p>Runs stay linked to the selected prompt hash. Public views show sanitized summaries only.</p>
          <div className="run-list">
            {promptRuns.slice(0, 5).map((run) => (
              <div className="run-row" key={run.id}>
                <code>{run.id}</code>
                <span>{run.live ? 'live exact-model' : 'selection preview'}</span>
                <small>{run.returnCode === 0 ? 'ok' : `code ${run.returnCode}`} · {run.resultCount ?? run.maxCases} case(s) · {run.live ? 'scored run' : 'no score'}{run.promptHash ? ` · ${run.promptHash}` : ''}</small>
              </div>
            ))}
            {!promptRuns.length && <small>No runs yet for this prompt.</small>}
          </div>
        </div>
      </div>
    </div>
  );
}

function humanPromptName(id: string) {
  const label = id.split('.').slice(1).join(' ') || id;
  return label.replace(/[._-]+/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function flattenEvalRows(families: EvalFamily[]): EvalRow[] {
  return families.flatMap((family) =>
    (family.cases ?? []).map((testCase) => ({
      family: family.id,
        caseId: testCase.id,
        surface: testCase.surface,
        expected: testCase.expected_decision ?? testCase.expected_surface ?? 'rubric',
        rubric: testCase.rubric?.length ?? 0,
        prompt: testCase.prompt ?? '',
        rubricItems: testCase.rubric ?? [],
        promptRefs: testCase.promptRefs ?? family.promptRefs ?? ['main.conscious_agent'],
        expectedDecision: testCase.expected_decision,
        expectedSurface: testCase.expected_surface,
        expectedKey: testCase.expected_surface ? 'expected_surface' : testCase.expected_decision ? 'expected_decision' : undefined,
      })),
  );
}
