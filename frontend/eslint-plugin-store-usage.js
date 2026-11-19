/**
 * ESLint Plugin for Store Usage Detection
 * 
 * Custom rules to detect dual-store anti-patterns and enforce
 * single source of truth principles.
 */

import { ESLintUtils } from '@typescript-eslint/utils'

const createRule = ESLintUtils.RuleCreator(
  (name) => `https://github.com/cogitate/cogitate/blob/main/docs/architecture/state-management.md`
)

/**
 * Rule: no-deprecated-stores
 * 
 * Detects usage of deprecated or removed stores
 */
const noDeprecatedStores = createRule({
  name: 'no-deprecated-stores',
  meta: {
    type: 'problem',
    docs: {
      description: 'Disallow usage of deprecated or removed stores',
      recommended: 'error',
    },
    messages: {
      deprecated: '{{store}} is deprecated. {{migration}}',
    },
    schema: [],
    fixable: 'code',
  },
  defaultOptions: [],
  create(context) {
    return {
      ImportDeclaration(node) {
        // Check for deprecated store imports
        if (node.source.value.includes('stores/')) {
          node.specifiers.forEach((specifier) => {
            if (specifier.type === 'ImportSpecifier') {
              const importName = specifier.imported.name

              if (importName === 'useAppStore' || importName === 'useAppActions') {
                context.report({
                  node: specifier,
                  messageId: 'deprecated',
                  data: {
                    store: 'useAppStore',
                    migration: 'Use notificationStore instead',
                  },
                })
              }

              if (importName === 'useAgentStore') {
                context.report({
                  node: specifier,
                  messageId: 'deprecated',
                  data: {
                    store: 'useAgentStore',
                    migration: 'Use cognitiveHubStore instead',
                  },
                })
              }
            }
          })
        }
      },
    }
  },
})

/**
 * Rule: no-dual-agent-store
 * 
 * Detects when both cognitiveHubStore and agentStore are imported
 */
const noDualAgentStore = createRule({
  name: 'no-dual-agent-store',
  meta: {
    type: 'problem',
    docs: {
      description: 'Disallow using both cognitiveHubStore and agentStore',
      recommended: 'error',
    },
    messages: {
      dualStore: 'Using both cognitiveHubStore and agentStore creates state duplication. Use cognitiveHubStore only.',
    },
    schema: [],
  },
  defaultOptions: [],
  create(context) {
    let hasCognitiveHub = false
    let hasAgentStore = false
    let agentStoreNode = null

    return {
      ImportDeclaration(node) {
        if (node.source.value.includes('stores/')) {
          node.specifiers.forEach((specifier) => {
            if (specifier.type === 'ImportSpecifier') {
              const importName = specifier.imported.name

              if (importName === 'useCognitiveHubStore') {
                hasCognitiveHub = true
              }

              if (importName === 'useAgentStore') {
                hasAgentStore = true
                agentStoreNode = specifier
              }
            }
          })
        }
      },

      'Program:exit'() {
        if (hasCognitiveHub && hasAgentStore && agentStoreNode) {
          context.report({
            node: agentStoreNode,
            messageId: 'dualStore',
          })
        }
      },
    }
  },
})

/**
 * Rule: prefer-cognitive-hub-for-agent-state
 * 
 * Ensures agent state is accessed from cognitiveHubStore, not other stores
 */
const preferCognitiveHubForAgentState = createRule({
  name: 'prefer-cognitive-hub-for-agent-state',
  meta: {
    type: 'suggestion',
    docs: {
      description: 'Prefer cognitiveHubStore for agent state access',
      recommended: 'warn',
    },
    messages: {
      prefer: 'Access agent state from cognitiveHubStore, not {{store}}',
    },
    schema: [],
  },
  defaultOptions: [],
  create(context) {
    return {
      MemberExpression(node) {
        // Check for selectedAgent access from non-cognitiveHub stores
        if (node.property.type === 'Identifier' && node.property.name === 'selectedAgent') {
          if (node.object.type === 'CallExpression') {
            if (node.object.callee.type === 'Identifier') {
              const storeName = node.object.callee.name
              if (storeName !== 'useCognitiveHubStore' && storeName.includes('Store')) {
                context.report({
                  node: node.property,
                  messageId: 'prefer',
                  data: { store: storeName },
                })
              }
            }
          }
        }
      },
    }
  },
})

export default {
  rules: {
    'no-deprecated-stores': noDeprecatedStores,
    'no-dual-agent-store': noDualAgentStore,
    'prefer-cognitive-hub-for-agent-state': preferCognitiveHubForAgentState,
  },
}
