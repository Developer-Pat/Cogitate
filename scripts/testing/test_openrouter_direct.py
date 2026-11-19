#!/usr/bin/env python3
"""
Test OpenRouter API directly - no LiteLLM.
"""

import requests
import json
import time
import os

# Read API key
api_key = None
try:
    with open(".env") as f:
        for line in f:
            if line.startswith("OPENROUTER_API_KEY="):
                api_key = line.split("=", 1)[1].strip()
                break
except:
    pass

if not api_key:
    print("❌ No OpenRouter API key found in .env")
    exit(1)

print(f"Using API key: {api_key[:20]}...")

def test_openrouter(model, description):
    """Test OpenRouter model."""
    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"Model: {model}")
    print('='*60)
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": "Say hello in one sentence."}
        ],
        "stream": False
    }
    
    print(f"Sending request...")
    start = time.time()
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        elapsed = time.time() - start
        
        print(f"Status: {response.status_code}")
        print(f"Time: {elapsed:.2f}s")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success!")
            if 'choices' in data and data['choices']:
                content = data['choices'][0]['message']['content']
                print(f"Response: {content}")
            return True, data
        else:
            print(f"❌ Error: {response.status_code}")
            try:
                err = response.json()
                print(f"Detail: {json.dumps(err, indent=2)}")
            except:
                print(f"Response: {response.text[:300]}")
            return False, response.text
            
    except requests.Timeout:
        elapsed = time.time() - start
        print(f"❌ Timeout after {elapsed:.2f}s")
        return False, "Timeout"
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False, str(e)


def main():
    print("="*60)
    print("OPENROUTER DIRECT API TEST")
    print("="*60)
    
    # Test 1: Working model
    print("\n📍 Test 1: Working NVIDIA model")
    success1, result1 = test_openrouter(
        "nvidia/nemotron-nano-12b-v2-vl:free",
        "NVIDIA Nemotron (Free tier)"
    )
    
    # Test 2: Retired model
    print("\n📍 Test 2: Retired model (should fail)")
    success2, result2 = test_openrouter(
        "hunter-alpha",
        "Hunter Alpha (Retired)"
    )
    
    # Test 3: Another retired model
    print("\n📍 Test 3: Another retired model")
    success3, result3 = test_openrouter(
        "healer-alpha",
        "Healer Alpha (Retired)"
    )
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"NVIDIA Nemotron (free):  {'✅' if success1 else '❌'}")
    print(f"Hunter Alpha (retired):  {'✅' if success2 else '❌'}")
    print(f"Healer Alpha (retired):  {'✅' if success3 else '❌'}")
    
    if not success2:
        print(f"\n🎯 Retired model error (Hunter):")
        if isinstance(result2, dict):
            print(json.dumps(result2.get('error', {}), indent=2))
        else:
            print(result2[:300])
    
    if not success3:
        print(f"\n🎯 Retired model error (Healer):")
        if isinstance(result3, dict):
            print(json.dumps(result3.get('error', {}), indent=2))
        else:
            print(result3[:300])


if __name__ == "__main__":
    main()
