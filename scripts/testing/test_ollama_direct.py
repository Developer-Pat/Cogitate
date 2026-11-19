#!/usr/bin/env python3
"""
Simple Ollama test - direct HTTP call, no LiteLLM.
"""

import requests
import json
import time

def test_ollama_direct():
    """Test Ollama directly via HTTP."""
    print("="*60)
    print("DIRECT OLLAMA TEST (No LiteLLM)")
    print("="*60)
    
    url = "http://localhost:11434/api/generate"
    
    payload = {
        "model": "mistral:7b",
        "prompt": "Say hello in one sentence.",
        "stream": False
    }
    
    print(f"Sending request to {url}...")
    print(f"Model: {payload['model']}")
    print(f"Prompt: {payload['prompt']}")
    
    start = time.time()
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        elapsed = time.time() - start
        
        print(f"\nResponse status: {response.status_code}")
        print(f"Time: {elapsed:.2f}s")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success!")
            print(f"Response: {data.get('response', 'N/A')[:200]}")
            return True, data
        else:
            print(f"❌ Error: {response.text[:200]}")
            return False, response.text
            
    except requests.Timeout:
        elapsed = time.time() - start
        print(f"❌ Timeout after {elapsed:.2f}s")
        return False, "Timeout"
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False, str(e)


def test_ollama_chat():
    """Test Ollama chat endpoint."""
    print("\n" + "="*60)
    print("OLLAMA CHAT API TEST")
    print("="*60)
    
    url = "http://localhost:11434/api/chat"
    
    payload = {
        "model": "mistral:7b",
        "messages": [
            {"role": "user", "content": "Say hello in one sentence."}
        ],
        "stream": False
    }
    
    print(f"Sending request to {url}...")
    
    start = time.time()
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        elapsed = time.time() - start
        
        print(f"\nResponse status: {response.status_code}")
        print(f"Time: {elapsed:.2f}s")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success!")
            message = data.get('message', {})
            print(f"Response: {message.get('content', 'N/A')[:200]}")
            return True, data
        else:
            print(f"❌ Error: {response.text[:200]}")
            return False, response.text
            
    except requests.Timeout:
        elapsed = time.time() - start
        print(f"❌ Timeout after {elapsed:.2f}s")
        return False, "Timeout"
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False, str(e)


def main():
    # Test 1: Direct generate
    success1, result1 = test_ollama_direct()
    
    # Test 2: Chat API
    success2, result2 = test_ollama_chat()
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Ollama Generate API: {'✅' if success1 else '❌'}")
    print(f"Ollama Chat API:     {'✅' if success2 else '❌'}")
    
    if success1 or success2:
        print("\n✅ Ollama is working correctly!")
        print("   The issue is likely with LiteLLM configuration.")
    else:
        print("\n❌ Ollama itself is having issues.")


if __name__ == "__main__":
    main()
