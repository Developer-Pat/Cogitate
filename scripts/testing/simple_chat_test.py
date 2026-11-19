#!/usr/bin/env python3
"""
Simple direct test of chat endpoints - no streaming complexity.
"""

import requests
import json
import time

BACKEND_URL = "http://localhost:8000"

def test_agent(agent_id, timeout=15):
    """Test an agent with non-streaming endpoint."""
    print(f"\n{'='*60}")
    print(f"Testing Agent #{agent_id}")
    print('='*60)
    
    # First try non-streaming completion
    payload = {
        "agent_id": agent_id,
        "message": "Say hello in one sentence.",
        "session_id": 999,
        "stream": False  # Non-streaming
    }
    
    print(f"Sending request (timeout={timeout}s)...")
    start = time.time()
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/v1/chat/completions",
            json=payload,
            timeout=timeout
        )
        
        elapsed = time.time() - start
        
        print(f"Status: {response.status_code}")
        print(f"Time: {elapsed:.2f}s")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success!")
            if 'choices' in data and data['choices']:
                content = data['choices'][0]['message']['content']
                print(f"Response: {content[:200]}")
            return True, data
        else:
            print(f"❌ Error: {response.text[:200]}")
            try:
                err = response.json()
                print(f"Detail: {err}")
            except:
                pass
            return False, response.text
            
    except requests.Timeout:
        print(f"❌ Timeout after {timeout}s")
        return False, "Timeout"
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False, str(e)


def main():
    print("="*60)
    print("SIMPLE CHAT ENDPOINT TEST")
    print("="*60)
    
    # Test good agent (Ollama)
    print("\n📍 Testing GOOD agent (Ollama - mistral:7b)")
    success_good, result_good = test_agent(16, timeout=15)
    
    time.sleep(2)
    
    # Test bad agent (retired OpenRouter)
    print("\n📍 Testing BAD agent (OpenRouter - hunter-alpha)")
    success_bad, result_bad = test_agent(21, timeout=15)
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Agent 16 (Ollama):     {'✅ Success' if success_good else '❌ Failed'}")
    print(f"Agent 21 (Retired):    {'✅ Success' if success_bad else '❌ Failed'}")
    
    if not success_bad and isinstance(result_bad, str):
        print(f"\n🎯 Root cause identified:")
        if 'not found' in result_bad.lower() or '404' in result_bad:
            print("   Model retired/unavailable")
        elif 'provider' in result_bad.lower():
            print("   Provider error")
        else:
            print(f"   {result_bad[:100]}")


if __name__ == "__main__":
    main()
