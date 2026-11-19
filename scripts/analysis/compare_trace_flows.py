#!/usr/bin/env python3
"""
Compare trace flows between successful and failed chat attempts.

Usage:
    python scripts/compare_trace_flows.py

This script helps debug issues by comparing trace flows between:
- A successful chat interaction (e.g., Ollama agent)
- A failed chat interaction (e.g., OpenRouter retired model)
"""

import requests
import json
from datetime import datetime

BACKEND_URL = "http://localhost:8000"


def fetch_recent_logs(n=500):
    """Fetch recent logs from backend."""
    try:
        response = requests.get(f"{BACKEND_URL}/api/v1/logs/recent?n={n}", timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"❌ Error fetching logs: {e}")
        return []


def filter_flow_traces(logs):
    """Filter for FlowTrace logs only."""
    return [
        log for log in logs 
        if log.get('source') == 'FlowTrace' 
        or 'FLOW TRACE' in log.get('message', '')
    ]


def analyze_flow(traces):
    """Analyze a flow trace sequence."""
    if not traces:
        return {"error": "No traces found", "total_traces": 0, "steps": [], "errors": []}
    
    analysis = {
        "total_traces": len(traces),
        "first_trace": traces[0],
        "last_trace": traces[-1],
        "steps": [],
        "errors": [],
        "trace_details": []
    }
    
    for trace in traces:
        ctx = trace.get('context', {})
        step = ctx.get('step', 'unknown')
        flow = ctx.get('flow', 'unknown')
        sequence = ctx.get('sequence', '?')
        
        analysis["steps"].append(f"{flow}:{step}")
        analysis["trace_details"].append({
            "sequence": sequence,
            "flow": flow,
            "step": step,
            "context": {k: v for k, v in ctx.items() if k not in ['traceId', 'sequence', 'flow', 'step', 'timestamp', 'perfTime']}
        })
        
        # Check for errors in context
        if 'error' in str(ctx).lower() or 'Error' in str(ctx):
            analysis["errors"].append({
                "sequence": sequence,
                "step": step,
                "error": ctx.get('error', 'Unknown error'),
                "message": trace.get('message', '')
            })
    
    return analysis


def print_flow_analysis(analysis, label):
    """Print flow analysis in readable format."""
    print(f"\n{'=' * 80}")
    print(f"{label}")
    print('=' * 80)
    
    if analysis.get('error'):
        print(f"❌ {analysis['error']}")
        return
    
    print(f"📊 Total traces: {analysis['total_traces']}")
    
    if analysis['total_traces'] > 0:
        first_ctx = analysis['first_trace'].get('context', {})
        last_ctx = analysis['last_trace'].get('context', {})
        
        print(f"▶️  First: {first_ctx.get('flow', '?')}:{first_ctx.get('step', '?')} (seq #{first_ctx.get('sequence', '?')})")
        print(f"⏹️  Last:  {last_ctx.get('flow', '?')}:{last_ctx.get('step', '?')} (seq #{last_ctx.get('sequence', '?')})")
        
        print(f"\n📋 Trace sequence:")
        for i, detail in enumerate(analysis['trace_details'][:20]):  # Show first 20
            ctx_items = []
            for k, v in detail['context'].items():
                if isinstance(v, str) and len(v) > 40:
                    v = v[:37] + '...'
                ctx_items.append(f"{k}={v}")
            
            ctx_str = f" ({', '.join(ctx_items)})" if ctx_items else ""
            print(f"   #{detail['sequence']:3d} [{detail['flow']}:{detail['step']}]{ctx_str}")
        
        if len(analysis['trace_details']) > 20:
            print(f"   ... and {len(analysis['trace_details']) - 20} more traces")
        
        if analysis['errors']:
            print(f"\n🚨 ERRORS FOUND: {len(analysis['errors'])}")
            for err in analysis['errors']:
                print(f"   #{err['sequence']} - {err['step']}: {err['error']}")
        else:
            print(f"\n✅ No errors detected in trace flow")


def main():
    print("=" * 80)
    print("TRACE FLOW COMPARISON TOOL")
    print("=" * 80)
    print()
    print("This tool compares trace flows between successful and failed chat attempts.")
    print()
    print("STEP 1: Send a message to a WORKING agent (e.g., Agent 16 - Hemingway)")
    print("        URL: http://localhost:5173/agent-interaction")
    print()
    input("➡️  Press Enter after the message is complete...")
    
    print("\n📡 Fetching success flow logs...")
    success_logs = fetch_recent_logs(500)
    success_traces = filter_flow_traces(success_logs)
    success_analysis = analyze_flow(success_traces)
    
    print_flow_analysis(success_analysis, "✅ SUCCESS FLOW")
    
    print("\n" + "=" * 80)
    print("STEP 2: Clear logs")
    print("        Run: curl -X DELETE http://localhost:8000/api/v1/logs/clear-frontend")
    print()
    input("➡️  Press Enter after logs are cleared...")
    
    print("\n" + "=" * 80)
    print("STEP 3: Send a message to a FAILED agent (e.g., Agent 21 - Hunter)")
    print("        This agent uses a retired OpenRouter model")
    print()
    input("➡️  Press Enter after you see the error or timeout...")
    
    print("\n📡 Fetching failed flow logs...")
    failed_logs = fetch_recent_logs(500)
    failed_traces = filter_flow_traces(failed_logs)
    failed_analysis = analyze_flow(failed_traces)
    
    print_flow_analysis(failed_analysis, "❌ FAILED FLOW")
    
    # Comparison
    print("\n" + "=" * 80)
    print("📊 COMPARISON SUMMARY")
    print("=" * 80)
    print(f"\nSuccess flow: {success_analysis['total_traces']} traces")
    print(f"Failed flow:  {failed_analysis['total_traces']} traces")
    print(f"Difference:   {success_analysis['total_traces'] - failed_analysis['total_traces']} traces")
    
    if failed_analysis.get('errors'):
        print(f"\n🚨 Errors in failed flow: {len(failed_analysis['errors'])}")
        for err in failed_analysis['errors']:
            print(f"   • Sequence #{err['sequence']} - {err['step']}")
            print(f"     Error: {err['error']}")
    
    # Find where flows diverge
    print(f"\n🔍 DIVERGENCE ANALYSIS")
    min_traces = min(len(success_analysis['trace_details']), len(failed_analysis['trace_details']))
    
    divergence_point = None
    for i in range(min_traces):
        success_step = success_analysis['trace_details'][i]
        failed_step = failed_analysis['trace_details'][i]
        
        if success_step['step'] != failed_step['step']:
            divergence_point = i
            break
    
    if divergence_point is not None:
        print(f"   Flows diverge at trace #{divergence_point + 1}")
        print(f"   Success: {success_analysis['trace_details'][divergence_point]['flow']}:{success_analysis['trace_details'][divergence_point]['step']}")
        print(f"   Failed:  {failed_analysis['trace_details'][divergence_point]['flow']}:{failed_analysis['trace_details'][divergence_point]['step']}")
    else:
        if len(failed_analysis['trace_details']) < len(success_analysis['trace_details']):
            print(f"   Failed flow stopped early at trace #{len(failed_analysis['trace_details'])}")
            if failed_analysis['trace_details']:
                last = failed_analysis['trace_details'][-1]
                print(f"   Last trace: {last['flow']}:{last['step']}")
        else:
            print(f"   No divergence found in first {min_traces} traces")
    
    # Save to file
    print("\n" + "=" * 80)
    print("💾 Save analysis to file?")
    save = input("   Type 'y' to save, or press Enter to skip: ").lower()
    
    if save == 'y':
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"/tmp/trace_comparison_{timestamp}.json"
        
        output = {
            "success": success_analysis,
            "failed": failed_analysis,
            "timestamp": timestamp,
            "summary": {
                "success_trace_count": success_analysis['total_traces'],
                "failed_trace_count": failed_analysis['total_traces'],
                "divergence_point": divergence_point,
                "error_count": len(failed_analysis.get('errors', []))
            }
        }
        
        with open(filename, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"\n✅ Saved to: {filename}")
        
        # Also save human-readable version
        txt_filename = f"/tmp/trace_comparison_{timestamp}.txt"
        with open(txt_filename, 'w') as f:
            f.write("TRACE FLOW COMPARISON REPORT\n")
            f.write("=" * 80 + "\n")
            f.write(f"Timestamp: {timestamp}\n\n")
            
            f.write("SUCCESS FLOW\n")
            f.write("-" * 80 + "\n")
            for detail in success_analysis['trace_details']:
                f.write(f"#{detail['sequence']} [{detail['flow']}:{detail['step']}]\n")
            
            f.write("\n\nFAILED FLOW\n")
            f.write("-" * 80 + "\n")
            for detail in failed_analysis['trace_details']:
                f.write(f"#{detail['sequence']} [{detail['flow']}:{detail['step']}]\n")
            
            if failed_analysis['errors']:
                f.write("\n\nERRORS\n")
                f.write("-" * 80 + "\n")
                for err in failed_analysis['errors']:
                    f.write(f"#{err['sequence']} - {err['step']}: {err['error']}\n")
        
        print(f"✅ Text report: {txt_filename}")
    
    print("\n" + "=" * 80)
    print("Analysis complete!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        raise
