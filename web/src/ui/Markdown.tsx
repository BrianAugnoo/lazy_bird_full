import DOMPurify from 'dompurify';
import { marked } from 'marked';
import { useMemo } from 'react';

/** Renders untrusted markdown safely. */
export function Markdown({ text, className = '' }: { text: string; className?: string }) {
  const html = useMemo(() => DOMPurify.sanitize(marked.parse(text, { async: false, gfm: true, breaks: true }) as string), [text]);
  return <div className={`markdown-body ${className}`} dangerouslySetInnerHTML={{ __html: html }} />;
}
