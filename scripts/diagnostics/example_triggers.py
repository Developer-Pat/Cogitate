#!/usr/bin/env python3
"""
Example triggers for testing and demonstration.

This script creates example triggers to demonstrate the event-driven trigger system:
1. A scheduled trigger that runs every 5 minutes (for testing)
2. A webhook trigger for custom events

Usage:
    cd /path/to/cogitate
    uv run --with requests scripts/example_triggers.py
    
    # Or from backend directory:
    cd backend && uv run ../scripts/example_triggers.py

Prerequisites:
    - Application must be running
    - At least one workflow template must exist
"""

import requests
import json
import sys
import os
from typing import Optional

# Determine base URL from environment or default
BASE_URL = os.environ.get("COGITATE_API_URL", "http://localhost:8000/api/v1")


def check_api_health() -> bool:
    """Check if the API is healthy."""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def get_available_workflows() -> list:
    """Get list of available workflow templates."""
    try:
        response = requests.get(f"{BASE_URL}/workflows/templates", timeout=5)
        if response.status_code == 200:
            templates = response.json()
            return [t["id"] for t in templates]
    except Exception as e:
        print(f"⚠️  Could not fetch workflows: {e}")
    
    # Return some common template IDs as fallback
    return ["agent-hello", "agent-summary", "agent-code-review"]


def create_scheduled_trigger(workflow_id: str, cron: str, timezone: str = "UTC") -> Optional[dict]:
    """
    Create a scheduled trigger.
    
    Args:
        workflow_id: ID of workflow to execute
        cron: Cron expression
        timezone: Timezone for schedule
    
    Returns:
        Trigger info if successful, None otherwise
    """
    trigger_id = f"example-schedule-{workflow_id}"
    
    payload = {
        "id": trigger_id,
        "workflow_id": workflow_id,
        "trigger_type": "schedule",
        "config": {
            "cron": cron,
            "timezone": timezone,
            "enabled": True
        },
        "name": f"Example Schedule: {workflow_id}",
        "description": f"Example scheduled trigger for {workflow_id} (cron: {cron})"
    }
    
    try:
        # Check if trigger already exists
        response = requests.get(f"{BASE_URL}/triggers/{trigger_id}", timeout=5)
        if response.status_code == 200:
            print(f"ℹ️  Trigger {trigger_id} already exists, updating...")
            response = requests.put(
                f"{BASE_URL}/triggers/{trigger_id}",
                json=payload,
                timeout=5
            )
        else:
            response = requests.post(
                f"{BASE_URL}/triggers",
                json=payload,
                timeout=5
            )
        
        if response.status_code in [200, 201]:
            result = response.json()
            print(f"✅ Created scheduled trigger: {trigger_id}")
            print(f"   Workflow: {workflow_id}")
            print(f"   Cron: {cron}")
            print(f"   Timezone: {timezone}")
            return result
        else:
            print(f"❌ Failed to create trigger: {response.status_code}")
            print(f"   {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error creating scheduled trigger: {e}")
        return None


def create_webhook_trigger(workflow_id: str, endpoint: str) -> Optional[dict]:
    """
    Create a webhook trigger.
    
    Args:
        workflow_id: ID of workflow to execute
        endpoint: Webhook endpoint path
    
    Returns:
        Trigger info if successful, None otherwise
    """
    trigger_id = f"example-webhook-{endpoint.strip('/').replace('/', '-')}"
    
    payload = {
        "id": trigger_id,
        "workflow_id": workflow_id,
        "trigger_type": "webhook",
        "config": {
            "endpoint": endpoint,
            "allowed_events": ["test", "deploy", "custom"],
            "headers": {}
        },
        "name": f"Example Webhook: {endpoint}",
        "description": f"Example webhook trigger at {endpoint}"
    }
    
    try:
        # Check if trigger already exists
        response = requests.get(f"{BASE_URL}/triggers/{trigger_id}", timeout=5)
        if response.status_code == 200:
            print(f"ℹ️  Trigger {trigger_id} already exists, updating...")
            response = requests.put(
                f"{BASE_URL}/triggers/{trigger_id}",
                json=payload,
                timeout=5
            )
        else:
            response = requests.post(
                f"{BASE_URL}/triggers",
                json=payload,
                timeout=5
            )
        
        if response.status_code in [200, 201]:
            result = response.json()
            print(f"✅ Created webhook trigger: {trigger_id}")
            print(f"   Workflow: {workflow_id}")
            print(f"   Endpoint: {endpoint}")
            print(f"   Allowed events: test, deploy, custom")
            return result
        else:
            print(f"❌ Failed to create trigger: {response.status_code}")
            print(f"   {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error creating webhook trigger: {e}")
        return None


def test_webhook_trigger(endpoint: str) -> dict:
    """
    Test a webhook trigger by sending a test event.
    
    Args:
        endpoint: Webhook endpoint path
    
    Returns:
        Response from webhook
    """
    payload = {
        "event": "test",
        "message": "This is a test webhook event",
        "data": {
            "test": True,
            "timestamp": "2026-03-30T12:00:00Z"
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Custom-Event": "test"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/webhooks{endpoint}",
            json=payload,
            headers=headers,
            timeout=10
        )
        
        return {
            "status_code": response.status_code,
            "response": response.json() if response.content else {}
        }
        
    except Exception as e:
        return {
            "status_code": 0,
            "error": str(e)
        }


def list_all_triggers():
    """List all triggers."""
    try:
        response = requests.get(f"{BASE_URL}/triggers", timeout=5)
        if response.status_code == 200:
            triggers = response.json()
            print(f"\n📋 All Triggers ({len(triggers)} total):")
            print("-" * 60)
            
            for trigger in triggers:
                status = "✅" if trigger.get("is_active", False) else "⏸️"
                trigger_type = trigger.get("trigger_type", "unknown")
                print(f"{status} {trigger['id']}")
                print(f"   Type: {trigger_type}")
                print(f"   Workflow: {trigger['workflow_id']}")
                
                if trigger_type == "schedule":
                    config = trigger.get("config", {})
                    print(f"   Cron: {config.get('cron', 'N/A')}")
                    print(f"   Timezone: {config.get('timezone', 'N/A')}")
                elif trigger_type == "webhook":
                    config = trigger.get("config", {})
                    print(f"   Endpoint: {config.get('endpoint', 'N/A')}")
                
                print()
            
            return triggers
    except Exception as e:
        print(f"❌ Error listing triggers: {e}")
    
    return []


def list_schedules():
    """List all scheduled triggers with next run times."""
    try:
        response = requests.get(f"{BASE_URL}/triggers/schedules/list", timeout=5)
        if response.status_code == 200:
            schedules = response.json()
            print(f"\n⏰ Scheduled Triggers ({len(schedules)} total):")
            print("-" * 60)
            
            for schedule in schedules:
                status = "⏸️" if schedule.get("paused", False) else "▶️"
                print(f"{status} {schedule['trigger_id']}")
                print(f"   Workflow: {schedule['workflow_id']}")
                print(f"   Cron: {schedule['cron']}")
                print(f"   Next run: {schedule.get('next_run_time', 'N/A')}")
                print(f"   Timezone: {schedule.get('timezone', 'UTC')}")
                print()
            
            return schedules
    except Exception as e:
        print(f"❌ Error listing schedules: {e}")
    
    return []


def list_webhook_endpoints():
    """List all webhook endpoints."""
    try:
        response = requests.get(f"{BASE_URL}/triggers/webhooks/endpoints", timeout=5)
        if response.status_code == 200:
            endpoints = response.json()
            print(f"\n🔗 Webhook Endpoints ({len(endpoints)} total):")
            print("-" * 60)
            
            for endpoint in endpoints:
                print(f"POST {endpoint['endpoint']}")
                print(f"   Trigger: {endpoint['trigger_id']}")
                print(f"   Workflow: {endpoint['workflow_id']}")
                print(f"   Allowed events: {', '.join(endpoint.get('allowed_events', []))}")
                print(f"   Requires signature: {'Yes' if endpoint.get('requires_signature') else 'No'}")
                print()
            
            return endpoints
    except Exception as e:
        print(f"❌ Error listing webhook endpoints: {e}")
    
    return []


def cleanup_example_triggers():
    """Delete all example triggers created by this script."""
    try:
        response = requests.get(f"{BASE_URL}/triggers", timeout=5)
        if response.status_code == 200:
            triggers = response.json()
            
            example_triggers = [
                t for t in triggers 
                if t.get("id", "").startswith("example-")
            ]
            
            if not example_triggers:
                print("ℹ️  No example triggers found to cleanup")
                return
            
            print(f"🧹 Cleaning up {len(example_triggers)} example triggers...")
            
            for trigger in example_triggers:
                trigger_id = trigger["id"]
                response = requests.delete(
                    f"{BASE_URL}/triggers/{trigger_id}",
                    timeout=5
                )
                if response.status_code == 200:
                    print(f"✅ Deleted: {trigger_id}")
                else:
                    print(f"⚠️  Failed to delete {trigger_id}: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")


def main():
    """Main function."""
    print("=" * 60)
    print("Example Triggers Setup Script")
    print("=" * 60)
    print()
    
    # Check API health
    print("🔍 Checking API health...")
    if not check_api_health():
        print("❌ API is not responding. Please start the application first.")
        print(f"   Expected at: {BASE_URL}")
        sys.exit(1)
    print("✅ API is healthy")
    print()
    
    # Get available workflows
    print("📋 Fetching available workflows...")
    workflows = get_available_workflows()
    print(f"   Found {len(workflows)} workflows: {', '.join(workflows[:5])}")
    print()
    
    # Select workflow for examples
    workflow_id = workflows[0] if workflows else "agent-hello"
    print(f"🎯 Using workflow '{workflow_id}' for examples")
    print()
    
    # Create example triggers
    print("=" * 60)
    print("Creating Example Triggers")
    print("=" * 60)
    print()
    
    # Example 1: Scheduled trigger (every 5 minutes for testing)
    print("1️⃣  Creating scheduled trigger (every 5 minutes)...")
    create_scheduled_trigger(
        workflow_id=workflow_id,
        cron="*/5 * * * *",  # Every 5 minutes
        timezone="UTC"
    )
    print()
    
    # Example 2: Scheduled trigger (daily at 9 AM)
    print("2️⃣  Creating scheduled trigger (daily at 9 AM)...")
    create_scheduled_trigger(
        workflow_id=workflow_id,
        cron="0 9 * * *",  # Daily at 9 AM
        timezone="America/New_York"
    )
    print()
    
    # Example 3: Webhook trigger
    print("3️⃣  Creating webhook trigger...")
    create_webhook_trigger(
        workflow_id=workflow_id,
        endpoint="/example-deploy"
    )
    print()
    
    # Example 4: Another webhook trigger
    print("4️⃣  Creating another webhook trigger...")
    create_webhook_trigger(
        workflow_id=workflow_id,
        endpoint="/example-custom"
    )
    print()
    
    # List all triggers
    print("=" * 60)
    print("Current Triggers")
    print("=" * 60)
    list_all_triggers()
    
    # List schedules
    list_schedules()
    
    # List webhook endpoints
    list_webhook_endpoints()
    
    # Test webhook
    print("=" * 60)
    print("Testing Webhook")
    print("=" * 60)
    print()
    print("🧪 Sending test webhook to /example-deploy...")
    result = test_webhook_trigger("/example-deploy")
    
    if result.get("status_code") == 200:
        print(f"✅ Webhook test successful!")
        print(f"   Response: {json.dumps(result.get('response', {}), indent=2)}")
    else:
        print(f"⚠️  Webhook test result: {result}")
    print()
    
    # Summary
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print()
    print("✅ Created 2 scheduled triggers:")
    print("   - Every 5 minutes (for testing)")
    print("   - Daily at 9 AM EST")
    print()
    print("✅ Created 2 webhook triggers:")
    print("   - POST /api/v1/webhooks/example-deploy")
    print("   - POST /api/v1/webhooks/example-custom")
    print()
    print("📝 To test webhooks:")
    print(f"   curl -X POST {BASE_URL}/webhooks/example-deploy \\")
    print("     -H 'Content-Type: application/json' \\")
    print("     -H 'X-Custom-Event: test' \\")
    print("     -d '{\"event\": \"test\", \"message\": \"Hello!\"}'")
    print()
    print("🧹 To cleanup example triggers:")
    print(f"   uv run scripts/example_triggers.py cleanup")
    print()
    
    return 0


if __name__ == "__main__":
    # Handle cleanup argument
    if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
        print("🧹 Cleaning up example triggers...")
        cleanup_example_triggers()
        print("✅ Cleanup complete")
        sys.exit(0)
    
    sys.exit(main())
