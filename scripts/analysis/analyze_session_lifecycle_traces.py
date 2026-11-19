#!/usr/bin/env python3
"""
Session Lifecycle Debug Trace Analyzer

Analyzes SessionLifecycleDebug traces to identify the root cause of duplicate session issues.

Focus Areas:
- Temp session creation and storage
- loadFromBackend timing and temp session preservation
- replaceSessionById operation (CRITICAL - where the bug likely is)
- Session ID tracking through the lifecycle

Usage:
    # Fetch traces and analyze immediately
    python3 scripts/analyze_session_lifecycle_traces.py --fetch --limit 1000

    # Analyze from exported file
    curl "http://localhost:8000/api/v1/logs/traces/export?format=json&limit=1000" -o traces.json
    python3 scripts/analyze_session_lifecycle_traces.py traces.json

    # Filter to only SessionLifecycleDebug traces
    python3 scripts/analyze_session_lifecycle_traces.py traces.json --filter SessionLifecycleDebug

    # Save report
    python3 scripts/analyze_session_lifecycle_traces.py traces.json --output report.txt
"""

import json
import subprocess
import sys
from datetime import datetime
from collections import defaultdict
from typing import Any

API_URL = "http://localhost:8000"

# ANSI colors for terminal output
class Colors:
    RESET = '\033[0m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'


def fetch_traces(limit: int = 1000) -> list[dict]:
    """Fetch traces from API."""
    cmd = [
        "curl", "-s",
        f"{API_URL}/api/v1/logs/traces/export?format=json&limit={limit}"
    ]

    print(f"{Colors.CYAN}Fetching {limit} traces from {API_URL}...{Colors.RESET}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"{Colors.RED}Error fetching traces: {result.stderr}{Colors.RESET}")
        sys.exit(1)

    data = json.loads(result.stdout)

    if isinstance(data, dict) and 'traces' in data:
        return data['traces']
    return data


def load_traces(filepath: str) -> list[dict]:
    """Load traces from JSON file."""
    with open(filepath, 'r') as f:
        data = json.load(f)

    if isinstance(data, dict) and 'traces' in data:
        return data['traces']
    return data


def filter_session_lifecycle_traces(traces: list[dict]) -> list[dict]:
    """Filter to only SessionLifecycleDebug traces."""
    return [t for t in traces if t.get('flow') == 'SessionLifecycleDebug']


def extract_session_id(trace: dict) -> str | None:
    """Extract session ID from trace context."""
    ctx = trace.get('context', {})
    session_id = (
        ctx.get('sessionId') or
        ctx.get('tempSessionId') or
        ctx.get('backendSessionId') or
        ctx.get('oldId') or
        ctx.get('newId')
    )
    if session_id:
        return session_id
    
    # Try sessionIds array
    session_ids = ctx.get('sessionIds', ctx.get('sessionIdsAfter', []))
    if session_ids and isinstance(session_ids, list) and len(session_ids) > 0:
        return session_ids[0]
    
    return None


def build_session_lifecycle(traces: list[dict]) -> dict[str, list[dict]]:
    """Group traces by session ID to build lifecycle timeline."""
    lifecycle = defaultdict(list)

    for trace in sorted(traces, key=lambda x: x.get('sequence', 0)):
        session_id = extract_session_id(trace)
        if session_id:
            lifecycle[session_id].append(trace)

    return dict(lifecycle)


def analyze_temp_session_flow(traces: list[dict]) -> list[dict]:
    """
    Analyze the complete flow of temp sessions.
    This is the CRITICAL analysis for the duplicate session bug.
    """
    issues = []

    # Group by temp session ID
    temp_sessions = {}
    for trace in traces:
        ctx = trace.get('context', {})
        temp_id = ctx.get('tempSessionId')
        if temp_id and temp_id.startswith('session-'):
            if temp_id not in temp_sessions:
                temp_sessions[temp_id] = {
                    'created': None,
                    'added': None,
                    'upserted': None,
                    'committed': None,
                    'replaced': None,
                    'final_state': None,
                    'traces': []
                }
            temp_sessions[temp_id]['traces'].append(trace)

    # Analyze each temp session's lifecycle
    for temp_id, data in temp_sessions.items():
        messages_count_at_commit = 0
        
        for trace in data['traces']:
            step = trace.get('step', '')
            ctx = trace.get('context', {})

            if step == 'createNewSession':
                data['created'] = trace
            elif step == 'createNewSessionComplete':
                data['added'] = trace
            elif step == 'upsertSessionComplete':
                data['upserted'] = trace
                # Check if session made it into the list
                if not ctx.get('sessionInList', False):
                    issues.append({
                        'type': 'upsert_failed',
                        'severity': 'CRITICAL',
                        'session': temp_id,
                        'sequence': trace.get('sequence'),
                        'message': f"upsertSession completed but session NOT in sessions list!",
                        'context': ctx
                    })
            elif step == 'loadFromBackendEntry':
                data['load_entry'] = trace
            elif step == 'loadFromBackend:preservingTempSessions':
                data['load_preserving'] = trace
            elif step == 'loadFromBackendComplete':
                data['load_complete'] = trace
            elif step == 'commitPendingSessionEntry':
                data['committed'] = trace
                messages_count_at_commit = ctx.get('sessionMsgs', 0)
            elif step == 'replaceSessionByIdEntry':
                data['replace_entry'] = trace
            elif step == 'replaceSessionByIdFindResult':
                data['replace_find'] = trace
                # CRITICAL CHECK: Was the old session found?
                if not ctx.get('oldSessionFound', False):
                    issues.append({
                        'type': 'session_not_found',
                        'severity': 'CRITICAL',
                        'session': temp_id,
                        'sequence': trace.get('sequence'),
                        'message': f"replaceSessionById could NOT find temp session to replace!",
                        'details': {
                            'searchedInSessions': ctx.get('searchedInSessions'),
                            'searchedInActiveSession': ctx.get('searchedInActiveSession'),
                            'oldSessionIndex': ctx.get('oldSessionIndex')
                        },
                        'context': ctx
                    })
            elif step == 'replaceSessionByIdComplete':
                data['replace_complete'] = trace
                data['final_state'] = trace
                # Check for duplicate sessions
                session_ids = ctx.get('sessionIdsAfter', [])
                backend_id = ctx.get('newId')
                messages_preserved = ctx.get('messagesPreserved', 0)
                
                # Check if messages were preserved
                if messages_preserved == 0 and messages_count_at_commit > 0:
                    issues.append({
                        'type': 'messages_lost',
                        'severity': 'CRITICAL',
                        'session': temp_id,
                        'backend_session': backend_id,
                        'sequence': trace.get('sequence'),
                        'message': f"Messages LOST during replace! Had {messages_count_at_commit} messages at commit, but {messages_preserved} preserved.",
                        'context': ctx
                    })
                
                # Check if both temp and backend session exist
                if temp_id in session_ids and backend_id in session_ids:
                    issues.append({
                        'type': 'duplicate_sessions',
                        'severity': 'CRITICAL',
                        'session': temp_id,
                        'backend_session': backend_id,
                        'sequence': trace.get('sequence'),
                        'message': f"DUPLICATE: Both temp session ({temp_id}) and backend session ({backend_id}) exist!",
                        'context': ctx
                    })

    return issues


def analyze_load_from_backend_timing(traces: list[dict]) -> list[dict]:
    """Analyze timing between session creation and loadFromBackend."""
    issues = []

    # Track session lifecycle events
    events = []
    for trace in sorted(traces, key=lambda x: x.get('sequence', 0)):
        step = trace.get('step', '')
        perf_time = trace.get('context', {}).get('perfTime')
        ctx = trace.get('context', {})

        if perf_time:
            events.append({
                'sequence': trace.get('sequence'),
                'step': step,
                'perf_time': perf_time,
                'context': ctx
            })

    # Find createNewSession and track when temp session is added
    create_event = None
    upsert_complete_event = None
    add_local_complete_event = None
    load_events = []

    for event in events:
        step = event['step']
        if step == 'createNewSession':
            create_event = event
        elif step == 'upsertSessionComplete':
            upsert_complete_event = event
        elif step == 'addLocalSessionComplete':
            add_local_complete_event = event
        elif step.startswith('loadFromBackend'):
            load_events.append(event)

    # Check if upsert succeeded but addLocalSessionComplete shows failure
    if upsert_complete_event and add_local_complete_event:
        upsert_ctx = upsert_complete_event['context']
        add_ctx = add_local_complete_event['context']

        if upsert_ctx.get('sessionInList') is True and add_ctx.get('sessionInList') is False:
            issues.append({
                'type': 'session_disappeared',
                'severity': 'CRITICAL',
                'message': "Session was in list after upsert but disappeared before addLocalSessionComplete",
                'details': {
                    'upsert_sequence': upsert_complete_event['sequence'],
                    'upsert_sessionInList': upsert_ctx.get('sessionInList'),
                    'upsert_sessionIds': upsert_ctx.get('sessionIds'),
                    'addLocalComplete_sequence': add_local_complete_event['sequence'],
                    'addLocalComplete_sessionInList': add_ctx.get('sessionInList'),
                    'addLocalComplete_sessionIds': add_ctx.get('sessionIdsAfter'),
                }
            })

    # Check for loadFromBackend running during session creation
    if create_event and load_events:
        for load_event in load_events:
            if load_event['perf_time'] > create_event['perf_time']:
                # Check if this loadFromBackend captured the temp session
                load_ctx = load_event['context']
                temp_preserved = load_ctx.get('tempSessionsPreserved', 0)
                final_ids = load_ctx.get('finalSessionIds', [])

                # If temp session exists but wasn't preserved, that's the bug
                if temp_preserved == 0 and create_event:
                    create_ctx = create_event['context']
                    temp_id = create_ctx.get('tempSessionId')
                    if temp_id and temp_id not in final_ids:
                        issues.append({
                            'type': 'temp_session_not_preserved',
                            'severity': 'CRITICAL',
                            'message': f"loadFromBackend did not preserve temp session {temp_id}",
                            'details': {
                                'load_sequence': load_event['sequence'],
                                'tempSessionId': temp_id,
                                'tempSessionsPreserved': temp_preserved,
                                'finalSessionIds': final_ids
                            }
                        })
                break

    return issues


def analyze_session_counts(traces: list[dict]) -> list[dict]:
    """
    Analyze session count changes through the lifecycle.

    Note: This check is disabled as it produces false positives due to
    the complex interleaving of async operations. The critical checks
    (session_disappeared, temp_session_not_preserved) are more reliable.
    """
    return []
    # Original implementation preserved for reference:
    # issues = []
    # count_changes = []
    # ...


def print_diagnostic_summary(traces: list[dict]):
    """Print summary of diagnostic findings."""
    print(f"\n{Colors.BOLD}{Colors.MAGENTA}🔬 DIAGNOSTIC FINDINGS{Colors.RESET}")
    print("=" * 80)
    
    issues_found = []
    
    for trace in sorted(traces, key=lambda x: x.get('sequence', 0)):
        step = trace.get('step', '')
        ctx = trace.get('context', {})
        seq = trace.get('sequence', '?')
        
        # Check for messages in wrong place
        if 'commitPendingSession:DIAGNOSTIC' in step:
            msgs_in_list = ctx.get('messagesInList', 0)
            msgs_in_active = ctx.get('messagesInActive', 0)
            temp_id = ctx.get('tempSessionId')
            
            if msgs_in_active > 0 and msgs_in_list == 0:
                issues_found.append({
                    'seq': seq,
                    'type': 'messages_only_in_activeSession',
                    'detail': f"Messages ONLY in activeSession (active={msgs_in_active}, list={msgs_in_list})",
                    'session': temp_id
                })
            
            if not ctx.get('sessionInList') and ctx.get('sessionInActive'):
                issues_found.append({
                    'seq': seq,
                    'type': 'temp_session_only_in_activeSession',
                    'detail': f"Temp session ONLY in activeSession, NOT in sessions list",
                    'session': temp_id
                })
        
        # Check for replace issues
        if 'replaceSessionById:POST_DIAGNOSTIC' in step:
            temp_still_exists = ctx.get('tempSessionStillInList', False)
            duplicates = ctx.get('hasDuplicateSessions', 0)
            temp_id = ctx.get('tempSessionId')
            backend_id = ctx.get('backendSessionId')
            
            if temp_still_exists:
                issues_found.append({
                    'seq': seq,
                    'type': 'temp_session_not_removed',
                    'detail': f"Temp session {temp_id} still in list after replace!",
                    'session': temp_id
                })
            
            if duplicates > 1:
                issues_found.append({
                    'seq': seq,
                    'type': 'duplicate_sessions_created',
                    'detail': f"{duplicates} sessions with 'New Session' or 'Untitled' title",
                    'session': f"{temp_id} → {backend_id}"
                })
            
            if not ctx.get('backendSessionInList'):
                issues_found.append({
                    'seq': seq,
                    'type': 'backend_session_not_in_list',
                    'detail': f"Backend session {backend_id} NOT in sessions list after replace!",
                    'session': backend_id
                })
        
        # Check for addLocalSession issues
        if 'addLocalSession:DIAGNOSTIC_AFTER' in step:
            in_list = ctx.get('sessionInList', False)
            in_active = ctx.get('sessionInActive', False)
            session_id = ctx.get('sessionId')
            
            if not in_list and in_active:
                issues_found.append({
                    'seq': seq,
                    'type': 'session_only_in_active_after_add',
                    'detail': f"After addLocalSession, session ONLY in activeSession, NOT in list",
                    'session': session_id
                })
    
    if issues_found:
        print(f"\n{Colors.RED}⚠️  ISSUES DETECTED:{Colors.RESET}\n")
        for i, issue in enumerate(issues_found, 1):
            print(f"  {i}. [{issue['type']}] #{issue['seq']}")
            print(f"     Session: {issue['session']}")
            print(f"     {Colors.YELLOW}{issue['detail']}{Colors.RESET}\n")
        
        print(f"\n{Colors.BOLD}ROOT CAUSE ANALYSIS:{Colors.RESET}")
        
        # Analyze pattern
        has_messages_issue = any('messages_only_in_activeSession' in i['type'] for i in issues_found)
        has_temp_only_active = any('temp_session_only_in_activeSession' in i['type'] for i in issues_found)
        has_replace_issue = any('temp_session_not_removed' in i['type'] or 'duplicate_sessions_created' in i['type'] for i in issues_found)
        
        if has_messages_issue and has_temp_only_active:
            print(f"\n  {Colors.MAGENTA}📍 CONFIRMED: Messages and temp session are in activeSession but NOT in sessions list{Colors.RESET}")
            print(f"  This causes replaceSessionById to ADD instead of REPLACE (idx=-1)")
            print(f"  Result: DUPLICATE sessions (temp + backend)")
        
        if has_replace_issue:
            print(f"\n  {Colors.MAGENTA}📍 CONFIRMED: replaceSessionById created duplicate sessions{Colors.RESET}")
            print(f"  The temp session was not properly replaced")
    else:
        print(f"\n{Colors.GREEN}✅ No diagnostic issues detected{Colors.RESET}")
    
    print()


def print_session_timeline(traces: list[dict]):
    """Print a visual timeline of session lifecycle events."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}SESSION LIFECYCLE TIMELINE{Colors.RESET}")
    print("-" * 80)

    # Group by session ID
    by_session = defaultdict(list)
    for trace in sorted(traces, key=lambda x: x.get('sequence', 0)):
        session_id = extract_session_id(trace)
        if session_id:
            by_session[session_id].append(trace)

    for session_id, session_traces in by_session.items():
        is_temp = str(session_id).startswith('session-')
        color = Colors.MAGENTA if is_temp else Colors.GREEN

        print(f"\n{color}{'📋' if is_temp else '✅'} Session: {session_id}{Colors.RESET}")
        print(f"  {'─' * 70}")

        for trace in session_traces:
            step = trace.get('step', 'Unknown')
            seq = trace.get('sequence', '?')
            ctx = trace.get('context', {})

            # Format step name
            step_display = step.replace('Entry', ' →').replace('Complete', ' ✓').replace(':', ' ')

            # Add relevant context
            extra = []
            if 'sessionInList' in ctx:
                extra.append(f"in_list={ctx['sessionInList']}")
            if 'sessionsAfter' in ctx:
                extra.append(f"count={ctx['sessionsAfter']}")
            if 'sessionIdsAfter' in ctx:
                ids = ctx['sessionIdsAfter']
                if len(ids) <= 5:
                    extra.append(f"ids={ids}")
                else:
                    extra.append(f"ids=[{len(ids)} sessions]")
            if 'oldSessionFound' in ctx:
                found = ctx['oldSessionFound']
                extra.append(f"{Colors.RED if not found else Colors.GREEN}found={found}{Colors.RESET}")

            extra_str = f"  ({', '.join(extra)})" if extra else ""

            print(f"    #{seq} {step_display:50s}{extra_str}")


def print_report(traces: list[dict], all_traces: list[dict] = None, output_file: str = None):
    """Generate and print analysis report."""

    # Filter to SessionLifecycleDebug traces
    sl_traces = filter_session_lifecycle_traces(traces)

    report = []

    def add_line(text=""):
        report.append(text)
        print(text)

    add_line("=" * 80)
    add_line(f"{Colors.BOLD}SESSION LIFECYCLE DEBUG TRACE ANALYSIS{Colors.RESET}")
    add_line(f"Generated: {datetime.now().isoformat()}")
    add_line(f"Total Traces: {len(traces)}")
    add_line(f"SessionLifecycleDebug Traces: {len(sl_traces)}")
    add_line("=" * 80)

    if not sl_traces:
        add_line(f"\n{Colors.YELLOW}⚠️  No SessionLifecycleDebug traces found!{Colors.RESET}")
        add_line("Make sure the frontend code with SessionLifecycleDebug traces is loaded.")
        add_line("Then: 1) Create a new session, 2) Send a message, 3) Wait for streaming to complete")
        return

    # Session count summary
    add_line(f"\n{Colors.BOLD}📊 SESSION SUMMARY{Colors.RESET}")
    add_line("-" * 40)

    sessions = set()
    temp_sessions = set()
    backend_sessions = set()

    for trace in sl_traces:
        ctx = trace.get('context', {})
        if ctx.get('tempSessionId'):
            sessions.add(ctx['tempSessionId'])
            temp_sessions.add(ctx['tempSessionId'])
        if ctx.get('backendSessionId'):
            sessions.add(ctx['backendSessionId'])
            backend_sessions.add(ctx['backendSessionId'])
        if ctx.get('sessionId'):
            sessions.add(ctx['sessionId'])

    add_line(f"  Total sessions tracked: {len(sessions)}")
    add_line(f"  Temp sessions: {len(temp_sessions)}")
    add_line(f"  Backend sessions: {len(backend_sessions)}")

    # Trace distribution by step
    add_line(f"\n{Colors.BOLD}📁 TRACE DISTRIBUTION BY STEP{Colors.RESET}")
    add_line("-" * 40)

    step_counts = defaultdict(int)
    for trace in sl_traces:
        step = trace.get('step', 'Unknown')
        step_counts[step] += 1

    for step, count in sorted(step_counts.items(), key=lambda x: -x[1]):
        add_line(f"  {step}: {count}")

    # Print timeline
    print_session_timeline(sl_traces)

    # Print diagnostic summary
    print_diagnostic_summary(sl_traces)

    # CRITICAL: Analyze for issues
    add_line(f"\n{Colors.BOLD}{Colors.RED}🔍 CRITICAL ANALYSIS - DUPLICATE SESSION BUG{Colors.RESET}")
    add_line("-" * 80)

    issues = []
    issues.extend(analyze_temp_session_flow(sl_traces))
    issues.extend(analyze_load_from_backend_timing(sl_traces))
    issues.extend(analyze_session_counts(sl_traces))

    # Categorize issues
    critical = [i for i in issues if i.get('severity') == 'CRITICAL']
    high = [i for i in issues if i.get('severity') == 'HIGH']
    medium = [i for i in issues if i.get('severity') == 'MEDIUM']

    add_line(f"\n  Issues Found:")
    add_line(f"    {Colors.RED}{Colors.BOLD}CRITICAL: {len(critical)}{Colors.RESET}")
    add_line(f"    {Colors.YELLOW}{Colors.BOLD}HIGH: {len(high)}{Colors.RESET}")
    add_line(f"    {Colors.CYAN}MEDIUM: {len(medium)}{Colors.RESET}")

    if critical:
        add_line(f"\n{Colors.RED}{Colors.BOLD}  ❌ CRITICAL ISSUES (Root Cause Likely Here){Colors.RESET}")
        add_line("  " + "─" * 76)
        for issue in critical:
            add_line(f"\n  [{issue.get('type', 'unknown')}]")
            add_line(f"  Session: {issue.get('session', 'N/A')}")
            add_line(f"  Sequence: #{issue.get('sequence', 'N/A')}")
            add_line(f"  {Colors.RED}{issue['message']}{Colors.RESET}")

            if issue.get('details'):
                add_line(f"  Details:")
                for key, value in issue.get('details', {}).items():
                    add_line(f"    {key}: {value}")

    if high:
        add_line(f"\n{Colors.YELLOW}{Colors.BOLD}  ⚠️  HIGH SEVERITY ISSUES{Colors.RESET}")
        add_line("  " + "─" * 76)
        for issue in high:
            add_line(f"\n  [{issue.get('type', 'unknown')}]")
            add_line(f"  {Colors.YELLOW}{issue['message']}{Colors.RESET}")

    if medium:
        add_line(f"\n{Colors.CYAN}  📋 MEDIUM SEVERITY ISSUES{Colors.RESET}")
        add_line("  " + "─" * 76)
        for issue in medium[:5]:  # Limit display
            add_line(f"  - {issue['message']}")

    # Root cause hypothesis
    if critical:
        add_line(f"\n{Colors.BOLD}{Colors.MAGENTA}💡 ROOT CAUSE HYPOTHESIS{Colors.RESET}")
        add_line("-" * 80)

        # Check for specific patterns
        not_found_issues = [i for i in critical if i.get('type') == 'session_not_found']
        duplicate_issues = [i for i in critical if i.get('type') == 'duplicate_sessions']
        upsert_failed = [i for i in critical if i.get('type') == 'upsert_failed']

        if not_found_issues:
            add_line(f"\n  {Colors.MAGENTA}LIKELY ROOT CAUSE:{Colors.RESET}")
            add_line("  The temp session is NOT in the sessions list when replaceSessionById is called.")
            add_line("  This causes replaceSessionById to ADD the backend session (idx=-1)")
            add_line("  instead of REPLACING the temp session.")
            add_line("\n  Possible causes:")
            add_line("    1. loadFromBackend ran and cleared sessions before temp session was added")
            add_line("    2. upsertSession didn't actually add the session to the list")
            add_line("    3. Race condition between createNewSession and loadFromBackend")
            add_line("\n  Check the trace with 'replaceSessionByIdFindResult' step above.")
            add_line("  Look for: oldSessionFound=false, oldSessionIndex=-1")

        if duplicate_issues:
            add_line(f"\n  {Colors.MAGENTA}CONFIRMED BUG:{Colors.RESET}")
            add_line("  Both temp session AND backend session exist in the sessions list!")
            add_line("  This confirms the replace operation failed to replace.")

        if upsert_failed:
            add_line(f"\n  {Colors.MAGENTA}EARLIER FAILURE:{Colors.RESET}")
            add_line("  upsertSession failed to add the temp session to the sessions list.")
            add_line("  This is the root cause - check upsertSession implementation.")

    # Recommendations
    add_line(f"\n{Colors.BOLD}{Colors.GREEN}🔧 RECOMMENDED FIXES{Colors.RESET}")
    add_line("-" * 80)
    add_line("  1. Check if loadFromBackend runs BEFORE temp session is added")
    add_line("     - Look at useEffect timing in useAgentInteraction.ts")
    add_line("     - Consider debouncing loadFromBackend")
    add_line("\n  2. Verify upsertSession actually adds to sessions list")
    add_line("     - Check cognitiveHubStore.ts upsertSession implementation")
    add_line("     - Look for: sessions: [session, ...state.sessions.filter(...)]")
    add_line("\n  3. Add defensive check in replaceSessionById")
    add_line("     - If oldSession not found, log warning with full state")
    add_line("     - Consider searching activeSession as fallback")
    add_line("\n  4. Consider using flags to prevent loadFromBackend when temp session exists")

    add_line("\n" + "=" * 80)

    # Save report if output file specified
    if output_file:
        # Strip ANSI codes for file output
        clean_report = [line.replace(Colors.RESET, '').replace(Colors.RED, '').replace(Colors.GREEN, '').replace(Colors.YELLOW, '').replace(Colors.BLUE, '').replace(Colors.MAGENTA, '').replace(Colors.CYAN, '').replace(Colors.BOLD, '') for line in report]
        with open(output_file, 'w') as f:
            f.write("\n".join(clean_report))
        print(f"\n{Colors.GREEN}Report saved to: {output_file}{Colors.RESET}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Analyze SessionLifecycleDebug traces')
    parser.add_argument('filepath', nargs='?', help='Path to traces JSON file')
    parser.add_argument('--fetch', action='store_true', help='Fetch traces from API')
    parser.add_argument('--limit', type=int, default=1000, help='Number of traces to fetch')
    parser.add_argument('--filter', type=str, help='Filter by flow name')
    parser.add_argument('--output', type=str, help='Save report to file')

    args = parser.parse_args()

    if args.fetch:
        traces = fetch_traces(args.limit)
    elif args.filepath:
        traces = load_traces(args.filepath)
    else:
        print(__doc__)
        print("\nError: Please provide a trace file path or use --fetch")
        print("Example: python3 analyze_session_lifecycle_traces.py --fetch --limit 1000")
        sys.exit(1)

    # Optional additional filtering
    if args.filter:
        traces = [t for t in traces if t.get('flow') == args.filter]

    print_report(traces, output_file=args.output)


if __name__ == '__main__':
    main()
