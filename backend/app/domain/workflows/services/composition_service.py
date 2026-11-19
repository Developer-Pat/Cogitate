"""
Workflow composition service layer.

Provides business logic for:
- Creating and managing workflow compositions
- Executing composition workflows
- Tracking composition execution history

Features:
- Composition CRUD operations
- Composition execution with state management
- Input/output mapping between workflows
- Comprehensive logging for diagnostics
"""

import logging
import sqlite3
import json
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, UTC


from app.domain.workflows.schemas.composition_config import (
    WorkflowComposition,
    CompositionExecutionResult,
)

logger = logging.getLogger(__name__)

# Database path - project root
from app.core.config import Paths, get_settings
from pathlib import Path
DB_PATH = Paths.from_settings(get_settings()).shared_db


class CompositionService:
    """
    Service for managing workflow compositions.
    
    This service handles:
    1. Loading composition configs from database
    2. Creating new compositions
    3. Updating composition configs
    4. Deleting compositions
    5. Executing compositions
    6. Tracking execution history
    """
    
    @property
    def db_path(self) -> Path:
        """The shared database, resolved on EVERY read.

        This was a module-level constant captured at import. That cannot follow
        a redirected installation: under test the harness points DATABASE_URL at
        a copy of a migrated DB, and a path bound at import (or in __init__)
        keeps naming the original — producing "no such table" against the wrong
        file. The resolver was always correct; it was just applied too early.
        """
        from app.core.config import Paths, get_settings

        override: Path | None = getattr(self, "_db_path_override", None)
        if override is not None:
            return override
        return Paths.from_settings(get_settings()).shared_db

    @db_path.setter
    def db_path(self, value) -> None:
        """An explicit override — the test seam.

        Kept deliberately: tests point a service at their own database.
        The resolver above is the DEFAULT, not a cage.
        """
        self._db_path_override = value
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    # =========================================================================
    # CRUD Operations
    # =========================================================================
    
    def create_composition(self, config: WorkflowComposition) -> bool:
        """
        Create a new workflow composition.
        
        Args:
            config: Workflow composition configuration
            
        Returns:
            True if successful
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Serialize config to JSON
            config_json = config.model_dump_json()
            
            cursor.execute(
                """
                INSERT INTO workflow_compositions (
                    id, name, description, config_json, version, tags, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    config.id,
                    config.name,
                    config.description,
                    config_json,
                    config.version,
                    json.dumps(config.tags) if config.tags else None,
                )
            )
            conn.commit()
            
            logger.info(f"✅ Created composition: {config.id} ({config.name})")
            return True
            
        except sqlite3.IntegrityError as e:
            logger.error(f"❌ Composition already exists: {config.id} - {e}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Failed to create composition: {e}", exc_info=True)
            return False
            
        finally:
            conn.close()
    
    def get_composition(self, composition_id: str) -> Optional[WorkflowComposition]:
        """
        Get composition by ID.

        Args:
            composition_id: ID of composition to retrieve

        Returns:
            WorkflowComposition or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT * FROM workflow_compositions WHERE id = ?",
                (composition_id,)
            )
            row = cursor.fetchone()

            if row:
                row_dict = dict(row)
                
                # Parse tags from JSON string if needed
                tags = row_dict.get('tags')
                if isinstance(tags, str):
                    tags = json.loads(tags)
                elif tags is None:
                    tags = []
                
                # Parse config_json from JSON string if needed  
                config = row_dict.get('config_json')
                if isinstance(config, str):
                    config = json.loads(config)
                elif config is None:
                    config = {}
                
                # Reconstruct WorkflowComposition from individual columns
                # This ensures we get the latest values, not stale data from config_json
                logger.info(f"📄 Retrieved composition: {composition_id}")
                return WorkflowComposition(
                    id=row_dict['id'],
                    name=row_dict['name'],
                    description=row_dict.get('description', ''),
                    config=config,
                    version=row_dict.get('version', '1.0'),
                    tags=tags,
                    workflows=config.get('workflows', [])  # Workflows are only in config_json
                )
            else:
                logger.debug(f"📄 Composition not found: {composition_id}")
                return None

        finally:
            conn.close()
    
    def list_compositions(self, active_only: bool = True) -> List[WorkflowComposition]:
        """
        List all compositions.
        
        Args:
            active_only: If True, only return active compositions
            
        Returns:
            List of WorkflowComposition objects
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            if active_only:
                cursor.execute(
                    "SELECT * FROM workflow_compositions WHERE is_active = 1 ORDER BY name"
                )
            else:
                cursor.execute(
                    "SELECT * FROM workflow_compositions ORDER BY name"
                )
            
            compositions = []
            for row in cursor.fetchall():
                row_dict = dict(row)
                if isinstance(row_dict.get('config_json'), str):
                    config_dict = json.loads(row_dict['config_json'])
                else:
                    config_dict = row_dict.get('config_json', {})
                
                if isinstance(row_dict.get('tags'), str):
                    config_dict['tags'] = json.loads(row_dict['tags'])
                
                try:
                    comp = WorkflowComposition.model_validate(config_dict)
                    compositions.append(comp)
                except Exception as e:
                    logger.warning(f"⚠️  Invalid composition config {row_dict['id']}: {e}")
            
            logger.info(f"📋 Listed {len(compositions)} compositions")
            return compositions
            
        finally:
            conn.close()
    
    def update_composition(self, composition_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update composition configuration.
        
        Args:
            composition_id: ID of composition to update
            updates: Fields to update
            
        Returns:
            True if successful
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Build update query dynamically
            set_clauses = []
            values = []
            
            for field, value in updates.items():
                if field in ['id', 'created_at', 'updated_at']:
                    continue  # Skip immutable fields
                
                if field == 'config':
                    set_clauses.append("config_json = ?")
                    values.append(json.dumps(value) if isinstance(value, dict) else value)
                elif field == 'tags':
                    set_clauses.append("tags = ?")
                    values.append(json.dumps(value) if isinstance(value, list) else value)
                else:
                    set_clauses.append(f"{field} = ?")
                    values.append(value)
            
            if not set_clauses:
                logger.warning(f"⚠️  No valid fields to update for {composition_id}")
                return False
            
            set_clauses.append("updated_at = CURRENT_TIMESTAMP")
            values.append(composition_id)
            
            query = f"UPDATE workflow_compositions SET {', '.join(set_clauses)} WHERE id = ?"
            
            cursor.execute(query, values)
            conn.commit()
            
            if cursor.rowcount > 0:
                logger.info(f"✅ Updated composition: {composition_id}")
                return True
            else:
                logger.warning(f"⚠️  Composition not found: {composition_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to update composition: {e}", exc_info=True)
            return False
            
        finally:
            conn.close()
    
    def delete_composition(self, composition_id: str) -> bool:
        """
        Delete a composition (soft delete by setting is_active=0).
        
        Args:
            composition_id: ID of composition to delete
            
        Returns:
            True if successful
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "UPDATE workflow_compositions SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (composition_id,)
            )
            conn.commit()
            
            if cursor.rowcount > 0:
                logger.info(f"✅ Deleted composition: {composition_id}")
                return True
            else:
                logger.warning(f"⚠️  Composition not found: {composition_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to delete composition: {e}", exc_info=True)
            return False
            
        finally:
            conn.close()
    
    # =========================================================================
    # Execution
    # =========================================================================
    
    def execute_composition(
        self,
        composition_id: str,
        initial_input: Dict[str, Any],
        workflow_id: Optional[str] = None
    ) -> CompositionExecutionResult:
        """
        Execute a workflow composition.
        
        Args:
            composition_id: ID of composition to execute
            initial_input: Initial input data for the composition
            workflow_id: Optional custom workflow execution ID
            
        Returns:
            CompositionExecutionResult with execution results
        """
        from app.workflows.graphs.composition_graph import build_composition_graph
        
        started_at = datetime.now(UTC)
        
        # Load composition config
        config = self.get_composition(composition_id)
        if not config:
            return CompositionExecutionResult(
                composition_id=composition_id,
                status="error",
                error=f"Composition not found: {composition_id}",
                started_at=started_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            )
        
        logger.info(f"🚀 Executing composition: {config.name} ({config.id})")
        
        try:
            # Build composition graph
            graph = build_composition_graph(config)
            # Phase G: the builder returns a raw StateGraph — it must
            # be COMPILED before invoke() (this was a latent bug: the
            # facility existed but every execution failed with
            # "'StateGraph' object has no attribute 'invoke'").
            # Phase F: apply the composition's error contract via the
            # policy injector (composition = chain-family semantics).
            from app.workflows.error_handling.policy_injector import apply_kind_retry_policy
            apply_kind_retry_policy(graph, "chain")
            try:
                compiled_graph = graph.compile()
            except Exception as _compile_err:
                logger.error(f"❌ Composition graph compile failed: {_compile_err}", exc_info=True)
                return CompositionExecutionResult(
                    composition_id=composition_id,
                    status="error",
                    error=f"Composition compile failed: {_compile_err}",
                    started_at=started_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                )

            # Generate workflow execution ID
            execution_id = workflow_id or f"exec-{uuid.uuid4().hex[:12]}"
            
            # Prepare initial state
            initial_state: dict[str, Any] = {
                "messages": [],
                "workflow_id": execution_id,
                "template_id": f"composition-{composition_id}",
                "inputs": initial_input,
                "current_step": None,
                "execution_result": None,
                "outputs": {},
                "approval_required": False,
                "approval_status": None,
                "metadata": {
                    "workflow_id": execution_id,
                    "template_id": f"composition-{composition_id}",
                    "composition_id": composition_id,
                    "status": "running",
                },
                "tool_calls_history": [],
                "tool_loop_count": 0,
                "pending_tool_calls": None,
                "current_agent_step": None,
                "composition_execution_history": [],
            }
            
            # Execute graph
            logger.info(f"📤 Invoking composition graph with input: {initial_input}")
            result = compiled_graph.invoke(initial_state)  # type: ignore[attr-defined]
            
            completed_at = datetime.now(UTC)
            elapsed = (completed_at - started_at).total_seconds()
            
            # Check for errors
            outputs = result.get("outputs", {})
            if "error" in outputs:
                logger.error(f"❌ Composition execution failed: {outputs['error']}")
                return CompositionExecutionResult(
                    composition_id=composition_id,
                    status="error",
                    error=outputs.get("error"),
                    outputs=outputs,
                    started_at=started_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                    completed_at=completed_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                    elapsed_seconds=elapsed,
                )
            
            # Extract workflow results
            workflow_results = []
            for hist in result.get("composition_execution_history", []):
                workflow_results.append({
                    "workflow_id": hist.get("workflow_id"),
                    "order": hist.get("order"),
                    "status": hist.get("status"),
                })
            
            logger.info(f"✅ Composition completed successfully in {elapsed:.2f}s")
            
            return CompositionExecutionResult(
                composition_id=composition_id,
                status="completed",
                outputs=outputs,
                workflow_results=workflow_results,
                started_at=started_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                completed_at=completed_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                elapsed_seconds=elapsed,
            )
            
        except Exception as e:
            logger.error(f"❌ Composition execution failed: {e}", exc_info=True)
            completed_at = datetime.now(UTC)
            elapsed = (completed_at - started_at).total_seconds()
            
            return CompositionExecutionResult(
                composition_id=composition_id,
                status="error",
                error=str(e),
                started_at=started_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                completed_at=completed_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                elapsed_seconds=elapsed,
            )
