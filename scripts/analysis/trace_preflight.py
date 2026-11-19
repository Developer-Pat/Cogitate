#!/usr/bin/env python3
"""
Pre-flight checks for trace workflow.

Ensures all prerequisites are met before running automated trace workflow.

Usage:
    python scripts/trace_preflight.py
"""

import requests
import sys
from pathlib import Path

BACKEND_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:5173"


def check_backend():
    """Check if backend is running."""
    print("🔍 Checking backend...")
    try:
        response = requests.get(f"{BACKEND_URL}/api/v1/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'healthy':
                print("   ✅ Backend is healthy")
                return True
        print(f"   ❌ Backend returned status {response.status_code}")
        return False
    except requests.RequestException as e:
        print(f"   ❌ Backend not reachable: {e}")
        return False


def check_frontend():
    """Check if frontend is running."""
    print("🔍 Checking frontend...")
    try:
        response = requests.get(FRONTEND_URL, timeout=5)
        if response.status_code == 200:
            print("   ✅ Frontend is running")
            return True
        print(f"   ❌ Frontend returned status {response.status_code}")
        return False
    except requests.RequestException as e:
        print(f"   ❌ Frontend not reachable: {e}")
        return False


def check_trace_points():
    """Check if trace points are enabled in StreamingService.ts."""
    print("🔍 Checking trace points...")
    
    streaming_service = Path("frontend/src/services/domain/StreamingService.ts")
    if not streaming_service.exists():
        print(f"   ❌ StreamingService.ts not found")
        return False
    
    content = streaming_service.read_text()
    
    # Count uncommented traceService.trace calls
    trace_count = 0
    for line in content.split('\n'):
        stripped = line.strip()
        if stripped.startswith('traceService.trace('):
            trace_count += 1
    
    if trace_count >= 8:
        print(f"   ✅ {trace_count} trace points active")
        return True
    elif trace_count > 0:
        print(f"   ⚠️  Only {trace_count} trace points active (expected 8)")
        print(f"      Some traces may be commented out")
        return False
    else:
        print(f"   ❌ No trace points found")
        print(f"      Run: Uncomment trace points in StreamingService.ts")
        return False


def check_agents():
    """Check if test agents exist."""
    print("🔍 Checking test agents...")
    
    try:
        response = requests.get(f"{BACKEND_URL}/api/v1/agents", timeout=5)
        if response.status_code != 200:
            print(f"   ❌ Failed to fetch agents")
            return False
        
        data = response.json()
        agents = data.get('agents', [])
        
        # Check for Agent 16 (Ollama)
        agent_16 = next((a for a in agents if a['id'] == 16), None)
        if agent_16:
            print(f"   ✅ Agent 16 (Hemingway) exists - {agent_16['provider']}/{agent_16['model']}")
        else:
            print(f"   ⚠️  Agent 16 not found")
        
        # Check for Agent 21 (OpenRouter retired)
        agent_21 = next((a for a in agents if a['id'] == 21), None)
        if agent_21:
            print(f"   ✅ Agent 21 (Hunter) exists - {agent_21['provider']}/{agent_21['model']}")
        else:
            print(f"   ⚠️  Agent 21 not found")
        
        if agent_16 and agent_21:
            return True
        elif agent_16:
            print(f"   ℹ️  Can still run with Agent 16 only")
            return True
        else:
            print(f"   ❌ No test agents available")
            return False
            
    except requests.RequestException as e:
        print(f"   ❌ Error fetching agents: {e}")
        return False


def check_scripts():
    """Check if required scripts exist."""
    print("🔍 Checking scripts...")
    
    scripts = [
        "scripts/analysis/automated_trace_workflow.py",
        "scripts/analysis/compare_trace_flows.py",
        "scripts/analysis/analyze_logs.py"
    ]
    
    all_exist = True
    for script in scripts:
        if Path(script).exists():
            print(f"   ✅ {script}")
        else:
            print(f"   ❌ {script} not found")
            all_exist = False
    
    return all_exist


def check_output_dir():
    """Check if output directory can be created."""
    print("🔍 Checking output directory...")
    
    output_dir = Path("/tmp/trace_workflows")
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        test_file = output_dir / ".test"
        test_file.write_text("test")
        test_file.unlink()
        print(f"   ✅ Output directory writable: {output_dir}")
        return True
    except Exception as e:
        print(f"   ❌ Cannot write to output directory: {e}")
        return False


def main():
    """Run all pre-flight checks."""
    print("=" * 80)
    print("TRACE WORKFLOW PRE-FLIGHT CHECKS")
    print("=" * 80)
    print()
    
    checks = [
        ("Backend", check_backend),
        ("Frontend", check_frontend),
        ("Trace Points", check_trace_points),
        ("Test Agents", check_agents),
        ("Scripts", check_scripts),
        ("Output Directory", check_output_dir)
    ]
    
    results = []
    for name, check_func in checks:
        result = check_func()
        results.append((name, result))
        print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {name}")
    
    print()
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 All checks passed! Ready to run trace workflow.")
        print("\nNext steps:")
        print("1. Open browser to http://localhost:5173")
        print("2. Enable tracing in console:")
        print("   loggingConfigService.updateConfig({")
        print("     enableTracing: true,")
        print("     enableFlowTraces: true,")
        print("     traceSamplingRate: 1.0")
        print("   })")
        print("3. Run: python scripts/automated_trace_workflow.py")
        return 0
    else:
        print("\n⚠️  Some checks failed. Please fix issues before running workflow.")
        print("\nFailed checks:")
        for name, result in results:
            if not result:
                print(f"  - {name}")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
