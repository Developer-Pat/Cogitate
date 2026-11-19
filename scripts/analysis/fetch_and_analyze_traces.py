#!/usr/bin/env python3
"""
Quick Trace Fetch & Analyze

Fetches traces from the API and analyzes them immediately.

Usage:
    python3 scripts/fetch_and_analyze_traces.py [limit] [output_file]
    
Examples:
    python3 scripts/fetch_and_analyze_traces.py          # Default: 500 traces
    python3 scripts/fetch_and_analyze_traces.py 1000     # 1000 traces
    python3 scripts/fetch_and_analyze_traces.py 500 report.txt  # Save report
"""

import json
import subprocess
import sys
from datetime import datetime


API_URL = "http://localhost:8000"


def fetch_traces(limit: int = 500) -> list[dict]:
    """Fetch traces from API."""
    cmd = [
        "curl", "-s",
        f"{API_URL}/api/v1/logs/traces/export?format=json&limit={limit}"
    ]
    
    print(f"Fetching {limit} traces from {API_URL}...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error fetching traces: {result.stderr}")
        sys.exit(1)
    
    data = json.loads(result.stdout)
    
    if isinstance(data, dict) and 'traces' in data:
        return data['traces']
    return data


def analyze_timing(traces: list[dict]) -> dict:
    """Analyze timing patterns."""
    if not traces:
        return {}
    
    sorted_traces = sorted(traces, key=lambda x: x.get('sequence', 0))
    
    timing = {
        'total': len(sorted_traces),
        'deltas': [],
        'gaps': [],
        'avg_ms': 0,
        'max_ms': 0,
        'min_ms': float('inf'),
    }
    
    prev = None
    for trace in sorted_traces:
        perf = trace.get('context', {}).get('perfTime')
        if perf is not None and prev is not None:
            delta = perf - prev
            timing['deltas'].append(delta)
            if delta > 100:
                timing['gaps'].append({
                    'seq': trace.get('sequence'),
                    'flow': trace.get('flow'),
                    'step': trace.get('step'),
                    'delta': round(delta, 2)
                })
            timing['max_ms'] = max(timing['max_ms'], delta)
            timing['min_ms'] = min(timing['min_ms'], delta)
        prev = perf
    
    if timing['deltas']:
        timing['avg_ms'] = round(sum(timing['deltas']) / len(timing['deltas']), 2)
    if timing['min_ms'] == float('inf'):
        timing['min_ms'] = 0
    
    return timing


def analyze_flows(traces: list[dict]) -> dict:
    """Analyze by flow."""
    from collections import defaultdict
    flows = defaultdict(int)
    steps = defaultdict(set)
    
    for t in traces:
        flow = t.get('flow', 'Unknown')
        step = t.get('step', 'Unknown')
        flows[flow] += 1
        steps[flow].add(step)
    
    return {
        'counts': dict(flows),
        'steps': {k: list(v) for k, v in steps.items()}
    }


def analyze_tags(traces: list[dict]) -> dict:
    """Analyze tags."""
    from collections import defaultdict
    tags = defaultdict(int)
    
    for t in traces:
        for tag in t.get('context', {}).get('tags', []):
            tags[tag] += 1
    
    return dict(tags)


def detect_issues(traces: list[dict]) -> list[dict]:
    """Detect potential issues."""
    issues = []
    by_flow = {}
    
    for t in traces:
        flow = t.get('flow', 'Unknown')
        by_flow.setdefault(flow, []).append(t)
    
    for flow, ftraces in by_flow.items():
        sorted_t = sorted(ftraces, key=lambda x: x.get('sequence', 0))
        prev_perf = None
        
        # Check for errors
        for t in sorted_t:
            ctx = t.get('context', {})
            if ctx.get('error'):
                issues.append({
                    'type': 'error',
                    'flow': flow,
                    'step': t.get('step'),
                    'seq': t.get('sequence'),
                    'msg': ctx.get('error')
                })
            
            # Large gaps
            perf = ctx.get('perfTime')
            if perf and prev_perf and (perf - prev_perf) > 1000:
                issues.append({
                    'type': 'gap',
                    'flow': flow,
                    'step': t.get('step'),
                    'seq': t.get('sequence'),
                    'gap': round(perf - prev_perf, 2)
                })
            prev_perf = perf
    
    return issues


def print_report(traces: list[dict]):
    """Print analysis report."""
    timing = analyze_timing(traces)
    flows = analyze_flows(traces)
    tags = analyze_tags(traces)
    issues = detect_issues(traces)
    
    print("\n" + "=" * 70)
    print("TRACE ANALYSIS REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total Traces: {len(traces)}")
    print("=" * 70)
    
    print("\n📊 TIMING")
    print("-" * 40)
    print(f"  Avg delta: {timing.get('avg_ms', 0):.2f}ms")
    print(f"  Min delta: {timing.get('min_ms', 0):.2f}ms")
    print(f"  Max delta: {timing.get('max_ms', 0):.2f}ms")
    print(f"  Gaps >100ms: {len(timing.get('gaps', []))}")
    
    if timing.get('gaps'):
        print("\n  ⚠️  Large Gaps:")
        for g in timing['gaps'][:5]:
            print(f"    #{g['seq']} {g['flow']}:{g['step']} +{g['delta']}ms")
    
    print("\n📁 FLOWS")
    print("-" * 40)
    for flow, count in sorted(flows['counts'].items(), key=lambda x: -x[1]):
        print(f"  {flow}: {count} traces")
    
    print("\n🏷️  TAGS")
    print("-" * 40)
    for tag, count in sorted(tags.items(), key=lambda x: -x[1]):
        print(f"  {tag}: {count}")
    
    print("\n🔍 ISSUES")
    print("-" * 40)
    errors = [i for i in issues if i['type'] == 'error']
    gaps = [i for i in issues if i['type'] == 'gap']
    print(f"  Errors: {len(errors)}")
    print(f"  Timing gaps >1s: {len(gaps)}")
    
    if errors:
        print("\n  ❌ Recent Errors:")
        for e in errors[:5]:
            print(f"    #{e['seq']} {e['flow']}:{e['step']}")
            print(f"       {e['msg']}")
    
    if gaps:
        print("\n  ⏱️  Large Gaps:")
        for g in gaps[:5]:
            print(f"    #{g['seq']} {g['flow']}:{g['step']} +{g['gap']}ms")
    
    print("\n" + "=" * 70)


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    output = sys.argv[2] if len(sys.argv) > 2 else None
    
    traces = fetch_traces(limit)
    print(f"Loaded {len(traces)} traces\n")
    
    print_report(traces)
    
    if output:
        with open(output, 'w') as f:
            f.write("Trace Analysis Report\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            import io
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            print_report(traces)
            f.write(sys.stdout.getvalue())
            sys.stdout = old_stdout
        print(f"\nReport saved to: {output}")


if __name__ == '__main__':
    main()
