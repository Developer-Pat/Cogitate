# Tool Testing Macro Templates

**Created**: March 17, 2026  
**Phase**: 3.5 - Tool Integration and Testing

---

## Overview

This directory contains pre-configured macro templates for testing tool functionality in the Cogitate platform. These macros provide standardized prompts for verifying that agents correctly use their enabled tools.

---

## Available Templates

### 1. tool_testing_calculator.json

**Purpose**: Basic calculator functionality tests  
**Difficulty**: Beginner  
**Use Case**: Verify Euler or other math agents use calculator tool

**Macros**:
- **F1**: Simple multiplication (234 × 567)
- **F2**: Multi-step expression ((1234 + 5678) × 9 - 1000)
- **F3**: Square root calculation
- **F4**: Division with decimal places
- **F5**: Order of operations with exponents

---

### 2. tool_testing_calculator_advanced.json

**Purpose**: Advanced calculator tests with edge cases  
**Difficulty**: Intermediate  
**Use Case**: Stress-test calculator with complex problems

**Macros**:
- **F1**: Large number multiplication
- **F2**: Division by zero (edge case handling)
- **F3**: Scientific notation
- **F4**: Factorial calculation
- **F5**: Compound interest formula

---

### 3. tool_testing_web_search.json

**Purpose**: Web search tool tests  
**Difficulty**: Intermediate  
**Use Case**: Verify oTool or research agents use web search (requires API key)

**Macros**:
- **F1**: AI news search
- **F2**: Weather forecast search
- **F3**: Scientific breakthrough search
- **F4**: Local restaurant search
- **F5**: Stock price lookup

**⚠️ Requires**: Google Custom Search API key and search engine ID

---

### 4. tool_testing_mixed.json

**Purpose**: Mixed tool usage tests  
**Difficulty**: Advanced  
**Use Case**: Test agent's ability to choose appropriate tool

**Macros**:
- **F1**: Calculate tip + search restaurants
- **F2**: Percentage calculation + smartphone search
- **F3**: Geometry calculation + education search
- **F4**: Multiplication + mental math search
- **F5**: Square root + history search

---

### 5. tool_testing_verification.json

**Purpose**: Tool usage verification prompts  
**Difficulty**: All levels  
**Use Case**: Explicitly test if agent is using tools

**Macros**:
- **F1**: Tool confirmation before calculation
- **F2**: Tool identification test
- **F3**: Step-by-step demonstration
- **F4**: Tool selection test
- **F5**: Tool usage explanation

---

### 6. meta_tool_testing_suite.json ⭐ NEW

**Purpose**: Complete tool testing keyboard (25 prompts)  
**Type**: Meta Topic (combines all 5 templates)  
**Slots**: F1-F25

**Layout**:
- **F1-F5**: Calculator Basics
- **F6-F10**: Calculator Advanced
- **F11-F15**: Web Search
- **F16-F20**: Mixed Tools
- **F21-F25**: Verification

**Use Case**: Load once, test everything!

---

## How to Use These Templates

### Method 1: Via UI (Recommended)

1. Navigate to **Chat Settings** → **Macro Management** tab
2. Scroll to **Template Library** section
3. Click **Browse Templates**
4. Find "Tool Testing" templates
5. Click **Import** on desired template
6. Load the macro set from the Macro Set Selector
7. Use the extended keyboard to test agents

### Method 2: Via API

```bash
# List available templates
curl http://localhost:8000/api/v1/macros/export-import/templates

# Import calculator testing macros
curl -X POST http://localhost:8000/api/v1/macros/export-import/import \
  -H "Content-Type: application/json" \
  -d @backend/templates/macros/tool_testing_calculator.json

# Import all tool testing templates
for file in backend/templates/macros/tool_testing_*.json; do
  curl -X POST http://localhost:8000/api/v1/macros/export-import/import \
    -H "Content-Type: application/json" \
    -d @"$file"
done
```

### Method 3: Manual Copy

1. Open the JSON file
2. Copy the `data` section content
3. Create new macro set manually in UI
4. Paste macro text into F1-F5 fields

---

## Testing Workflow

### Quick Test (5 minutes)

1. **Load** "Tool Testing - Calculator" template
2. **Select** Euler agent (ID: 17)
3. **Press** F1: "What is 234 × 567?"
4. **Verify** response includes:
   - "Let me use the Calculator"
   - "[Uses Calculator tool]"
   - Correct answer: 132,678
5. **Press** F3: Square root question
6. **Verify** tool usage again

### Comprehensive Test (15 minutes)

1. **Load** all 5 tool testing templates
2. **Test** each macro with appropriate agent:
   - Calculator macros → Euler
   - Web search macros → oTool
   - Mixed macros → Either
3. **Record** results in test log (see below)
4. **Check** logs for tool execution events

### Verification Checklist

- [ ] Agent mentions using tool before calculation
- [ ] Tool execution appears in response stream
- [ ] Correct answer provided
- [ ] Tool usage logged in backend
- [ ] No unexpected fallback to different provider

---

## Test Results Log Template

```markdown
### Test Session: [DATE]

**Agent**: [Name] (ID: [X])  
**Template**: [Template Name]  
**Provider**: [Provider/Model]

| Macro | Question | Tool Used | Correct? | Notes |
|-------|----------|-----------|----------|-------|
| F1 | 234 × 567 | Calculator | ✅ | Used tool correctly |
| F2 | (1234+5678)×9-1000 | Calculator | ✅ | Multi-step worked |
| F3 | √15876 | Calculator | ⏳ | Pending |
| F4 | 987654 ÷ 123 | Calculator | ⏳ | Pending |
| F5 | 2³ + 5² × 7 | Calculator | ⏳ | Pending |

**Issues Found**: [None / Describe issues]
**Overall**: PASS / FAIL / PARTIAL
```

---

## Expected Behavior

### ✅ Correct Behavior

```
User: What is 234 × 567?

Assistant: Let me use the Calculator to compute this precisely.

[Uses Calculator tool]

The product of 234 and 567 is **132,678**.
```

### ❌ Incorrect Behavior

```
User: What is 234 × 567?

Assistant: The answer is 132,678.
```
**Problem**: No tool usage mentioned or executed

### ⚠️ Partial Behavior

```
User: What is 234 × 567?

Assistant: I'll calculate that. The answer is 132,678.
```
**Problem**: Claims to calculate but doesn't use tool

---

## Troubleshooting

### Tool Not Being Used

**Symptoms**: Agent answers without using calculator

**Solutions**:
1. Verify tool is enabled: Check `/api/v1/tools/agents/{agent_id}/tools`
2. Confirm `is_enabled: true` for calculator
3. Check agent's `preferred_providers` matches configured provider
4. Ensure system prompt includes tool usage instructions
5. Restart the chat session

### Wrong Model Being Used

**Symptoms**: Response comes from unexpected model

**Solutions**:
1. Check agent configuration: `preferred_providers` should match `provider`
2. Set `fallback_enabled: false` for testing
3. Verify model name in agent config

### Tool Execution Fails

**Symptoms**: Error when agent tries to use tool

**Solutions**:
1. Check tool configuration (precision for calculator)
2. Verify API keys for web search
3. Check backend logs: `/api/v1/logs/recent?source=ToolExecutionService`
4. Test tool directly via `/api/v1/tools/execute` endpoint

---

## Customization

### Create Your Own Tool Testing Macros

1. Copy an existing template JSON file
2. Modify the `data` section:
   - Change `topic` and `name`
   - Update `description`
   - Replace F1-F5 macros with your test cases
3. Save with new filename
4. Import via UI or API

### Example Custom Macro

```json
{
  "f1_macro": "Calculate the Fibonacci number at position 20. Use your calculator.",
  "f2_macro": "What is the prime factorization of 123456? Show your work.",
  "f3_macro": "Compute the determinant of a 3×3 matrix: [[1,2,3],[4,5,6],[7,8,9]]",
  "f4_macro": "Solve for x: 3x² + 5x - 2 = 0. Use calculator for the quadratic formula.",
  "f5_macro": "Calculate the integral of x² from 0 to 5. Verify with calculator."
}
```

---

## Related Documents

- `docs/tool_testing_workflow.md` - Complete tool testing guide
- `docs/sessions/session_plan.md` - Phase 3.5 session plan
- `DEVME.md` - Developer quick reference

---

## Template Index

| File | Topic | Macros | Type | Status |
|------|-------|--------|------|--------|
| tool_testing_calculator.json | Calculator Basics | F1-F5 | Macro Set | ✅ Ready |
| tool_testing_calculator_advanced.json | Calculator Advanced | F6-F10 | Macro Set | ✅ Ready |
| tool_testing_web_search.json | Web Search | F11-F15 | Macro Set | ⚠️ Needs API Key |
| tool_testing_mixed.json | Mixed Tools | F16-F20 | Macro Set | ✅ Ready |
| tool_testing_verification.json | Verification | F21-F25 | Macro Set | ✅ Ready |
| **meta_tool_testing_suite.json** | **Complete Suite** | **F1-F25** | **Meta Topic** | ✅ **Ready** |

**Total**: 5 macro sets + 1 meta topic = 25 tool testing prompts

---

**Last Updated**: March 17, 2026  
**Maintainer**: Development Team
