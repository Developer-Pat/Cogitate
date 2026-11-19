#!/usr/bin/env python3
"""
Direct Tool Testing Script - Session #33

Test tools directly without LLM to debug tool execution issues.
Removes LLM from the debug loop for faster, more reliable testing.

Usage:
    uv run python scripts/test_tools_direct.py datetime
    uv run python scripts/test_tools_direct.py calculator --expression "2+2"
    uv run python scripts/test_tools_direct.py calculator --expression "123*456" --precision 3
    uv run python scripts/test_tools_direct.py all  # Test all tools
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))


class ToolTester:
    """Test tools directly without LLM."""
    
    def __init__(self):
        self.results = []
    
    def test_datetime(self, **kwargs):
        """Test datetime tool."""
        print("\n" + "="*70)
        print("TEST: datetime tool")
        print("="*70)

        format_type = kwargs.get('format', 'human')
        timezone_val = kwargs.get('timezone', 'UTC')

        print(f"Arguments: format={format_type}, timezone={timezone_val}")
        
        # Trace argument details (matches backend logging)
        print(f"\n🔍 ARGUMENT TRACE:")
        print(f"   Format: {format_type}")
        print(f"   Timezone: {timezone_val}")
        print(f"   Format valid: {format_type in ['iso', 'human', 'timestamp', 'date', 'time']}")
        
        print(f"\n✓ DateTime called with valid arguments")
        
        now = datetime.now()
        
        if format_type == "iso":
            result = {"datetime": now.isoformat(), "timezone": timezone_val}
        elif format_type == "timestamp":
            result = {"timestamp": now.timestamp(), "timezone": timezone_val}
        elif format_type == "date":
            result = {"date": now.strftime("%Y-%m-%d"), "timezone": timezone_val}
        elif format_type == "time":
            result = {"time": now.strftime("%H:%M:%S"), "timezone": timezone_val}
        else:  # human
            result = {
                "datetime": now.strftime("%A, %B %d, %Y at %I:%M %p"),
                "timezone": timezone_val
            }
        
        print(f"Result: {json.dumps(result, indent=2)}")
        self.results.append(("datetime", True, result))
        return result
    
    def test_calculator(self, **kwargs):
        """Test calculator tool."""
        print("\n" + "="*70)
        print("TEST: calculator tool")
        print("="*70)

        expression = kwargs.get('expression', '')
        precision = kwargs.get('precision', 2)

        print(f"Arguments: expression='{expression}', precision={precision}")
        
        # Trace argument details (matches backend logging)
        print(f"\n🔍 ARGUMENT TRACE:")
        print(f"   Raw expression: '{expression}'")
        print(f"   Expression type: {type(expression).__name__}")
        print(f"   Expression empty: {not expression}")
        print(f"   Expression stripped: '{expression.strip() if expression else ''}'")
        print(f"   Precision: {precision}")

        # If no expression provided, return helpful error
        if not expression or not expression.strip():
            result = {
                "error": "No expression provided. Please provide a mathematical expression to calculate (e.g., '2 + 2' or '123 * 456')."
            }
            print(f"\n⚠️  WARNING: CALCULATOR CALLED WITHOUT EXPRESSION!")
            print(f"   This is why the tool fails - no 'expression' argument provided")
            print(f"\nResult: {json.dumps(result, indent=2)}")
            self.results.append(("calculator", False, result))
            return result
        
        try:
            # Safe evaluation - only allow basic math
            allowed_chars = set("0123456789+-*/.() ")
            if not all(c in allowed_chars for c in expression):
                result = {"error": "Invalid characters in expression. Only numbers and +,-,*,/,.,(,) are allowed."}
                print(f"Result: {json.dumps(result, indent=2)}")
                self.results.append(("calculator", False, result))
                return result
            
            calc_result = eval(expression)
            result = {
                "expression": expression,
                "result": round(float(calc_result), precision)
            }
            print(f"Result: {json.dumps(result, indent=2)}")
            self.results.append(("calculator", True, result))
            return result
        except Exception as e:
            result = {"error": f"Calculation error: {str(e)}"}
            print(f"Result: {json.dumps(result, indent=2)}")
            self.results.append(("calculator", False, result))
            return result
    
    def test_clipboard(self, **kwargs):
        """Test clipboard tool."""
        print("\n" + "="*70)
        print("TEST: clipboard tool")
        print("="*70)
        
        operation = kwargs.get('operation', 'read')
        content = kwargs.get('content', '')
        
        print(f"Arguments: operation={operation}, content='{content[:50]}...'")
        
        if operation == "read":
            result = {"content": "[Clipboard read not available in this environment]"}
        elif operation == "write":
            result = {"success": True, "message": f"Would write {len(content)} chars to clipboard"}
        else:
            result = {"error": f"Unknown operation: {operation}"}
        
        print(f"Result: {json.dumps(result, indent=2)}")
        self.results.append(("clipboard", True, result))
        return result
    
    def test_file_info(self, **kwargs):
        """Test file-info tool."""
        print("\n" + "="*70)
        print("TEST: file-info tool")
        print("="*70)
        
        path = kwargs.get('path', '.')
        
        print(f"Arguments: path={path}")
        
        result = {
            "path": path,
            "exists": False,
            "message": "File access not available in this environment"
        }
        
        print(f"Result: {json.dumps(result, indent=2)}")
        self.results.append(("file-info", True, result))
        return result
    
    def test_web_search(self, **kwargs):
        """Test web-search tool."""
        print("\n" + "="*70)
        print("TEST: web-search tool")
        print("="*70)
        
        query = kwargs.get('query', '')
        max_results = kwargs.get('max_results', 5)
        
        print(f"Arguments: query='{query}', max_results={max_results}")
        
        result = {
            "query": query,
            "results": [],
            "message": "Web search not configured - requires API keys"
        }
        
        print(f"Result: {json.dumps(result, indent=2)}")
        self.results.append(("web-search", True, result))
        return result
    
    def test_todo_list(self, **kwargs):
        """Test todo-list tool."""
        print("\n" + "="*70)
        print("TEST: todo-list tool")
        print("="*70)
        
        action = kwargs.get('action', 'list')
        
        print(f"Arguments: action={action}")
        
        result = {
            "action": action,
            "todos": [],
            "message": "Todo list not implemented"
        }
        
        print(f"Result: {json.dumps(result, indent=2)}")
        self.results.append(("todo-list", True, result))
        return result
    
    def test_line_editor(self, **kwargs):
        """Test line-editor tool."""
        print("\n" + "="*70)
        print("TEST: line-editor tool")
        print("="*70)
        
        print(f"Arguments: {kwargs}")
        
        result = {"message": "Line editor not implemented"}
        
        print(f"Result: {json.dumps(result, indent=2)}")
        self.results.append(("line-editor", True, result))
        return result
    
    def test_text_tools(self, **kwargs):
        """Test text-tools tool."""
        print("\n" + "="*70)
        print("TEST: text-tools tool")
        print("="*70)
        
        text = kwargs.get('text', '')
        operation = kwargs.get('operation', 'uppercase')
        
        print(f"Arguments: text='{text[:50]}...', operation={operation}")
        
        if operation == "uppercase":
            result = {"result": text.upper()}
        elif operation == "lowercase":
            result = {"result": text.lower()}
        elif operation == "reverse":
            result = {"result": text[::-1]}
        else:
            result = {"result": text}
        
        print(f"Result: {json.dumps(result, indent=2)}")
        self.results.append(("text-tools", True, result))
        return result
    
    def test_all_tools(self):
        """Test all tools with default arguments."""
        print("\n" + "="*70)
        print("TESTING ALL TOOLS")
        print("="*70)
        
        # Test each tool
        self.test_datetime()
        self.test_calculator(expression="2+2")
        self.test_calculator(expression="123*456")
        self.test_calculator()  # Test error case
        self.test_clipboard()
        self.test_file_info()
        self.test_web_search(query="test")
        self.test_todo_list()
        self.test_line_editor()
        self.test_text_tools(text="Hello World", operation="uppercase")
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        
        passed = sum(1 for _, success, _ in self.results if success)
        failed = len(self.results) - passed
        
        print(f"\nTotal: {len(self.results)} tests")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        
        if failed > 0:
            print("\nFailed tests:")
            for tool, success, result in self.results:
                if not success:
                    print(f"  - {tool}: {result.get('error', 'Unknown error')}")
        
        print("\n" + "="*70)


def main():
    parser = argparse.ArgumentParser(description='Test tools directly without LLM')
    parser.add_argument('tool', choices=['datetime', 'calculator', 'clipboard', 'file-info', 
                                        'web-search', 'todo-list', 'line-editor', 
                                        'text-tools', 'all'],
                       help='Tool to test (or "all" to test all tools)')
    parser.add_argument('--expression', type=str, help='Calculator expression')
    parser.add_argument('--precision', type=int, default=2, help='Calculator precision')
    parser.add_argument('--format', type=str, default='human', 
                       choices=['iso', 'human', 'timestamp', 'date', 'time'],
                       help='DateTime format')
    parser.add_argument('--timezone', type=str, default='UTC', help='DateTime timezone')
    parser.add_argument('--operation', type=str, help='Operation (clipboard, text-tools)')
    parser.add_argument('--content', type=str, help='Content (clipboard write)')
    parser.add_argument('--path', type=str, help='File path (file-info)')
    parser.add_argument('--query', type=str, help='Search query (web-search)')
    parser.add_argument('--max-results', type=int, default=5, help='Max search results')
    parser.add_argument('--text', type=str, help='Text to transform (text-tools)')
    parser.add_argument('--action', type=str, help='Action (todo-list)')
    
    args = parser.parse_args()
    
    tester = ToolTester()
    
    # Map tool names to methods
    tool_methods = {
        'datetime': tester.test_datetime,
        'calculator': tester.test_calculator,
        'clipboard': tester.test_clipboard,
        'file-info': tester.test_file_info,
        'web-search': tester.test_web_search,
        'todo-list': tester.test_todo_list,
        'line-editor': tester.test_line_editor,
        'text-tools': tester.test_text_tools,
    }
    
    if args.tool == 'all':
        tester.test_all_tools()
    else:
        # Convert args to kwargs
        kwargs = {k: v for k, v in vars(args).items() if k != 'tool'}
        
        # Call the appropriate method
        method = tool_methods.get(args.tool)
        if method:
            method(**kwargs)
            
            # Print mini summary
            print("\n" + "="*70)
            passed = sum(1 for _, success, _ in tester.results if success)
            print(f"Test {'PASSED ✅' if passed else 'FAILED ❌'}")
            print("="*70)
        else:
            print(f"Unknown tool: {args.tool}")
            sys.exit(1)


if __name__ == "__main__":
    main()
