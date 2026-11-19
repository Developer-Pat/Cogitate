#!/usr/bin/env python3
"""
Tool Integration Test Script

Tests direct LLM calls with tools via OpenRouter API.
Verifies that:
1. Tools are properly formatted for OpenRouter
2. LLM can see and understand available tools
3. Tool calls work correctly
"""

import os
import sys
import json
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

# Try to load environment variables from multiple locations
for env_path in [
    Path(__file__).parent / '.env',
    Path(__file__).parent.parent / '.env',
]:
    if env_path.exists():
        from dotenv import load_dotenv
        load_dotenv(env_path)
        print(f"✅ Loaded .env file: {env_path}")
        break
else:
    print(f"⚠️  No .env file found")


def get_openrouter_api_key():
    """Get OpenRouter API key from environment."""
    api_key = os.getenv('OPENROUTER_API_KEY')
    if not api_key:
        print("❌ OPENROUTER_API_KEY not found in environment")
        print("\nSet it with:")
        print("  export OPENROUTER_API_KEY='your-key-here'")
        print("\nOr add to .env file:")
        print("  OPENROUTER_API_KEY=your-key-here")
        return None
    return api_key


def test_basic_completion(api_key: str):
    """Test basic completion without tools."""
    print("\n" + "="*70)
    print("TEST 1: Basic Completion (No Tools)")
    print("="*70)
    
    import requests
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5173",  # Required by OpenRouter
        "X-Title": "Cogitate Tool Test"
    }
    
    payload = {
        "model": "nvidia/nemotron-nano-12b-v2-vl:free",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant."
            },
            {
                "role": "user",
                "content": "Hello! How are you?"
            }
        ],
        "max_tokens": 100,
        "temperature": 0.5
    }
    
    print(f"\n📤 Request:")
    print(f"   URL: {url}")
    print(f"   Model: {payload['model']}")
    print(f"   Messages: {len(payload['messages'])}")
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        print(f"\n✅ Response received!")
        print(f"   Status: {response.status_code}")
        print(f"   Content: {result['choices'][0]['message']['content'][:100]}...")
        
        if 'usage' in result:
            print(f"   Tokens: {result['usage']}")
        
        return True
        
    except requests.exceptions.Timeout:
        print(f"\n❌ Request timed out after 30 seconds")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Response: {e.response.text}")
        return False


def test_with_tools(api_key: str):
    """Test completion with tools."""
    print("\n" + "="*70)
    print("TEST 2: Completion WITH Tools")
    print("="*70)
    
    import requests
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5173",
        "X-Title": "Cogitate Tool Test"
    }
    
    # O Tool's system prompt
    system_prompt = """You are a tool testing and demonstration agent. Your primary purpose is to actively use and demonstrate the capabilities of available tools.

## Tool Inventory

First response:
- State that you are reporting for duty and are ready to test some tools.
- List the tools you have access to
- If you have no tools available, say "There are no tools available".
- Do not fabricate

## Tool Usage Mandate

**You MUST use tools when available:**
- When asked to use capabilities, actually DEMONSTRATE them
- Don't just list tools - USE them
- If a user asks a question that a tool can answer, use the tool e.g. "What time is it?"
- If you're unsure about something, use a tool to verify
- Show the tool's output and explain what it means
"""
    
    # Tool definitions (matching our database)
    tools = [
        {
            "type": "function",
            "function": {
                "name": "calculator",
                "description": "Perform mathematical calculations",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "Mathematical expression to evaluate"
                        },
                        "precision": {
                            "type": "integer",
                            "default": 2,
                            "minimum": 0,
                            "maximum": 10,
                            "description": "Number of decimal places"
                        }
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "datetime",
                "description": "Get current date/time and perform date operations",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "timezone": {
                            "type": "string",
                            "default": "UTC",
                            "description": "Timezone for operations"
                        },
                        "format": {
                            "type": "string",
                            "enum": ["iso", "human", "timestamp", "date", "time"],
                            "default": "iso",
                            "description": "Output format"
                        }
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "clipboard",
                "description": "Read and write to system clipboard",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": ["read", "write"],
                            "description": "Operation to perform"
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write (required for write operation)"
                        }
                    },
                    "required": ["operation"]
                }
            }
        }
    ]
    
    payload = {
        "model": "nvidia/nemotron-nano-12b-v2-vl:free",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "What tools do you have access to? List them and describe what each one does."}
        ],
        "tools": tools,
        "max_tokens": 500,
        "temperature": 0.5
    }
    
    print(f"\n📤 Request:")
    print(f"   URL: {url}")
    print(f"   Model: {payload['model']}")
    print(f"   Tools: {len(tools)}")
    for tool in tools:
        print(f"      - {tool['function']['name']}: {tool['function']['description']}")
    print(f"   Messages: {len(payload['messages'])}")
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        message = result['choices'][0]['message']
        
        print(f"\n✅ Response received!")
        print(f"   Status: {response.status_code}")
        
        # Check for tool calls
        if 'tool_calls' in message and message['tool_calls']:
            print(f"\n🔧 Tool calls detected: {len(message['tool_calls'])}")
            for tc in message['tool_calls']:
                print(f"      - {tc['function']['name']}")
                print(f"        Args: {tc['function']['arguments'][:100]}...")
        else:
            print(f"\n💬 Content response:")
            content = message.get('content', '')
            # Count lines for display
            lines = content.split('\n')
            for i, line in enumerate(lines[:15]):  # Show first 15 lines
                print(f"   {line}")
            if len(lines) > 15:
                print(f"   ... ({len(lines) - 15} more lines)")
        
        if 'usage' in result:
            print(f"\n   Tokens: {result['usage']}")
        
        # Check if LLM saw the tools
        content_lower = message.get('content', '').lower()
        tool_names = ['calculator', 'datetime', 'clipboard']
        found_tools = [name for name in tool_names if name in content_lower]
        
        print(f"\n📊 Analysis:")
        print(f"   Tools mentioned: {len(found_tools)}/{len(tool_names)}")
        if found_tools:
            print(f"      ✓ {', '.join(found_tools)}")
        if len(found_tools) == len(tool_names):
            print(f"   ✅ LLM successfully saw all tools!")
        elif len(found_tools) > 0:
            print(f"   ⚠️  LLM saw some tools but not all")
        else:
            print(f"   ❌ LLM didn't mention any tools - may not have received them")
        
        return True
        
    except requests.exceptions.Timeout:
        print(f"\n❌ Request timed out after 60 seconds")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Response: {e.response.text[:500]}")
        return False


def test_tool_call_trigger(api_key: str):
    """Test if LLM triggers tool calls."""
    print("\n" + "="*70)
    print("TEST 3: Tool Call Trigger")
    print("="*70)
    
    import requests
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5173",
        "X-Title": "Cogitate Tool Test"
    }
    
    tools = [
        {
            "type": "function",
            "function": {
                "name": "datetime",
                "description": "Get current date/time. Use this when user asks about time, date, or current moment.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "timezone": {
                            "type": "string",
                            "default": "UTC"
                        },
                        "format": {
                            "type": "string",
                            "enum": ["iso", "human", "timestamp"],
                            "default": "human"
                        }
                    }
                }
            }
        }
    ]
    
    payload = {
        "model": "nvidia/nemotron-nano-12b-v2-vl:free",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant with access to tools. Use tools when appropriate."},
            {"role": "user", "content": "What time is it right now?"}
        ],
        "tools": tools,
        "max_tokens": 200,
        "temperature": 0.3
    }
    
    print(f"\n📤 Request:")
    print(f"   Model: {payload['model']}")
    print(f"   Tools: 1 (datetime)")
    print(f"   User: \"What time is it right now?\"")
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        message = result['choices'][0]['message']
        
        print(f"\n✅ Response received!")
        
        if 'tool_calls' in message and message['tool_calls']:
            print(f"\n🔧 LLM triggered tool call!")
            for tc in message['tool_calls']:
                print(f"      Tool: {tc['function']['name']}")
                print(f"      Args: {tc['function']['arguments']}")
            print(f"   ✅ Tool calling works!")
        else:
            content = message.get('content', '')
            print(f"\n💬 Content response:")
            print(f"   {content[:200]}...")
            if 'time' in content.lower() or 'clock' in content.lower():
                print(f"   ⚠️  LLM answered about time but didn't use tool")
            else:
                print(f"   ❌ LLM didn't use tool or answer correctly")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Response: {e.response.text[:500]}")
        return False


def main():
    """Run all tests."""
    print("="*70)
    print("TOOL INTEGRATION TEST - OpenRouter API")
    print("="*70)
    
    api_key = get_openrouter_api_key()
    if not api_key:
        print("\n❌ Cannot run tests without API key")
        sys.exit(1)
    
    print(f"\n✅ API key found")
    print(f"   Key: {api_key[:20]}...{api_key[-10:]}")
    
    results = []
    
    # Test 1: Basic completion
    results.append(("Basic Completion", test_basic_completion(api_key)))
    
    # Test 2: With tools
    results.append(("With Tools", test_with_tools(api_key)))
    
    # Test 3: Tool call trigger
    results.append(("Tool Call Trigger", test_tool_call_trigger(api_key)))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(passed for _, passed in results)
    
    print("\n" + "="*70)
    if all_passed:
        print("✅ ALL TESTS PASSED")
    else:
        print("⚠️  SOME TESTS FAILED")
    print("="*70)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
