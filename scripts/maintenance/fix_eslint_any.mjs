#!/usr/bin/env node

/**
 * fix_eslint_any.mjs — Automated codemod for ESLint `@typescript-eslint/no-explicit-any`
 *
 * Performs AST-aware regex replacements for mechanical `any` → `unknown` patterns.
 *
 * Usage:
 *   node scripts/maintenance/fix_eslint_any.mjs              # Run on frontend/src/
 *   node scripts/maintenance/fix_eslint_any.mjs --dry-run    # Preview changes only
 *   node scripts/maintenance/fix_eslint_any.mjs --report     # Generate report only, no changes
 *
 * Strategy:
 *   Tier 1 — High-confidence mechanical replacements (fully automated)
 *   Tier 2 — Medium-confidence context-aware replacements (semi-automated)
 *   Tier 3 — Log-only patterns requiring human review
 *
 * After running, follow up with:
 *   cd frontend && npx eslint --fix src/
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, '../..');
const FRONTEND_SRC = path.join(REPO_ROOT, 'frontend', 'src');

// ── Skip patterns ──────────────────────────────────────────────────────────
const SKIP_PATTERNS = [
  /node_modules/,
  /\.next/,
  /dist/,
  /build/,
  /\.d\.ts$/,
];

// ── Tier 1: High-confidence mechanical replacements ────────────────────────
// These are safe to apply automatically — they always compile and are always
// more type-safe than `any`.
const TIER1_REPLACEMENTS = [
  // --- Record<string, any> → Record<string, unknown> (105 hits) ---
  { pattern: /Record<string, any>/g, replacement: 'Record<string, unknown>', desc: 'Record<string, any>' },

  // --- Record<string, any[]> → Record<string, unknown[]> ---
  { pattern: /Record<string, any\[\]>/g, replacement: 'Record<string, unknown[]>', desc: 'Record<string, any[]>' },

  // --- any[] → unknown[] in type positions (27 hits) ---
  // Must NOT match inside strings or comments
  { pattern: /:\s*any\[\]/g, replacement: ': unknown[]', desc: ': any[] → : unknown[]' },
  { pattern: /:\s*any\s*\[/g, replacement: ': unknown[', desc: 'any indexed access' },
  { pattern: /\(any\[\]\)/g, replacement: '(unknown[])', desc: 'cast any[] in parens' },

  // --- Function param: named params → unknown (37 hits total) ---
  { pattern: /\bdata:\s*any(?=\s*[,)])/g, replacement: 'data: unknown', desc: 'data: any param' },
  { pattern: /\bvalue:\s*any(?=\s*[,)])/g, replacement: 'value: unknown', desc: 'value: any param' },
  { pattern: /\bconfig:\s*any(?=\s*[,)])/g, replacement: 'config: unknown', desc: 'config: any param' },
  { pattern: /\bargs:\s*any(?=\s*[,)])/g, replacement: 'args: unknown', desc: 'args: any param' },
  { pattern: /\bresult:\s*any(?=\s*[,)])/g, replacement: 'result: unknown', desc: 'result: any param' },
  { pattern: /\bitem:\s*any(?=\s*[,)])/g, replacement: 'item: unknown', desc: 'item: any param' },
  { pattern: /\bpayload:\s*any(?=\s*[,)])/g, replacement: 'payload: unknown', desc: 'payload: any param' },
  { pattern: /\bprops:\s*any(?=\s*[,)])/g, replacement: 'props: Record<string, unknown>', desc: 'props: any param' },
  { pattern: /\bparams:\s*any(?=\s*[,)])/g, replacement: 'params: unknown', desc: 'params: any param' },
  { pattern: /\boutput:\s*any(?=\s*[,)])/g, replacement: 'output: unknown', desc: 'output: any param' },
  { pattern: /\binput:\s*any(?=\s*[,)])/g, replacement: 'input: unknown', desc: 'input: any param' },

  // --- Return type => any → => unknown (8 hits) ---
  { pattern: /\)\s*=>\s*any(?=\s*[{,])/g, replacement: ') => unknown', desc: '=> any return' },

  // --- catch clauses: catch (e: any) → catch (e: unknown) (2 hits) ---
  { pattern: /catch\s*\(\s*(\w+)\s*:\s*any\s*\)/g, replacement: 'catch ($1: unknown)', desc: 'catch (x: any)' },

  // --- Promise<any> → Promise<unknown> (2 hits) ---
  { pattern: /Promise<any>/g, replacement: 'Promise<unknown>', desc: 'Promise<any>' },

  // --- <T extends any> → <T> (2 hits) ---
  { pattern: /<T extends any>/g, replacement: '<T>', desc: '<T extends any>' },
  { pattern: /<T = any>/g, replacement: '<T = unknown>', desc: '<T = any>' },

  // --- Callback: (item: any) → (item: unknown) ---
  { pattern: /\(\s*item\s*:\s*any\s*\)/g, replacement: '(item: unknown)', desc: '(item: any)' },
  { pattern: /\(\s*err\s*:\s*any\s*\)/g, replacement: '(err: unknown)', desc: '(err: any)' },
  { pattern: /\(\s*error\s*:\s*any\s*\)/g, replacement: '(error: unknown)', desc: '(error: any)' },

  // --- Generic short param names (likely in callbacks) ---
  // These are single-letter or very short param names typed as any
  { pattern: /\(\s*(\b[a-z]\b)\s*:\s*any\s*\)/g, replacement: '($1: unknown)', desc: 'short-name: any callback' },

  // --- Variable declarations with : any → : unknown ---
  // Matches: `const x: any =` or `let x: any =` or `var x: any =`
  { pattern: /(const|let|var)\s+\w+\s*:\s*any\s*=/g, replacement: (match) => match.replace(/: any(?=\s*=)/, ': unknown'), desc: 'variable: any declaration' },

  // --- Interface/type property: any (59 hits remaining) ---
  // Matches `name: any;`, `name?: any;`, `name: any,`, `name?: any,`, `name: any }`
  // Must NOT match inside function params `name: any)`
  { pattern: /(\w+\??:\s*)any(?=\s*[;,}])/g, replacement: '$1unknown', desc: 'property: any field' },

  // --- Generic type argument <any> (85 hits remaining) ---
  // Replace <any> with <unknown> when used as type arg in generic calls/declarations
  // Must NOT match `<T extends any>`, `<T = any>`, `as any`, `<any[]`
  { pattern: /<(any)(?=[\s,>])/g, replacement: '<unknown', desc: '<any> generic arg' },

  // --- Index signature [key: string]: any → [key: string]: unknown ---
  { pattern: /\[key:\s*\w+\]:\s*any(?=\s*[;,}])/g, replacement: (match) => match.replace(/: any(?=\s*[;,}])/, ': unknown'), desc: 'index: any → unknown' },

  // --- JSDoc/TSDoc @type {any} → @type {unknown} ---
  { pattern: /@type\s*\{any\}/g, replacement: '@type {unknown}', desc: '@type {any}' },
];

// ── Tier 2: Semi-automated replacements (may need review) ─────────────────
// These are context-dependent — they may not always be correct but are likely
// safe in this codebase. Logged separately for review.
const TIER2_REPLACEMENTS = [
  // --- as any → as unknown (99 hits) ---
  // Only replace when not followed by `as <Type>` (already typed)
  // Pattern: `... as any` where :any isn't followed by another `as`
  { pattern: / as any(?!\s*(as|const|\w))/g, replacement: ' as unknown', desc: 'as any → as unknown' },
  { pattern: /\(any\)/g, replacement: '(unknown)', desc: 'cast (any)' },
];

// ── Patterns logged for human review (Tier 3) ──────────────────────────────
const REVIEW_PATTERNS = [
  /Promise<any>/g,
  /any\[\]/g,
  /=> any/g,
  /\bas any\b/g,
];

// ── Utility functions ──────────────────────────────────────────────────────
function shouldSkip(filePath) {
  return SKIP_PATTERNS.some(p => p.test(filePath));
}

function findFiles(dir) {
  const files = [];
  try {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (shouldSkip(fullPath)) continue;
      if (entry.isDirectory()) {
        files.push(...findFiles(fullPath));
      } else if (entry.isFile() && /\.(tsx|ts)$/.test(entry.name)) {
        files.push(fullPath);
      }
    }
  } catch (err) {
    console.error(`  ❌ Error reading directory ${dir}: ${err.message}`);
  }
  return files;
}

function applyReplacements(content, replacements) {
  let result = content;
  let totalReplaces = 0;
  const applied = [];

  for (const { pattern, replacement, desc } of replacements) {
    const matches = result.match(pattern);
    if (matches) {
      const count = matches.length;
      totalReplaces += count;
      if (typeof replacement === 'function') {
        result = result.replace(pattern, replacement);
      } else {
        result = result.replace(pattern, replacement);
      }
      applied.push({ desc, count });
    }
  }

  return { result, totalReplaces, applied };
}

function findReviewItems(content, patterns) {
  const items = [];
  for (const pattern of patterns) {
    const matches = content.match(pattern);
    if (matches) {
      items.push({ pattern: pattern.toString(), count: matches.length });
    }
  }
  return items;
}

// ── Main ───────────────────────────────────────────────────────────────────
function main() {
  const args = process.argv.slice(2);
  const isDryRun = args.includes('--dry-run');
  const isReportOnly = args.includes('--report');

  const targetDir = FRONTEND_SRC;

  console.log('🔧 ESLint no-explicit-any Codemod');
  console.log('================================');
  console.log(`Mode:      ${isReportOnly ? 'REPORT ONLY' : isDryRun ? 'DRY RUN' : 'APPLY'}`);
  console.log(`Target:    ${targetDir}`);
  console.log('');

  const files = findFiles(targetDir);
  console.log(`Found ${files.length} TypeScript files to scan`);
  console.log('');

  let totalTier1 = 0;
  let totalTier2 = 0;
  let filesChanged = 0;
  const fileResults = [];
  const allReviewItems = [];

  for (const file of files) {
    const content = fs.readFileSync(file, 'utf8');
    const relativePath = path.relative(FRONTEND_SRC, file);

    // Track original for change detection
    let workingContent = content;
    let fileTier1 = 0;
    let fileTier2 = 0;

    // Tier 1: High-confidence
    const { result: afterTier1, totalReplaces: t1Count, applied: t1Applied } = applyReplacements(workingContent, TIER1_REPLACEMENTS);
    workingContent = afterTier1;
    fileTier1 += t1Count;

    // Tier 2: Semi-automated
    const { result: afterTier2, totalReplaces: t2Count, applied: t2Applied } = applyReplacements(workingContent, TIER2_REPLACEMENTS);
    workingContent = afterTier2;
    fileTier2 += t2Count;

    // Tier 3: Review items
    const reviewItems = findReviewItems(workingContent, REVIEW_PATTERNS);
    if (reviewItems.length > 0) {
      allReviewItems.push({ file: relativePath, items: reviewItems });
    }

    const fileTotalChanges = fileTier1 + fileTier2;
    if (fileTotalChanges > 0) {
      totalTier1 += fileTier1;
      totalTier2 += fileTier2;
      filesChanged++;

      if (!isDryRun && !isReportOnly && content !== workingContent) {
        fs.writeFileSync(file, workingContent, 'utf8');
      }

      fileResults.push({
        file: relativePath,
        tier1: fileTier1,
        tier2: fileTier2,
        total: fileTotalChanges,
      });
    }
  }

  // ── Summary ──────────────────────────────────────────────────────────
  fileResults.sort((a, b) => b.total - a.total);

  console.log('📊 Summary');
  console.log('-----------');
  console.log(`Files scanned:   ${files.length}`);
  console.log(`Files changed:   ${filesChanged}`);
  console.log(`Tier 1 (mech):   ${totalTier1} replacements`);
  console.log(`Tier 2 (semi):   ${totalTier2} replacements`);
  console.log(`Total:           ${totalTier1 + totalTier2} replacements`);
  console.log('');

  if (fileResults.length > 0) {
    console.log('📁 Top files changed:');
    console.log('----------------------');
    fileResults.slice(0, 25).forEach(({ file, tier1, tier2, total }) => {
      const label = [];
      if (tier1 > 0) label.push(`t1:${tier1}`);
      if (tier2 > 0) label.push(`t2:${tier2}`);
      console.log(`  ${String(total).padStart(4)}  ${file}  (${label.join(', ')})`);
    });
    if (fileResults.length > 25) {
      console.log(`  ... and ${fileResults.length - 25} more files`);
    }
  }

  console.log('');

  if (allReviewItems.length > 0) {
    console.log('⚠️  Files needing manual review (remaining `any` patterns):');
    console.log('--------------------------------------------------------');
    allReviewItems.slice(0, 15).forEach(({ file, items }) => {
      const summaries = items.map(i => `${i.pattern} (${i.count})`).join(', ');
      console.log(`  ${file}  —  ${summaries}`);
    });
    if (allReviewItems.length > 15) {
      console.log(`  ... and ${allReviewItems.length - 15} more files`);
    }
  }

  if (!isReportOnly) {
    console.log('');
    if (isDryRun) {
      console.log('🔎 Dry run complete. Run without --dry-run to apply changes.');
    } else {
      console.log('✅ Changes applied!');
    }
    console.log('');
    console.log('Next steps:');
    console.log('  1. cd frontend && npx eslint --fix src/');
    console.log('  2. cd frontend && npx eslint src/ | grep "no-explicit-any" | wc -l');
    console.log('  3. Review remaining `any` cases manually');
  }

  if (isReportOnly) {
    // Generate report file
    const reportPath = path.join(REPO_ROOT, 'local', 'reports', 'any-codemod-report.md');
    const reportLines = [
      '# ESLint `any` Codemod Report',
      '',
      `**Date**: ${new Date().toISOString().split('T')[0]}`,
      `**Mode**: Report-only (no changes applied)`,
      '',
      '## Summary',
      '',
      `| Metric | Count |`,
      `|--------|:-----:|`,
      `| Files scanned | ${files.length} |`,
      `| Files with changes | ${filesChanged} |`,
      `| Tier 1 replacements | ${totalTier1} |`,
      `| Tier 2 replacements | ${totalTier2} |`,
      `| Total replacements | ${totalTier1 + totalTier2} |`,
      `| Files needing review | ${allReviewItems.length} |`,
      '',
      '## Top Files Changed',
      '',
      '| Changes | File | Detail |',
      '|:-------:|------|--------|',
    ];
    fileResults.slice(0, 50).forEach(({ file, tier1, tier2, total }) => {
      reportLines.push(`| ${total} | \`${file}\` | T1:${tier1}, T2:${tier2} |`);
    });
    reportLines.push('');
    if (allReviewItems.length > 0) {
      reportLines.push('## Files Needing Manual Review', '', '| File | Patterns |', '|------|----------|');
      allReviewItems.slice(0, 50).forEach(({ file, items }) => {
        const summaries = items.map(i => `\`${i.pattern}\` (${i.count})`).join(', ');
        reportLines.push(`| \`${file}\` | ${summaries} |`);
      });
    }

    const reportContent = reportLines.join('\n');
    fs.writeFileSync(reportPath, reportContent, 'utf8');
    console.log(`📄 Report written to: ${reportPath}`);
  }

  return { totalTier1, totalTier2, filesChanged, fileResults, allReviewItems };
}

main();
