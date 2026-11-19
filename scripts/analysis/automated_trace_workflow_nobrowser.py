#!/usr/bin/env python3
"""
Fully Automated Trace Workflow - No Browser Required

This version:
- Uses backend API directly
- Captures backend logs (which include frontend traces when sent)
- No browser interaction needed
- Tests the actual chat flow end-to-end

Usage:
    python scripts/automated_trace_workflow_nobrowser.py
"""

import requests
import json
import time
import argparse
from datetime import datetime
from pathlib import Path

# Configuration
BACKEND_URL = "http://localhost:8000"
OUTPUT_DIR = Path("/tmp/trace_workflows")


class FullyAutomatedWorkflow:
    """Fully automated workflow - no browser needed."""
    
    def __init__(self, agent_good: int = 16, agent_bad: int = 21):
        self.agent_good = agent_good
        self.agent_bad = agent_bad
        self.session_id = int(time.time()) % 10000
        self.output_dir = OUTPUT_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        print("=" * 80)
        print("FULLY AUTOMATED TRACE WORKFLOW (No Browser)")
        print("=" * 80)
        print(f"\nConfiguration:")
        print(f"  Good Agent:  #{agent_good}")
        print(f"  Bad Agent:   #{agent_bad}")
        print(f"  Session ID:  {self.session_id}")
        print(f"  Output Dir:  {self.output_dir}")
        print()
    
    def clear_logs(self) -> bool:
        """Clear frontend logs."""
        print("📡 Clearing logs...")
        try:
            response = requests.delete(f"{BACKEND_URL}/api/v1/logs/clear-frontend", timeout=10)
            if response.status_code == 200:
                print("   ✅ Logs cleared")
                return True
            return True
        except requests.RequestException as e:
            print(f"   ⚠️  Error: {e}")
            return False
    
    def get_log_count(self) -> int:
        """Get current log count."""
        try:
            response = requests.get(f"{BACKEND_URL}/api/v1/logs/recent?n=1", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get('total', 0)
        except:
            pass
        return 0
    
    def send_test_message(self, agent_id: int, message: str = "Hello, this is an automated trace test.") -> dict:
        """Send test message and capture full response."""
        print(f"\n📡 Sending message to Agent #{agent_id}...")
        
        start_time = time.time()
        
        try:
            payload = {
                "agent_id": agent_id,
                "message": message,
                "session_id": self.session_id,
                "stream": True
            }
            
            response = requests.post(
                f"{BACKEND_URL}/api/v1/chat/stream",
                json=payload,
                timeout=60,  # Increased timeout for Ollama
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
                content = ""
                chunk_count = 0
                events = []
                
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode('utf-8')
                        events.append(line_str)
                        
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
                result["sse_events"] = len(events)
                print(f"   ✅ Success - {chunk_count} chunks, {len(content)} chars in {elapsed:.2f}s")
            else:
                result["error"] = response.text[:300]
                print(f"   ❌ Failed - Status {response.status_code}")
                try:
                    error_json = response.json()
                    result["error_detail"] = error_json
                except:
                    pass
            
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
    
    def fetch_logs(self, limit: int = 500) -> list:
        """Fetch recent logs."""
        print(f"\n📡 Fetching logs (limit={limit})...")
        
        try:
            response = requests.get(
                f"{BACKEND_URL}/api/v1/logs/recent",
                params={"n": limit},
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            logs = data.get('items', []) if isinstance(data, dict) else data
            
            print(f"   ✅ Fetched {len(logs)} logs")
            return logs
            
        except requests.RequestException as e:
            print(f"   ❌ Error: {e}")
            return []
    
    def analyze_logs(self, logs: list, label: str) -> dict:
        """Analyze logs for flow traces and errors."""
        print(f"\n📊 Analyzing {label} logs...")
        
        if not logs:
            return {"error": "No logs found", "total": 0}
        
        # Filter for relevant logs
        flow_traces = [
            log for log in logs
            if log.get('source') == 'FlowTrace'
            or 'FLOW TRACE' in log.get('message', '')
        ]
        
        errors = [
            log for log in logs
            if log.get('level') in ['error', 'critical']
            or 'error' in log.get('message', '').lower()
        ]
        
        analysis = {
            "label": label,
            "total_logs": len(logs),
            "flow_traces": len(flow_traces),
            "errors": len(errors),
            "trace_details": [],
            "error_details": []
        }
        
        # Analyze flow traces
        for trace in flow_traces:
            ctx = trace.get('context', {})
            analysis["trace_details"].append({
                "sequence": ctx.get('sequence', '?'),
                "flow": ctx.get('flow', 'unknown'),
                "step": ctx.get('step', 'unknown'),
                "message": trace.get('message', ''),
                "context": {
                    k: v for k, v in ctx.items()
                    if k not in ['traceId', 'sequence', 'flow', 'step', 'timestamp', 'perfTime']
                }
            })
        
        # Analyze errors
        for err in errors:
            analysis["error_details"].append({
                "level": err.get('level'),
                "source": err.get('source'),
                "message": err.get('message'),
                "context": err.get('context', {})
            })
        
        # Print summary
        print(f"   Total logs: {analysis['total_logs']}")
        print(f"   Flow traces: {analysis['flow_traces']}")
        print(f"   Errors: {analysis['errors']}")
        
        if flow_traces:
            first = flow_traces[0]
            last = flow_traces[-1]
            print(f"   First trace: {first.get('message', 'N/A')}")
            print(f"   Last trace:  {last.get('message', 'N/A')}")
        
        if errors and analysis['error_details']:
            print(f"   🚨 Error examples:")
            for err in analysis['error_details'][:3]:
                print(f"      [{err['level']}] {err['message'][:80]}")
        
        return analysis
    
    def compare_results(self, good: dict, bad: dict, good_analysis: dict, bad_analysis: dict):
        """Compare results from both agents."""
        print("\n" + "=" * 80)
        print("📊 COMPARISON ANALYSIS")
        print("=" * 80)
        
        print(f"\n✅ GOOD AGENT #{self.agent_good}:")
        print(f"   Status: {'Success' if good['success'] else 'Failed'}")
        print(f"   Time: {good['elapsed_seconds']}s")
        if good.get('chunks_received'):
            print(f"   Chunks: {good['chunks_received']}")
            print(f"   Content: {good.get('content_preview', 'N/A')}")
        
        print(f"\n❌ BAD AGENT #{self.agent_bad}:")
        print(f"   Status: {'Success' if bad['success'] else 'Failed'}")
        print(f"   Time: {bad['elapsed_seconds']}s")
        if bad.get('error'):
            print(f"   Error: {bad['error'][:100]}")
        
        print(f"\n📈 LOG COMPARISON:")
        print(f"   Good agent logs: {good_analysis.get('total_logs', 0)}")
        print(f"   Bad agent logs:  {bad_analysis.get('total_logs', 0)}")
        print(f"   Good traces:     {good_analysis.get('flow_traces', 0)}")
        print(f"   Bad traces:      {bad_analysis.get('flow_traces', 0)}")
        
        # Root cause analysis
        print(f"\n🎯 ROOT CAUSE ANALYSIS:")
        
        if not bad['success']:
            if bad.get('error_detail'):
                error_detail = bad['error_detail']
                if isinstance(error_detail, dict):
                    detail = error_detail.get('detail', 'Unknown error')
                else:
                    detail = str(error_detail)
                
                print(f"   Failure type: API Error")
                print(f"   Error detail: {detail}")
                
                if 'model' in detail.lower() and ('not found' in detail.lower() or 'retired' in detail.lower()):
                    print(f"   ✅ Root cause: Model retired/unavailable")
                elif 'provider' in detail.lower():
                    print(f"   ✅ Root cause: Provider issue")
                else:
                    print(f"   ⚠️  Root cause: {detail[:100]}")
            else:
                print(f"   ⚠️  No detailed error information")
        
        if bad_analysis.get('error_details'):
            print(f"\n   Errors captured in logs:")
            for err in bad_analysis['error_details'][:3]:
                print(f"      [{err['level']}] {err['message'][:70]}")
    
    def save_report(self, good_result: dict, bad_result: dict, good_analysis: dict, bad_analysis: dict):
        """Save comprehensive report."""
        print("\n" + "=" * 80)
        print("💾 SAVING REPORT")
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
            "bad_analysis": bad_analysis
        }
        
        # JSON report
        json_file = self.output_dir / "workflow_report.json"
        with open(json_file, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"   ✅ JSON: {json_file}")
        
        # Text report
        txt_file = self.output_dir / "workflow_report.txt"
        with open(txt_file, 'w') as f:
            f.write("AUTOMATED TRACE WORKFLOW REPORT\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Timestamp: {report['workflow_summary']['timestamp']}\n")
            f.write(f"Good Agent: #{self.agent_good}\n")
            f.write(f"Bad Agent:  #{self.agent_bad}\n\n")
            
            f.write("GOOD AGENT RESULT\n")
            f.write("-" * 80 + "\n")
            f.write(f"Status: {'✅ Success' if good_result['success'] else '❌ Failed'}\n")
            f.write(f"Time: {good_result['elapsed_seconds']}s\n")
            if good_result.get('chunks_received'):
                f.write(f"Chunks: {good_result['chunks_received']}\n")
                f.write(f"Content: {good_result.get('content_preview', 'N/A')}\n")
            f.write(f"Logs: {good_analysis.get('total_logs', 0)}\n")
            f.write(f"Flow traces: {good_analysis.get('flow_traces', 0)}\n\n")
            
            f.write("BAD AGENT RESULT\n")
            f.write("-" * 80 + "\n")
            f.write(f"Status: {'✅ Success' if bad_result['success'] else '❌ Failed'}\n")
            f.write(f"Time: {bad_result['elapsed_seconds']}s\n")
            if bad_result.get('error'):
                f.write(f"Error: {bad_result['error']}\n")
            if bad_result.get('error_detail'):
                f.write(f"Detail: {bad_result['error_detail']}\n")
            f.write(f"Logs: {bad_analysis.get('total_logs', 0)}\n")
            f.write(f"Flow traces: {bad_analysis.get('flow_traces', 0)}\n\n")
            
            if bad_analysis.get('error_details'):
                f.write("ERRORS IN BAD FLOW\n")
                f.write("-" * 80 + "\n")
                for err in bad_analysis['error_details']:
                    f.write(f"[{err['level']}] {err['source']}: {err['message']}\n")
                f.write("\n")
        
        print(f"   ✅ Text: {txt_file}")
        
        # Save raw logs
        with open(self.output_dir / "good_logs.json", 'w') as f:
            json.dump(good_analysis.get('trace_details', []), f, indent=2)
        
        with open(self.output_dir / "bad_logs.json", 'w') as f:
            json.dump(bad_analysis.get('trace_details', []), f, indent=2)
        
        print(f"   ✅ Raw logs saved")
    
    def run(self):
        """Execute complete workflow."""
        print("\n" + "=" * 80)
        print("STARTING WORKFLOW")
        print("=" * 80)
        
        # Test good agent
        print("\n" + "=" * 80)
        print("PHASE 1: GOOD AGENT TEST")
        print("=" * 80)
        
        self.clear_logs()
        good_result = self.send_test_message(self.agent_good)
        time.sleep(1)  # Allow logs to flush
        good_logs = self.fetch_logs(500)
        good_analysis = self.analyze_logs(good_logs, "Good Agent")
        
        # Save good agent data
        with open(self.output_dir / "good_agent_raw.json", 'w') as f:
            json.dump({"result": good_result, "logs": good_logs}, f, indent=2)
        
        # Test bad agent
        print("\n" + "=" * 80)
        print("PHASE 2: BAD AGENT TEST")
        print("=" * 80)
        
        self.clear_logs()
        bad_result = self.send_test_message(self.agent_bad)
        time.sleep(1)
        bad_logs = self.fetch_logs(500)
        bad_analysis = self.analyze_logs(bad_logs, "Bad Agent")
        
        # Save bad agent data
        with open(self.output_dir / "bad_agent_raw.json", 'w') as f:
            json.dump({"result": bad_result, "logs": bad_logs}, f, indent=2)
        
        # Compare
        self.compare_results(good_result, bad_result, good_analysis, bad_analysis)
        
        # Save report
        self.save_report(good_result, bad_result, good_analysis, bad_analysis)
        
        # Final summary
        print("\n" + "=" * 80)
        print("WORKFLOW COMPLETE")
        print("=" * 80)
        print(f"\n📁 Output: {self.output_dir}")
        print(f"📄 Files:")
        for file in sorted(self.output_dir.glob("*")):
            print(f"   - {file.name}")
        
        print(f"\n🔍 Summary:")
        print(f"   Good: {'✅' if good_result['success'] else '❌'} {good_result['elapsed_seconds']}s")
        print(f"   Bad:  {'✅' if bad_result['success'] else '❌'} {bad_result['elapsed_seconds']}s")
        
        if not bad_result['success'] and bad_result.get('error_detail'):
            detail = bad_result['error_detail']
            if isinstance(detail, dict):
                print(f"\n🎯 Root cause: {detail.get('detail', 'Unknown')[:100]}")
        
        print("\n" + "=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Fully automated trace workflow")
    parser.add_argument("--agent-good", "-g", type=int, default=16, help="Good agent ID")
    parser.add_argument("--agent-bad", "-b", type=int, default=21, help="Bad agent ID")
    args = parser.parse_args()
    
    workflow = FullyAutomatedWorkflow(
        agent_good=args.agent_good,
        agent_bad=args.agent_bad
    )
    workflow.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise
