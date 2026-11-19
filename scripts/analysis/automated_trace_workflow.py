#!/usr/bin/env python3
"""
Automated Trace Workflow - Chat Flow Debugging

This script automates the process of:
1. Clearing logs
2. Enabling tracing via API
3. Sending test messages to specific agents
4. Capturing and analyzing traces
5. Generating comparison reports

Usage:
    python scripts/automated_trace_workflow.py
    
    # Or with specific agents
    python scripts/automated_trace_workflow.py --agent-good 16 --agent-bad 21
"""

import requests
import json
import time
import argparse
from datetime import datetime
from typing import Optional
from pathlib import Path

# Configuration
BACKEND_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:5173"
OUTPUT_DIR = Path("/tmp/trace_workflows")


class TraceWorkflow:
    """Automated trace workflow for debugging chat flows."""
    
    def __init__(self, agent_good: int = 16, agent_bad: int = 21, session_id: Optional[int] = None):
        self.agent_good = agent_good
        self.agent_bad = agent_bad
        self.session_id = session_id or int(time.time()) % 10000  # Unique session ID
        self.output_dir = OUTPUT_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        print("=" * 80)
        print("AUTOMATED TRACE WORKFLOW")
        print("=" * 80)
        print(f"\nConfiguration:")
        print(f"  Good Agent:  #{agent_good}")
        print(f"  Bad Agent:   #{agent_bad}")
        print(f"  Session ID:  {session_id}")
        print(f"  Output Dir:  {self.output_dir}")
        print()
    
    def clear_logs(self) -> bool:
        """Clear frontend logs."""
        print("📡 Step 1: Clearing logs...")
        try:
            response = requests.delete(f"{BACKEND_URL}/api/v1/logs/clear-frontend", timeout=10)
            if response.status_code == 200:
                print("   ✅ Logs cleared successfully")
                return True
            else:
                print(f"   ⚠️  Clear returned status {response.status_code}")
                return True  # Continue anyway
        except requests.RequestException as e:
            print(f"   ❌ Error clearing logs: {e}")
            return False
    
    def enable_tracing(self) -> bool:
        """Enable tracing via API (if endpoint exists) or provide instructions."""
        print("\n📡 Step 2: Enabling tracing...")
        
        # Check if there's a config endpoint
        try:
            # Try to update config via API (if available)
            config_data = {
                "enableTracing": True,
                "enableFlowTraces": True,
                "traceSamplingRate": 1.0,
                "enableDeduplication": False,
                "backendLoggingEnabled": True
            }
            
            # Note: This endpoint may not exist yet - frontend config is typically client-side
            # For now, we'll document the requirement
            print("   ℹ️  Tracing must be enabled in browser console:")
            print(f"   ")
            print(f"   Open: {FRONTEND_URL}")
            print(f"   Console: loggingConfigService.updateConfig({{")
            for key, value in config_data.items():
                print(f"     {key}: {json.dumps(value)},")
            print(f"   }})")
            print()
            print("   ⏸️  Press Enter after enabling tracing in browser...")
            input()
            
            print("   ✅ Tracing enabled")
            return True
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return False
    
    def send_test_message(self, agent_id: int, message: str = "Hello, this is an automated trace test.") -> dict:
        """Send a test message to an agent and capture response."""
        print(f"\n📡 Sending test message to Agent #{agent_id}...")
        
        try:
            payload = {
                "agent_id": agent_id,
                "message": message,
                "session_id": self.session_id,
                "stream": True
            }
            
            start_time = time.time()
            response = requests.post(
                f"{BACKEND_URL}/api/v1/chat/stream",
                json=payload,
                timeout=30,
                stream=True
            )
            
            elapsed = time.time() - start_time
            
            result = {
                "agent_id": agent_id,
                "status_code": response.status_code,
                "elapsed_seconds": round(elapsed, 2),
                "success": response.status_code == 200,
                "timestamp": datetime.now().isoformat()
            }
            
            if response.status_code == 200:
                # Read streaming response
                content = ""
                chunk_count = 0
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode('utf-8')
                        if line_str.startswith('data: '):
                            data = line_str[6:]
                            if data != '[DONE]':
                                try:
                                    parsed = json.loads(data)
                                    if 'choices' in parsed and parsed['choices']:
                                        delta = parsed['choices'][0].get('delta', {})
                                        content += delta.get('content', '')
                                        chunk_count += 1
                                except json.JSONDecodeError:
                                    pass
                
                result["chunks_received"] = chunk_count
                result["content_length"] = len(content)
                result["content_preview"] = content[:100] + "..." if len(content) > 100 else content
                print(f"   ✅ Success - {chunk_count} chunks, {len(content)} chars in {elapsed:.2f}s")
                
            else:
                result["error"] = response.text[:200]
                print(f"   ❌ Failed - Status {response.status_code}")
            
            return result
            
        except requests.Timeout:
            print(f"   ❌ Timeout after 30s")
            return {
                "agent_id": agent_id,
                "status_code": 0,
                "elapsed_seconds": 30.0,
                "success": False,
                "error": "Timeout",
                "timestamp": datetime.now().isoformat()
            }
        except requests.RequestException as e:
            print(f"   ❌ Error: {e}")
            return {
                "agent_id": agent_id,
                "status_code": 0,
                "elapsed_seconds": 0.0,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def fetch_traces(self, limit: int = 500) -> list:
        """Fetch recent flow traces."""
        print(f"\n📡 Fetching traces (limit={limit})...")
        
        try:
            response = requests.get(
                f"{BACKEND_URL}/api/v1/logs/recent",
                params={"n": limit},
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            logs = data.get('items', []) if isinstance(data, dict) else data
            
            # Filter for FlowTrace
            traces = [
                log for log in logs
                if log.get('source') == 'FlowTrace'
                or 'FLOW TRACE' in log.get('message', '')
            ]
            
            print(f"   ✅ Fetched {len(traces)} flow traces from {len(logs)} total logs")
            return traces
            
        except requests.RequestException as e:
            print(f"   ❌ Error fetching traces: {e}")
            return []
    
    def analyze_traces(self, traces: list, label: str) -> dict:
        """Analyze trace sequence."""
        print(f"\n📊 Analyzing {label} traces...")
        
        if not traces:
            return {"error": "No traces found", "total": 0}
        
        analysis = {
            "label": label,
            "total_traces": len(traces),
            "first_trace": None,
            "last_trace": None,
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
                "timestamp": trace.get('timestamp'),
                "context": {
                    k: v for k, v in ctx.items()
                    if k not in ['traceId', 'sequence', 'flow', 'step', 'timestamp', 'perfTime']
                }
            })
            
            # Track first and last
            if not analysis["first_trace"]:
                analysis["first_trace"] = {"flow": flow, "step": step, "sequence": sequence}
            analysis["last_trace"] = {"flow": flow, "step": step, "sequence": sequence}
            
            # Check for errors
            if 'error' in str(ctx).lower():
                analysis["errors"].append({
                    "sequence": sequence,
                    "step": step,
                    "error": ctx.get('error', 'Unknown'),
                    "message": trace.get('message', '')
                })
        
        # Print summary
        print(f"   Total traces: {analysis['total_traces']}")
        if analysis['first_trace']:
            print(f"   First: {analysis['first_trace']['flow']}:{analysis['first_trace']['step']} (seq #{analysis['first_trace']['sequence']})")
        if analysis['last_trace']:
            print(f"   Last:  {analysis['last_trace']['flow']}:{analysis['last_trace']['step']} (seq #{analysis['last_trace']['sequence']})")
        
        if analysis['errors']:
            print(f"   🚨 Errors: {len(analysis['errors'])}")
            for err in analysis['errors'][:3]:  # Show first 3
                print(f"      #{err['sequence']} - {err['step']}: {err['error']}")
        else:
            print(f"   ✅ No errors detected")
        
        return analysis
    
    def compare_analyses(self, good: dict, bad: dict) -> dict:
        """Compare two trace analyses."""
        print("\n" + "=" * 80)
        print("📊 COMPARISON ANALYSIS")
        print("=" * 80)
        
        comparison = {
            "good_total": good.get('total_traces', 0),
            "bad_total": bad.get('total_traces', 0),
            "difference": good.get('total_traces', 0) - bad.get('total_traces', 0),
            "good_errors": len(good.get('errors', [])),
            "bad_errors": len(bad.get('errors', [])),
            "divergence_point": None,
            "divergence_details": None
        }
        
        print(f"\nGood flow: {comparison['good_total']} traces")
        print(f"Bad flow:  {comparison['bad_total']} traces")
        print(f"Difference: {comparison['difference']} traces")
        
        # Find divergence point
        good_steps = good.get('steps', [])
        bad_steps = bad.get('steps', [])
        
        for i in range(min(len(good_steps), len(bad_steps))):
            if good_steps[i] != bad_steps[i]:
                comparison['divergence_point'] = i
                comparison['divergence_details'] = {
                    "index": i,
                    "good_step": good_steps[i],
                    "bad_step": bad_steps[i]
                }
                print(f"\n🔍 Flows diverge at trace #{i + 1}")
                print(f"   Good: {good_steps[i]}")
                print(f"   Bad:  {bad_steps[i]}")
                break
        
        if not comparison['divergence_point'] and len(bad_steps) < len(good_steps):
            comparison['divergence_point'] = len(bad_steps)
            print(f"\n🔍 Bad flow stopped early at trace #{len(bad_steps)}")
            if bad_steps:
                print(f"   Last trace: {bad_steps[-1]}")
        
        if comparison['bad_errors'] > 0:
            print(f"\n🚨 Errors in bad flow: {comparison['bad_errors']}")
            for err in bad.get('errors', [])[:5]:
                print(f"   #{err['sequence']} - {err['step']}")
                print(f"      {err['error']}")
        
        return comparison
    
    def save_report(self, good_result: dict, bad_result: dict, good_analysis: dict, bad_analysis: dict, comparison: dict):
        """Save comprehensive report."""
        print("\n" + "=" * 80)
        print("💾 Saving Report")
        print("=" * 80)
        
        report = {
            "workflow_summary": {
                "timestamp": datetime.now().isoformat(),
                "agent_good": self.agent_good,
                "agent_bad": self.agent_bad,
                "session_id": self.session_id,
                "output_dir": str(self.output_dir)
            },
            "good_agent_result": good_result,
            "bad_agent_result": bad_result,
            "good_analysis": good_analysis,
            "bad_analysis": bad_analysis,
            "comparison": comparison
        }
        
        # Save JSON
        json_file = self.output_dir / "trace_comparison.json"
        with open(json_file, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"   ✅ JSON report: {json_file}")
        
        # Save human-readable text
        txt_file = self.output_dir / "trace_comparison.txt"
        with open(txt_file, 'w') as f:
            f.write("TRACE WORKFLOW COMPARISON REPORT\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Timestamp: {report['workflow_summary']['timestamp']}\n")
            f.write(f"Good Agent:  #{self.agent_good}\n")
            f.write(f"Bad Agent:   #{self.agent_bad}\n")
            f.write(f"Session ID:  {self.session_id}\n\n")
            
            f.write("GOOD AGENT RESULT\n")
            f.write("-" * 80 + "\n")
            f.write(f"Status: {'✅ Success' if good_result['success'] else '❌ Failed'}\n")
            f.write(f"Time: {good_result['elapsed_seconds']}s\n")
            if good_result.get('chunks_received'):
                f.write(f"Chunks: {good_result['chunks_received']}\n")
                f.write(f"Content: {good_result.get('content_preview', 'N/A')}\n")
            f.write("\n")
            
            f.write("BAD AGENT RESULT\n")
            f.write("-" * 80 + "\n")
            f.write(f"Status: {'✅ Success' if bad_result['success'] else '❌ Failed'}\n")
            f.write(f"Time: {bad_result['elapsed_seconds']}s\n")
            if bad_result.get('error'):
                f.write(f"Error: {bad_result['error']}\n")
            f.write("\n")
            
            f.write("TRACE ANALYSIS\n")
            f.write("-" * 80 + "\n")
            f.write(f"Good traces: {good_analysis.get('total_traces', 0)}\n")
            f.write(f"Bad traces:  {bad_analysis.get('total_traces', 0)}\n")
            f.write(f"Good first:  {good_analysis.get('first_trace', {})}\n")
            f.write(f"Good last:   {good_analysis.get('last_trace', {})}\n")
            f.write(f"Bad first:   {bad_analysis.get('first_trace', {})}\n")
            f.write(f"Bad last:    {bad_analysis.get('last_trace', {})}\n")
            f.write("\n")
            
            if good_analysis.get('trace_details'):
                f.write("GOOD FLOW SEQUENCE\n")
                f.write("-" * 80 + "\n")
                for detail in good_analysis['trace_details'][:20]:
                    f.write(f"#{detail['sequence']} [{detail['flow']}:{detail['step']}]\n")
                if len(good_analysis['trace_details']) > 20:
                    f.write(f"... and {len(good_analysis['trace_details']) - 20} more\n")
                f.write("\n")
            
            if bad_analysis.get('trace_details'):
                f.write("BAD FLOW SEQUENCE\n")
                f.write("-" * 80 + "\n")
                for detail in bad_analysis['trace_details'][:20]:
                    f.write(f"#{detail['sequence']} [{detail['flow']}:{detail['step']}]\n")
                if len(bad_analysis['trace_details']) > 20:
                    f.write(f"... and {len(bad_analysis['trace_details']) - 20} more\n")
                f.write("\n")
            
            if comparison.get('divergence_details'):
                f.write("DIVERGENCE POINT\n")
                f.write("-" * 80 + "\n")
                div = comparison['divergence_details']
                f.write(f"Index: {div['index']}\n")
                f.write(f"Good: {div['good_step']}\n")
                f.write(f"Bad:  {div['bad_step']}\n")
                f.write("\n")
            
            if bad_analysis.get('errors'):
                f.write("ERRORS IN BAD FLOW\n")
                f.write("-" * 80 + "\n")
                for err in bad_analysis['errors']:
                    f.write(f"#{err['sequence']} - {err['step']}\n")
                    f.write(f"  {err['error']}\n\n")
        
        print(f"   ✅ Text report: {txt_file}")
        
        # Save trace sequences for detailed review
        traces_file = self.output_dir / "trace_sequences.json"
        with open(traces_file, 'w') as f:
            json.dump({
                "good_traces": good_analysis.get('trace_details', []),
                "bad_traces": bad_analysis.get('trace_details', [])
            }, f, indent=2)
        print(f"   ✅ Trace sequences: {traces_file}")
    
    def run(self):
        """Execute the complete workflow."""
        print("\n" + "=" * 80)
        print("STARTING AUTOMATED TRACE WORKFLOW")
        print("=" * 80)
        
        # Step 1: Clear logs
        if not self.clear_logs():
            print("\n⚠️  Failed to clear logs, continuing anyway...")
        
        # Step 2: Enable tracing
        if not self.enable_tracing():
            print("\n⚠️  Tracing not enabled, traces may not be captured...")
        
        # Step 3: Send to good agent
        print("\n" + "=" * 80)
        print("TESTING GOOD AGENT")
        print("=" * 80)
        good_result = self.send_test_message(self.agent_good)
        
        # Small delay to ensure logs are written
        time.sleep(1)
        
        # Fetch and analyze good traces
        good_traces = self.fetch_traces(500)
        good_analysis = self.analyze_traces(good_traces, "Good Agent")
        
        # Save good traces
        with open(self.output_dir / "good_traces.json", 'w') as f:
            json.dump({"traces": good_traces, "analysis": good_analysis}, f, indent=2)
        
        # Step 4: Clear logs for bad agent test
        print("\n" + "=" * 80)
        self.clear_logs()
        
        # Step 5: Send to bad agent
        print("\n" + "=" * 80)
        print("TESTING BAD AGENT")
        print("=" * 80)
        bad_result = self.send_test_message(self.agent_bad)
        
        # Small delay
        time.sleep(1)
        
        # Fetch and analyze bad traces
        bad_traces = self.fetch_traces(500)
        bad_analysis = self.analyze_traces(bad_traces, "Bad Agent")
        
        # Save bad traces
        with open(self.output_dir / "bad_traces.json", 'w') as f:
            json.dump({"traces": bad_traces, "analysis": bad_analysis}, f, indent=2)
        
        # Step 6: Compare
        comparison = self.compare_analyses(good_analysis, bad_analysis)
        
        # Step 7: Save report
        self.save_report(good_result, bad_result, good_analysis, bad_analysis, comparison)
        
        # Final summary
        print("\n" + "=" * 80)
        print("WORKFLOW COMPLETE")
        print("=" * 80)
        print(f"\n📁 Output directory: {self.output_dir}")
        print(f"📄 Files created:")
        for file in sorted(self.output_dir.glob("*")):
            print(f"   - {file.name}")
        
        print(f"\n🔍 Quick Summary:")
        print(f"   Good agent: {'✅' if good_result['success'] else '❌'} - {good_result['elapsed_seconds']}s")
        print(f"   Bad agent:  {'✅' if bad_result['success'] else '❌'} - {bad_result['elapsed_seconds']}s")
        print(f"   Trace difference: {comparison['difference']} traces")
        
        if comparison.get('divergence_details'):
            div = comparison['divergence_details']
            print(f"\n🎯 Root cause likely at:")
            print(f"   Step: {div['bad_step']}")
            print(f"   Expected: {div['good_step']}")
        
        print("\n" + "=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Automated trace workflow for debugging chat flows"
    )
    parser.add_argument(
        "--agent-good", "-g",
        type=int,
        default=16,
        help="Agent ID known to work (default: 16 - Hemingway/Ollama)"
    )
    parser.add_argument(
        "--agent-bad", "-b",
        type=int,
        default=21,
        help="Agent ID known to fail (default: 21 - Hunter/OpenRouter retired)"
    )
    parser.add_argument(
        "--session-id", "-s",
        type=int,
        default=None,
        help="Session ID to use (default: auto-generated)"
    )
    
    args = parser.parse_args()
    
    workflow = TraceWorkflow(
        agent_good=args.agent_good,
        agent_bad=args.agent_bad,
        session_id=args.session_id
    )
    
    workflow.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        raise
