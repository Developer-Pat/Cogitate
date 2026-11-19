#!/usr/bin/env python3
"""
Direct LiteLLM test - bypass the backend entirely.
Tests if LiteLLM can connect to the providers.
"""

import asyncio
import json
import time

async def test_litellm(model, provider, api_key=None):
    """Test LiteLLM completion directly."""
    print(f"\n{'='*60}")
    print(f"Testing LiteLLM: {provider}/{model}")
    print('='*60)
    
    try:
        from litellm import acompletion
    except ImportError:
        print("❌ LiteLLM not installed")
        return False, None
    
    # Build model string
    if model.startswith(f"{provider}/"):
        litellm_model = model
    else:
        litellm_model = f"{provider}/{model}"
    
    print(f"LiteLLM model: {litellm_model}")
    
    # Set API key if provided
    if api_key and provider == "openrouter":
        import os
        os.environ["OPENROUTER_API_KEY"] = api_key
    
    messages = [
        {"role": "user", "content": "Say hello in one sentence."}
    ]
    
    start = time.time()
    
    try:
        response = await acompletion(
            model=litellm_model,
            messages=messages,
            stream=True,
            timeout=10  # 10 second timeout
        )
        
        print(f"✅ Got response object after {time.time() - start:.2f}s")
        
        content = ""
        chunk_count = 0
        
        async for chunk in response:
            chunk_count += 1
            if hasattr(chunk, 'choices') and chunk.choices:
                delta = chunk.choices[0].delta
                if hasattr(delta, 'content') and delta.content:
                    content += delta.content
                    print(f"   Chunk {chunk_count}: {delta.content[:50]}")
        
        elapsed = time.time() - start
        print(f"\n✅ Success! {chunk_count} chunks, {len(content)} chars in {elapsed:.2f}s")
        return True, content
        
    except Exception as e:
        elapsed = time.time() - start
        print(f"❌ Error after {elapsed:.2f}s: {type(e).__name__}: {e}")
        return False, str(e)


async def main():
    print("="*60)
    print("DIRECT LITELLM TEST")
    print("="*60)
    
    # Read API key from .env
    api_key = None
    try:
        with open(".env") as f:
            for line in f:
                if line.startswith("OPENROUTER_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break
    except:
        pass
    
    if api_key:
        print(f"OpenRouter API key: {api_key[:20]}...")
    else:
        print("⚠️  No OpenRouter API key found")
    
    # Test 1: Ollama (local, no API key)
    print("\n📍 Test 1: Ollama - mistral:7b")
    success1, result1 = await test_litellm("mistral:7b", "ollama")
    
    await asyncio.sleep(2)
    
    # Test 2: OpenRouter - working model
    print("\n📍 Test 2: OpenRouter - nvidia/nemotron-nano-12b-v2-vl:free")
    success2, result2 = await test_litellm(
        "nvidia/nemotron-nano-12b-v2-vl:free",
        "openrouter",
        api_key
    )
    
    await asyncio.sleep(2)
    
    # Test 3: OpenRouter - retired model
    print("\n📍 Test 3: OpenRouter - hunter-alpha (retired)")
    success3, result3 = await test_litellm(
        "hunter-alpha",
        "openrouter",
        api_key
    )
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Ollama mistral:7b:                    {'✅' if success1 else '❌'}")
    print(f"OpenRouter nvidia/nemotron-nano:      {'✅' if success2 else '❌'}")
    print(f"OpenRouter hunter-alpha (retired):    {'✅' if success3 else '❌'}")
    
    if not success3 and result3:
        print(f"\n🎯 Retired model error: {result3[:200]}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        raise
