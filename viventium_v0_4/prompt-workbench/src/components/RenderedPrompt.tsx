import { Fragment, useState, type ReactNode } from 'react';

interface Props {
  markdown: string;
}

type MarkdownBlock =
  | { kind: 'heading'; level: number; text: string }
  | { kind: 'paragraph'; text: string }
  | { kind: 'list'; ordered: boolean; items: string[] }
  | { kind: 'quote'; lines: string[] }
  | { kind: 'code'; language: string; text: string };

export function RenderedPrompt({ markdown }: Props) {
  const [mode, setMode] = useState<'read' | 'raw'>('read');
  const blocks = parseMarkdown(markdown);
  return (
    <div className="rendered-preview rendered-document">
      <div className="rendered-mode-toggle segmented slim" role="tablist" aria-label="Rendered prompt mode">
        <button role="tab" aria-selected={mode === 'read'} className={mode === 'read' ? 'active' : ''} onClick={() => setMode('read')}>Read</button>
        <button role="tab" aria-selected={mode === 'raw'} className={mode === 'raw' ? 'active' : ''} onClick={() => setMode('raw')}>Raw</button>
      </div>
      {mode === 'read' ? blocks.map((block, index) => renderBlock(block, index)) : (
        <pre className="rendered-raw-text">{markdown}</pre>
      )}
    </div>
  );
}

function parseMarkdown(markdown: string): MarkdownBlock[] {
  const lines = markdown.replace(/\r\n?/g, '\n').split('\n');
  const blocks: MarkdownBlock[] = [];
  let paragraph: string[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;
  let quote: string[] = [];
  let code: { language: string; lines: string[] } | null = null;

  const flushParagraph = () => {
    const text = paragraph.join(' ').trim();
    if (text) blocks.push({ kind: 'paragraph', text });
    paragraph = [];
  };
  const flushList = () => {
    if (list?.items.length) blocks.push({ kind: 'list', ordered: list.ordered, items: list.items });
    list = null;
  };
  const flushQuote = () => {
    if (quote.length) blocks.push({ kind: 'quote', lines: quote });
    quote = [];
  };
  const flushText = () => {
    flushParagraph();
    flushList();
    flushQuote();
  };

  for (const line of lines) {
    const trimmed = line.trim();
    if (code) {
      if (trimmed.startsWith('```')) {
        blocks.push({ kind: 'code', language: code.language, text: code.lines.join('\n') });
        code = null;
      } else {
        code.lines.push(line);
      }
      continue;
    }
    if (trimmed.startsWith('```')) {
      flushText();
      code = { language: trimmed.slice(3).trim(), lines: [] };
      continue;
    }
    if (!trimmed) {
      flushText();
      continue;
    }

    const heading = /^(#{1,6})\s+(.+)$/.exec(trimmed);
    if (heading) {
      flushText();
      blocks.push({ kind: 'heading', level: heading[1].length, text: heading[2].trim() });
      continue;
    }
    const quoteMatch = /^>\s?(.*)$/.exec(line);
    if (quoteMatch) {
      flushParagraph();
      flushList();
      quote.push(quoteMatch[1]);
      continue;
    }

    const unordered = /^(\s*)[-*+]\s+(.+)$/.exec(line);
    const ordered = /^(\s*)\d+[.)]\s+(.+)$/.exec(line);
    if (unordered || ordered) {
      flushParagraph();
      flushQuote();
      const nextOrdered = Boolean(ordered);
      if (!list || list.ordered !== nextOrdered) flushList();
      list ??= { ordered: nextOrdered, items: [] };
      list.items.push((unordered?.[2] ?? ordered?.[2] ?? '').trim());
      continue;
    }
    if (list && /^\s{2,}\S/.test(line)) {
      list.items[list.items.length - 1] = `${list.items[list.items.length - 1]} ${trimmed}`;
      continue;
    }

    flushList();
    flushQuote();
    paragraph.push(trimmed);
  }

  if (code) blocks.push({ kind: 'code', language: code.language, text: code.lines.join('\n') });
  flushText();
  return blocks;
}

function renderBlock(block: MarkdownBlock, index: number) {
  if (block.kind === 'heading') {
    const content = renderInline(block.text);
    if (block.level <= 1) return <h2 key={index}>{content}</h2>;
    if (block.level === 2) return <h3 key={index}>{content}</h3>;
    if (block.level === 3) return <h4 key={index}>{content}</h4>;
    return <h5 key={index}>{content}</h5>;
  }
  if (block.kind === 'paragraph') {
    return <p key={index}>{renderInline(block.text)}</p>;
  }
  if (block.kind === 'list') {
    const List = block.ordered ? 'ol' : 'ul';
    return (
      <List key={index}>
        {block.items.map((item, itemIndex) => (
          <li key={`${index}-${itemIndex}`}>{renderInline(item)}</li>
        ))}
      </List>
    );
  }
  if (block.kind === 'quote') {
    return (
      <blockquote key={index}>
        {block.lines.map((line, lineIndex) => (
          <p key={`${index}-${lineIndex}`}>{renderInline(line)}</p>
        ))}
      </blockquote>
    );
  }
  if (block.kind === 'code') {
    return (
      <pre key={index} className="rendered-code-block">
        <code>{block.text}</code>
      </pre>
    );
  }
  return null;
}

function renderInline(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const pattern = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*\n]+\*|\[[^\]]+\]\([^)]+\))/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text))) {
    if (match.index > lastIndex) nodes.push(text.slice(lastIndex, match.index));
    const token = match[0];
    const key = `${match.index}-${token}`;
    if (token.startsWith('`')) {
      nodes.push(<code key={key}>{token.slice(1, -1)}</code>);
    } else if (token.startsWith('**')) {
      nodes.push(<strong key={key}>{renderInline(token.slice(2, -2))}</strong>);
    } else if (token.startsWith('*')) {
      nodes.push(<em key={key}>{renderInline(token.slice(1, -1))}</em>);
    } else {
      const link = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(token);
      const href = safeHref(link?.[2] ?? '');
      nodes.push(href ? <a key={key} href={href} target="_blank" rel="noreferrer">{link?.[1]}</a> : <Fragment key={key}>{link?.[1] ?? token}</Fragment>);
    }
    lastIndex = match.index + token.length;
  }
  if (lastIndex < text.length) nodes.push(text.slice(lastIndex));
  return nodes;
}

function safeHref(href: string) {
  if (/^(https?:|mailto:|#|\/)/.test(href)) return href;
  return '';
}
