#!/usr/bin/env python3
"""
Log Analysis Script for Cogitate

Analyzes logs from the backend API to identify:
- Most frequent log messages
- Log volume by source
- Log volume by level
- Potential runaway logging (repeated messages)
- Flow trace analysis
"""

import requests
import json
from collections import Counter, defaultdict
from datetime import datetime
import argparse

BASE_URL = "http://localhost:8000"

def fetch_logs(limit=1000):
    """Fetch recent logs from backend"""
    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/logs/recent?n={limit}",
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Error fetching logs: {e}")
        return []

def analyze_logs(logs):
    """Analyze logs and return statistics"""
    if not logs:
        return None
    
    # Count by message
    message_counts = Counter(log['message'] for log in logs)
    
    # Count by source
    source_counts = Counter(log['source'] for log in logs)
    
    # Count by level
    level_counts = Counter(log['level'] for log in logs)
    
    # Find FlowTrace logs
    flow_traces = [log for log in logs if log.get('source') == 'FlowTrace']
    flow_steps = Counter(log.get('context', {}).get('step', 'unknown') for log in flow_traces)
    flow_flows = Counter(log.get('context', {}).get('flow', 'unknown') for log in flow_traces)
    
    # Find repeated messages (potential runaway logging)
    repeated_messages = {
        msg: count for msg, count in message_counts.items() 
        if count > 10
    }
    
    # Calculate time-based stats
    timestamps = []
    for log in logs:
        try:
            ts = datetime.fromisoformat(log['timestamp'].replace('Z', '+00:00'))
            timestamps.append(ts)
        except:
            pass
    
    time_span = None
    if len(timestamps) >= 2:
        time_span = max(timestamps) - min(timestamps)
    
    return {
        'total_logs': len(logs),
        'message_counts': message_counts,
        'source_counts': source_counts,
        'level_counts': level_counts,
        'flow_traces': len(flow_traces),
        'flow_steps': flow_steps,
        'flow_flows': flow_flows,
        'repeated_messages': repeated_messages,
        'time_span': time_span,
        'logs_per_second': len(logs) / time_span.total_seconds() if time_span and time_span.total_seconds() > 0 else 0
    }

def print_analysis(stats):
    """Print analysis results"""
    if not stats:
        print("No logs to analyze")
        return
    
    print("\n" + "="*80)
    print("📊 LOG ANALYSIS REPORT")
    print("="*80)
    
    print(f"\n📈 OVERVIEW")
    print(f"   Total logs analyzed: {stats['total_logs']}")
    if stats['time_span']:
        print(f"   Time span: {stats['time_span']}")
        print(f"   Rate: {stats['logs_per_second']:.2f} logs/second")
    
    print(f"\n📋 LOG LEVELS")
    for level, count in stats['level_counts'].most_common():
        pct = (count / stats['total_logs']) * 100
        bar = "█" * int(pct / 5)
        print(f"   {level:10} {count:6} ({pct:5.1f}%) {bar}")
    
    print(f"\n🏷️  TOP SOURCES")
    for source, count in stats['source_counts'].most_common(10):
        pct = (count / stats['total_logs']) * 100
        bar = "█" * int(pct / 5)
        print(f"   {source:30} {count:6} ({pct:5.1f}%) {bar}")
    
    if stats['flow_traces'] > 0:
        print(f"\n🔍 FLOW TRACE ANALYSIS ({stats['flow_traces']} traces)")
        print(f"   Flows:")
        for flow, count in stats['flow_flows'].most_common(5):
            print(f"      {flow}: {count} traces")
        print(f"   Steps:")
        for step, count in stats['flow_steps'].most_common(10):
            print(f"      {step}: {count}")
    
    if stats['repeated_messages']:
        print(f"\n⚠️  REPEATED MESSAGES (potential runaway logging)")
        for msg, count in sorted(stats['repeated_messages'].items(), key=lambda x: -x[1])[:10]:
            msg_preview = msg[:60] + "..." if len(msg) > 60 else msg
            print(f"   [{count:4}x] {msg_preview}")
    
    print(f"\n📝 TOP 20 UNIQUE MESSAGES")
    for msg, count in stats['message_counts'].most_common(20):
        msg_preview = msg[:70] + "..." if len(msg) > 70 else msg
        print(f"   [{count:3}x] {msg_preview}")
    
    print("\n" + "="*80)

def print_flow_trace_details(logs):
    """Print detailed FlowTrace analysis"""
    flow_traces = [log for log in logs if log.get('source') == 'FlowTrace']
    
    if not flow_traces:
        print("\nNo FlowTrace logs found")
        return
    
    print("\n" + "="*80)
    print("🔍 FLOW TRACE DETAILED ANALYSIS")
    print("="*80)
    
    # Group by flow
    by_flow = defaultdict(list)
    for log in flow_traces:
        flow = log.get('context', {}).get('flow', 'unknown')
        by_flow[flow].append(log)
    
    for flow, flow_logs in by_flow.items():
        print(f"\n📌 Flow: {flow} ({len(flow_logs)} traces)")
        
        # Sort by sequence
        sorted_logs = sorted(flow_logs, key=lambda x: x.get('context', {}).get('sequence', 0))
        
        # Print sequence
        for log in sorted_logs[-20:]:  # Last 20
            ctx = log.get('context', {})
            seq = ctx.get('sequence', '?')
            step = ctx.get('step', '?')
            trace_id = ctx.get('traceId', '?')
            
            # Extract useful context
            extras = []
            for k, v in ctx.items():
                if k not in ['traceId', 'sequence', 'flow', 'step', 'timestamp', 'userAgent', 'url']:
                    extras.append(f"{k}={v}")
            
            extra_str = f" ({', '.join(extras[:3])})" if extras else ""
            print(f"   #{seq:5} [{trace_id:30}] {step}{extra_str}")

def main():
    parser = argparse.ArgumentParser(description='Analyze Cogitate logs')
    parser.add_argument('-n', '--limit', type=int, default=1000, help='Number of logs to fetch')
    parser.add_argument('-f', '--flow', action='store_true', help='Show detailed FlowTrace analysis')
    parser.add_argument('-j', '--json', action='store_true', help='Output as JSON')
    args = parser.parse_args()
    
    print(f"Fetching {args.limit} logs from {BASE_URL}...")
    logs = fetch_logs(args.limit)
    
    if not logs:
        print("No logs found")
        return
    
    stats = analyze_logs(logs)
    
    if args.json:
        # Convert Counter objects to dicts for JSON serialization
        json_stats = {
            'total_logs': stats['total_logs'],
            'by_level': dict(stats['level_counts']),
            'by_source': dict(stats['source_counts']),
            'flow_traces': stats['flow_traces'],
            'flow_by_step': dict(stats['flow_steps']),
            'flow_by_flow': dict(stats['flow_flows']),
            'repeated_messages': dict(stats['repeated_messages']),
            'logs_per_second': stats['logs_per_second']
        }
        print(json.dumps(json_stats, indent=2))
    else:
        print_analysis(stats)
        
        if args.flow:
            print_flow_trace_details(logs)

if __name__ == '__main__':
    main()
