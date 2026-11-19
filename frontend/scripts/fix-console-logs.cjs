const fs = require('fs');
const path = require('path');

// Files to process
const filesToProcess = [
  'src/services/profilesService.ts',
  'src/hooks/useAgentInteraction.ts',
  'src/utils/mockDetector.ts',
  'src/hooks/useSessionManagement.ts',
  'src/hooks/useLogs.ts',
  'src/services/sessionSyncService.ts',
  'src/components/AgentProfiles/ProfileDetail.tsx',
  'src/services/logsService.ts',
  'src/services/frontendLoggingService.ts',
  'src/components/features/agentInteraction/ResponseStream.tsx',
  'src/components/features/agentInteraction/SessionManager.tsx',
  'src/services/logStoreInstance.ts',
  'src/components/AgentProfiles/ProfileImageUpload.tsx',
  'src/services/domains/providers/mockProviderService.ts',
  'src/services/sseClient.ts',
  'src/services/chatSettingsService.ts',
  'src/services/agentService.ts',
  'src/pages/ChatSettings.tsx',
  'src/components/features/agentInteraction/SessionActions.tsx',
  'src/services/domains/providers/realProviderService.ts',
  'src/components/ui/tables/UsageExample.tsx',
  'src/pages/Debugging.tsx',
  'src/hooks/useSettings.ts',
  'src/hooks/useConfiguration.ts',
  'src/services/runtimeConfigService.ts',
  'src/services/domains/llm/chatService.ts',
  'src/pages/RealTimeMonitor.tsx',
  'src/pages/AgentVersions.tsx'
];

// Check if frontendLoggingService is already imported, if not add it
function ensureImport(content) {
  // Check if already imported
  if (content.includes('frontendLoggingService')) {
    return content;
  }

  // Find the first import statement
  const importMatch = content.match(/^(import\s+.*?;)/m);
  if (importMatch) {
    const importStatement = "import { frontendLoggingService } from '../services/frontendLoggingService'\n";
    return content.replace(/^(import\s+.*?;)/m, importStatement + '$1');
  }

  return content;
}

// Replace console.log patterns
function replaceConsoleLogs(content, sourceName) {
  let result = content;
  let count = 0;

  // Pattern 1: console.error with message
  result = result.replace(/console\.error\(\s*['"]([^'"]+)['"]\s*,?\s*([^)]*)\)/g, (match, message, context) => {
    count++;
    const contextArg = context.trim() ? `, ${context.trim()}` : '';
    return `frontendLoggingService.error('${sourceName}', '${message}'${contextArg})`;
  });

  // Pattern 2: console.warn with message
  result = result.replace(/console\.warn\(\s*['"]([^'"]+)['"]\s*,?\s*([^)]*)\)/g, (match, message, context) => {
    count++;
    const contextArg = context.trim() ? `, ${context.trim()}` : '';
    return `frontendLoggingService.warning('${sourceName}', '${message}'${contextArg})`;
  });

  // Pattern 3: console.log with tag pattern [Tag] message
  result = result.replace(/console\.log\(\s*['"]\[([^\]]+)\][^'"]*['"]\s*,?\s*([^)]*)\)/g, (match, tag, rest) => {
    count++;
    // Extract message and context from rest
    const parts = rest.split(',').map(p => p.trim());
    const message = parts[0]?.replace(/^['"]|['"]$/g, '') || 'Log message';
    const contextArgs = parts.slice(1).join(', ');
    return `frontendLoggingService.debug('${tag}', '${message}'${contextArgs ? ', ' + contextArgs : ''})`;
  });

  // Pattern 4: console.log with emoji pattern (debug logs)
  result = result.replace(/console\.log\(\s*['"](🛑|✅|❌|🔍|📊|🟢|🔵|➕|📤|📥|✏️|🧹|📝|🏁|📋|📌|🔄|⚠️|💥|💬|⏱️)[^'"]*['"]\s*,?\s*([^)]*)\)/g, (match, emoji, rest) => {
    count++;
    const parts = rest.split(',').map(p => p.trim());
    const message = parts[0]?.replace(/^['"]|['"]$/g, '') || 'Log message';
    const contextArgs = parts.slice(1).join(', ');
    return `frontendLoggingService.debug('${sourceName}', '${message.replace(/'/g, "\\'")}'${contextArgs ? ', ' + contextArgs : ''})`;
  });

  // Pattern 5: Generic console.log
  result = result.replace(/console\.log\(\s*['"]([^'"]+)['"]\s*,?\s*([^)]*)\)/g, (match, message, context) => {
    count++;
    const contextArg = context.trim() ? `, ${context.trim()}` : '';
    return `frontendLoggingService.debug('${sourceName}', '${message}'${contextArg})`;
  });

  // Pattern 6: console.log with variables (no string literal first)
  result = result.replace(/console\.log\((?![\s]*['"])/g, (match) => {
    count++;
    return `frontendLoggingService.debug('${sourceName}', `;
  });

  return { result, count };
}

// Process a single file
function processFile(filePath) {
  const fullPath = path.join(process.cwd(), filePath);
  
  if (!fs.existsSync(fullPath)) {
    console.log(`⚠️  File not found: ${filePath}`);
    return;
  }

  let content = fs.readFileSync(fullPath, 'utf8');
  
  // Extract source name from file path
  const sourceName = path.basename(filePath).replace(/\.(tsx?|ts)$/, '');

  // Ensure import exists
  content = ensureImport(content);

  // Replace console logs
  const { result, count } = replaceConsoleLogs(content, sourceName);

  if (count > 0) {
    fs.writeFileSync(fullPath, result, 'utf8');
    console.log(`✓ Fixed ${count} console calls in ${filePath}`);
  } else {
    console.log(`- No console calls found in ${filePath}`);
  }
}

// Main execution
console.log('🔧 Starting console.log replacement...\n');

filesToProcess.forEach(processFile);

console.log('\n✅ Done! Please review the changes and run tests.');
