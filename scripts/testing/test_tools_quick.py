#!/usr/bin/env python3
"""
Quick Tool Test - Uses backend's existing OpenRouter configuration

This script tests tool integration using the same configuration as the backend.
No API key needed - it uses the backend's configured key.
"""

import sys
import json
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

# Load environment from root .env (canonical location)
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path)
    print(f"✅ Loaded root .env: {env_path}")
else:
    print(f"⚠️  Root .env not found: {env_path}")

# Setup async environment
import asyncio  # noqa: E402
from app.core.config import Settings  # noqa: E402
settings = Settings()

print("="*70)
print("QUICK TOOL TEST - Using Backend Configuration")
print("="*70)

print(f"\n📋 Configuration:")
print(f"   Database: {settings.database_url}")
print(f"   OpenRouter Key: {'✅ Set' if settings.openrouter_api_key else '❌ Not set'}")

if not settings.openrouter_api_key:
    print("\n❌ OpenRouter API key not configured in backend")
    print("\nAdd to .env file:")
    print("  OPENROUTER_API_KEY=your-key-here")
    sys.exit(1)

async def test_with_tools():
    """Test LLM call with tools using LiteLLM (same as backend)."""
    print("\n" + "="*70)
    print("TEST: LLM Call with Tools (via LiteLLM)")
    print("="*70)
    
    try:
        from litellm import acompletion
    except ImportError:
        print("\n❌ LiteLLM not installed")
        return False
    
    # Tool definitions
    tools = [
        {
            "type": "function",
            "function": {
                "name": "calculator",
                "description": "Perform mathematical calculations",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {"type": "string", "description": "Math expression"},
                        "precision": {"type": "integer", "default": 2}
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "datetime",
                "description": "Get current date/time",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "timezone": {"type": "string", "default": "UTC"},
                        "format": {"type": "string", "enum": ["iso", "human"], "default": "human"}
                    }
                }
            }
        }
    ]
    
    print(f"\n📤 Request:")
    print(f"   Model: openrouter/nvidia/nemotron-nano-12b-v2-vl:free")
    print(f"   Tools: {len(tools)}")
    for tool in tools:
        print(f"      - {tool['function']['name']}: {tool['function']['description']}")
    
    try:
        print(f"\n⏳ Calling OpenRouter API...")
        
        response = await acompletion(
            model="openrouter/nvidia/nemotron-nano-12b-v2-vl:free",
            messages=[
                {"role": "system", "content": "You are a helpful assistant with tool access."},
                {"role": "user", "content": "What tools do you have? List them."}
            ],
            tools=tools,
            max_tokens=300,
            temperature=0.5,
            stream=False
        )
        
        message = response.choices[0].message
        
        print(f"\n✅ Response received!")
        
        # Check for tool calls
        if hasattr(message, 'tool_calls') and message.tool_calls:
            print(f"\n🔧 Tool calls: {len(message.tool_calls)}")
            for tc in message.tool_calls:
                print(f"      - {tc.function.name}")
        else:
            content = message.content or ""
            print(f"\n💬 Content:")
            lines = content.split('\n')
            for line in lines[:10]:
                print(f"   {line}")
            
            # Check if tools were mentioned
            content_lower = content.lower()
            if 'calculator' in content_lower or 'datetime' in content_lower:
                print(f"\n✅ LLM saw the tools!")
            else:
                print(f"\n⚠️  LLM didn't mention tools")
        
        if hasattr(response, 'usage') and response.usage:
            print(f"\n   Tokens: prompt={response.usage.prompt_tokens}, completion={response.usage.completion_tokens}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_tool_call():
    """Test if LLM triggers tool calls."""
    print("\n" + "="*70)
    print("TEST: Tool Call Trigger")
    print("="*70)
    
    try:
        from litellm import acompletion
    except ImportError:
        print("\n❌ LiteLLM not installed")
        return False
    
    tools = [
        {
            "type": "function",
            "function": {
                "name": "datetime",
                "description": "Get current time. Use when user asks about time.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "format": {"type": "string", "enum": ["iso", "human"], "default": "human"}
                    }
                }
            }
        }
    ]
    
    print(f"\n📤 Request:")
    print(f"   User: \"What time is it?\"")
    print(f"   Tools: 1 (datetime)")
    
    try:
        print(f"\n⏳ Calling OpenRouter API...")
        
        response = await acompletion(
            model="openrouter/nvidia/nemotron-nano-12b-v2-vl:free",
            messages=[
                {"role": "user", "content": "What time is it?"}
            ],
            tools=tools,
            max_tokens=100,
            stream=False
        )
        
        message = response.choices[0].message
        
        print(f"\n✅ Response received!")
        
        if hasattr(message, 'tool_calls') and message.tool_calls:
            print(f"\n🔧 LLM triggered tool call!")
            for tc in message.tool_calls:
                print(f"      Tool: {tc.function.name}")
                print(f"      Args: {tc.function.arguments}")
            print(f"   ✅ SUCCESS: Tool calling works!")
        else:
            content = message.content or ""
            print(f"\n💬 Content: {content[:150]}...")
            print(f"   ⚠️  LLM answered without using tool")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


async def main():
    """Run tests."""
    results = []
    
    # Test 1
    results.append(("Tools Visible", await test_with_tools()))
    
    # Test 2
    results.append(("Tool Call Trigger", await test_tool_call()))
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(passed for _, passed in results)
    
    print("="*70)
    if all_passed:
        print("✅ ALL TESTS PASSED - Tool integration working!")
    else:
        print("⚠️  SOME TESTS FAILED - Check configuration")
    print("="*70)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(result)
