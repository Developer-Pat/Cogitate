import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';

interface ReportViewerProps {
  body: string;
  className?: string;
}

/**
 * The shared markdown report renderer — used by the Workflow
 * Products modal (the peek) AND the full-page viewer (the read).
 * One renderer, no drift (the report-viewer mini-map, 2026-08-17).
 */
const ReportViewer: React.FC<ReportViewerProps> = ({ body, className }) => (
  <article className={`prose prose-sm max-w-none dark:prose-invert ${className ?? ''}`}>
    <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
      {body ?? ''}
    </ReactMarkdown>
  </article>
);

export default ReportViewer;
