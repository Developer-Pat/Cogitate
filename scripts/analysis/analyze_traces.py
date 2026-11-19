#!/usr/bin/env python3
"""
Trace Analysis Script

Analyzes captured trace logs to identify patterns, timing issues, and race conditions.

Usage:
    python3 scripts/analyze_traces.py [--limit 500] [--flow ChatFlow] [--format json]

Export traces first:
    curl "http://localhost:8000/api/v1/logs/traces/export?format=json&limit=500" -o traces.json
    python3 scripts/analyze_traces.py traces.json
"""

import json
import sys
from datetime import datetime
from collections import defaultdict
from typing import Any


def load_traces(filepath: str) -> list[dict]:
    """Load traces from JSON file."""
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    # Handle both raw list and wrapped response
    if isinstance(data, dict) and 'traces' in data:
        return data['traces']
    return data


def analyze_timing(traces: list[dict]) -> dict:
    """Analyze timing patterns in traces."""
    if not traces:
        return {}
    
    # Sort by sequence
    sorted_traces = sorted(traces, key=lambda x: x.get('sequence', 0))
    
    timing_stats = {
        'total_traces': len(sorted_traces),
        'deltas': [],
        'gaps': [],  # Gaps > 100ms
        'avg_delta_ms': 0,
        'max_delta_ms': 0,
        'min_delta_ms': float('inf'),
    }
    
    prev_perf_time = None
    for i, trace in enumerate(sorted_traces):
        perf_time = trace.get('context', {}).get('perfTime')
        
        if perf_time is not None and prev_perf_time is not None:
            delta = perf_time - prev_perf_time
            timing_stats['deltas'].append(delta)
            
            if delta > 100:  # Gap > 100ms
                timing_stats['gaps'].append({
                    'sequence': trace.get('sequence'),
                    'flow': trace.get('flow'),
                    'step': trace.get('step'),
                    'delta_ms': round(delta, 2),
                    'timestamp': trace.get('timestamp')
                })
            
            timing_stats['max_delta_ms'] = max(timing_stats['max_delta_ms'], delta)
            timing_stats['min_delta_ms'] = min(timing_stats['min_delta_ms'], delta)
        
        prev_perf_time = perf_time
    
    if timing_stats['deltas']:
        timing_stats['avg_delta_ms'] = round(
            sum(timing_stats['deltas']) / len(timing_stats['deltas']), 2
        )
    
    if timing_stats['min_delta_ms'] == float('inf'):
        timing_stats['min_delta_ms'] = 0
    
    return timing_stats


def analyze_flows(traces: list[dict]) -> dict:
    """Analyze trace distribution by flow."""
    flow_counts = defaultdict(int)
    flow_steps = defaultdict(set)
    flow_tags = defaultdict(lambda: defaultdict(int))
    
    for trace in traces:
        flow = trace.get('flow', 'Unknown')
        step = trace.get('step', 'Unknown')
        tags = trace.get('context', {}).get('tags', [])
        
        flow_counts[flow] += 1
        flow_steps[flow].add(step)
        
        for tag in tags:
            flow_tags[flow][tag] += 1
    
    return {
        'by_flow': dict(flow_counts),
        'steps_by_flow': {k: list(v) for k, v in flow_steps.items()},
        'tags_by_flow': {k: dict(v) for k, v in flow_tags.items()}
    }


def analyze_tags(traces: list[dict]) -> dict:
    """Analyze tag distribution."""
    tag_counts = defaultdict(int)
    tag_sequences = defaultdict(list)
    
    for trace in traces:
        tags = trace.get('context', {}).get('tags', [])
        sequence = trace.get('sequence', 0)
        
        for tag in tags:
            tag_counts[tag] += 1
            tag_sequences[tag].append(sequence)
    
    # Find tag co-occurrence
    tag_pairs = defaultdict(int)
    for trace in traces:
        tags = trace.get('context', {}).get('tags', [])
        for i, tag1 in enumerate(tags):
            for tag2 in tags[i+1:]:
                pair = tuple(sorted([tag1, tag2]))
                tag_pairs[pair] += 1
    
    return {
        'by_tag': dict(tag_counts),
        'tag_pairs': {f"{k[0]}+{k[1]}": v for k, v in sorted(tag_pairs.items(), key=lambda x: -x[1])[:10]},
        'sequences_by_tag': {k: v[:10] for k, v in tag_sequences.items()}  # First 10 each
    }


def detect_patterns(traces: list[dict]) -> list[dict]:
    """Detect common async patterns and potential issues."""
    issues = []
    
    # Group by flow
    by_flow = defaultdict(list)
    for trace in traces:
        flow = trace.get('flow', 'Unknown')
        by_flow[flow].append(trace)
    
    for flow, flow_traces in by_flow.items():
        sorted_traces = sorted(flow_traces, key=lambda x: x.get('sequence', 0))
        
        # Check for start without success/error
        starts = [t for t in sorted_traces if ':start' in t.get('step', '')]
        successes = [t for t in sorted_traces if ':success' in t.get('step', '')]
        errors = [t for t in sorted_traces if ':error' in t.get('step', '')]
        
        for start in starts:
            start_seq = start.get('sequence', 0)
            matching_success = any(
                s.get('sequence', 0) > start_seq 
                for s in successes
            )
            matching_error = any(
                e.get('sequence', 0) > start_seq 
                for e in errors
            )
            
            if not matching_success and not matching_error:
                issues.append({
                    'type': 'incomplete_operation',
                    'flow': flow,
                    'step': start.get('step'),
                    'sequence': start_seq,
                    'message': f"Operation started but no success/error found"
                })
        
        # Check for errors
        for error in errors:
            issues.append({
                'type': 'error',
                'flow': flow,
                'step': error.get('step'),
                'sequence': error.get('sequence'),
                'message': f"Error in {flow}:{error.get('step')}",
                'context': error.get('context', {})
            })
        
        # Check for large timing gaps
        prev_perf = None
        for trace in sorted_traces:
            perf = trace.get('context', {}).get('perfTime')
            if perf is not None and prev_perf is not None:
                delta = perf - prev_perf
                if delta > 1000:  # > 1 second gap
                    issues.append({
                        'type': 'timing_gap',
                        'flow': flow,
                        'step': trace.get('step'),
                        'sequence': trace.get('sequence'),
                        'gap_ms': round(delta, 2),
                        'message': f"Large timing gap ({delta:.0f}ms) before this step"
                    })
            prev_perf = perf
    
    return issues


def print_report(traces: list[dict], output_file: str = None):
    """Generate and print analysis report."""
    timing = analyze_timing(traces)
    flows = analyze_flows(traces)
    tags = analyze_tags(traces)
    patterns = detect_patterns(traces)
    
    report = []
    report.append("=" * 80)
    report.append("TRACE ANALYSIS REPORT")
    report.append(f"Generated: {datetime.now().isoformat()}")
    report.append(f"Total Traces: {len(traces)}")
    report.append("=" * 80)
    
    # Timing Analysis
    report.append("\n📊 TIMING ANALYSIS")
    report.append("-" * 40)
    report.append(f"  Average delta: {timing.get('avg_delta_ms', 0):.2f}ms")
    report.append(f"  Min delta: {timing.get('min_delta_ms', 0):.2f}ms")
    report.append(f"  Max delta: {timing.get('max_delta_ms', 0):.2f}ms")
    report.append(f"  Large gaps (>100ms): {len(timing.get('gaps', []))}")
    
    if timing.get('gaps'):
        report.append("\n  ⚠️  Large Timing Gaps:")
        for gap in timing['gaps'][:5]:
            report.append(f"    #{gap['sequence']} {gap['flow']}:{gap['step']} +{gap['delta_ms']:.2f}ms")
    
    # Flow Distribution
    report.append("\n📁 FLOW DISTRIBUTION")
    report.append("-" * 40)
    for flow, count in sorted(flows['by_flow'].items(), key=lambda x: -x[1]):
        steps = len(flows['steps_by_flow'].get(flow, []))
        report.append(f"  {flow}: {count} traces, {steps} unique steps")
    
    # Tag Distribution
    report.append("\n🏷️  TAG DISTRIBUTION")
    report.append("-" * 40)
    for tag, count in sorted(tags['by_tag'].items(), key=lambda x: -x[1]):
        report.append(f"  {tag}: {count}")
    
    if tags.get('tag_pairs'):
        report.append("\n  Common tag pairs:")
        for pair, count in list(tags['tag_pairs'].items())[:5]:
            report.append(f"    {pair}: {count}")
    
    # Detected Patterns/Issues
    report.append("\n🔍 DETECTED PATTERNS & ISSUES")
    report.append("-" * 40)
    
    errors = [p for p in patterns if p['type'] == 'error']
    incomplete = [p for p in patterns if p['type'] == 'incomplete_operation']
    gaps = [p for p in patterns if p['type'] == 'timing_gap']
    
    report.append(f"  Errors: {len(errors)}")
    report.append(f"  Incomplete operations: {len(incomplete)}")
    report.append(f"  Timing gaps (>1s): {len(gaps)}")
    
    if errors:
        report.append("\n  ❌ Errors:")
        for error in errors[:5]:
            report.append(f"    #{error['sequence']} {error['flow']}:{error['step']}")
            if error.get('context', {}).get('error'):
                report.append(f"       {error['context']['error']}")
    
    if incomplete:
        report.append("\n  ⚠️  Incomplete Operations:")
        for issue in incomplete[:5]:
            report.append(f"    #{issue['sequence']} {issue['flow']}:{issue['step']} - {issue['message']}")
    
    if gaps:
        report.append("\n  ⏱️  Large Timing Gaps:")
        for gap in gaps[:5]:
            report.append(f"    #{gap['sequence']} {gap['flow']}:{gap['step']} +{gap['gap_ms']:.0f}ms")
    
    report.append("\n" + "=" * 80)
    
    # Print report
    report_text = "\n".join(report)
    print(report_text)
    
    if output_file:
        with open(output_file, 'w') as f:
            f.write(report_text)
        print(f"\nReport saved to: {output_file}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nError: Please provide a trace file path")
        print("Example: python3 analyze_traces.py traces.json")
        sys.exit(1)
    
    filepath = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        traces = load_traces(filepath)
        print(f"Loaded {len(traces)} traces from {filepath}")
        print_report(traces, output_file)
    except FileNotFoundError:
        print(f"Error: File not found: {filepath}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
