"""
Log service for database operations.

Provides high-level business logic for log management.
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import Log

logger = logging.getLogger(__name__)


class LogService:
    """
    Service for log database operations.
    
    Provides business logic for log management.
    """
    
    def __init__(self, db: AsyncSession):
        """
        Initialize log service.
        
        Args:
            db: Async database session
        """
        self.db = db
    
    async def create_frontend_log(
        self,
        timestamp: str,
        level: str,
        source: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        user_agent: Optional[str] = None,
        url: Optional[str] = None,
        session_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> Log:
        """
        Create a new frontend log entry.
        
        Args:
            timestamp: Log timestamp
            level: Log level
            source: Component/hook name
            message: Log message
            context: Additional context data
            user_agent: Browser user agent
            url: Page URL
            session_id: Session identifier
            trace_id: Trace identifier
            
        Returns:
            Created log entry
        """
        log = Log(
            timestamp=timestamp,
            level=level.upper(),
            source=source,
            message=message,
            context=context,
            user_agent=user_agent,
            url=url,
            session_id=session_id,
            trace_id=trace_id,
            log_type="frontend"
        )
        
        self.db.add(log)
        await self.db.flush()
        await self.db.refresh(log)
        
        logger.debug(f"Created frontend log: {log.id} - {level} - {source} - {message}")
        
        return log
    
    async def create_backend_log(
        self,
        timestamp: str,
        level: str,
        source: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None
    ) -> Log:
        """
        Create a new backend log entry.
        
        Args:
            timestamp: Log timestamp
            level: Log level
            source: Module name
            message: Log message
            context: Additional context data
            trace_id: Trace identifier
            
        Returns:
            Created log entry
        """
        log = Log(
            timestamp=timestamp,
            level=level.upper(),
            source=source,
            message=message,
            context=context,
            trace_id=trace_id,
            log_type="backend"
        )
        
        self.db.add(log)
        await self.db.flush()
        await self.db.refresh(log)
        
        logger.debug(f"Created backend log: {log.id} - {level} - {source} - {message}")
        
        return log
    
    async def get_log_by_id(self, log_id: int) -> Optional[Log]:
        """
        Get log entry by ID.
        
        Args:
            log_id: Log ID
            
        Returns:
            Log entry if found, None otherwise
        """
        query = select(Log).where(Log.id == log_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_logs(
        self,
        skip: int = 0,
        limit: int = 50,
        level: Optional[str] = None,
        source: Optional[str] = None,
        from_time: Optional[str] = None,
        to_time: Optional[str] = None,
        search: Optional[str] = None,
        session_id: Optional[str] = None,
        log_type: Optional[str] = None
    ) -> Tuple[List[Log], int]:
        """
        Get logs with filtering and pagination.
        
        Args:
            skip: Number of records to skip
            limit: Maximum records to return
            level: Filter by log level
            source: Filter by source
            from_time: Start time filter (ISO 8601)
            to_time: End time filter (ISO 8601)
            search: Full-text search in message
            session_id: Filter by session ID
            log_type: Filter by log type (frontend/backend)
            
        Returns:
            Tuple of (logs list, total count)
        """
        # Build filter conditions
        conditions = []
        
        if level:
            conditions.append(Log.level == level.upper())
        
        if source:
            conditions.append(Log.source.ilike(f"%{source}%"))
        
        if from_time:
            try:
                from_dt = datetime.fromisoformat(from_time.replace('Z', '+00:00'))
                conditions.append(Log.timestamp >= from_dt.isoformat())
            except ValueError:
                logger.warning(f"Invalid from_time format: {from_time}")
        
        if to_time:
            try:
                to_dt = datetime.fromisoformat(to_time.replace('Z', '+00:00'))
                conditions.append(Log.timestamp <= to_dt.isoformat())
            except ValueError:
                logger.warning(f"Invalid to_time format: {to_time}")
        
        if search:
            conditions.append(Log.message.ilike(f"%{search}%"))
        
        if session_id:
            conditions.append(Log.session_id == session_id)
        
        if log_type:
            conditions.append(Log.log_type == log_type)
        
        # Get total count
        count_query = select(func.count()).select_from(Log)
        if conditions:
            count_query = count_query.where(and_(*conditions))
        
        total = await self.db.scalar(count_query) or 0
        
        # Get logs with filters
        query = select(Log)
        if conditions:
            query = query.where(and_(*conditions))
        
        # Order by timestamp descending (newest first)
        query = query.order_by(Log.timestamp.desc())
        
        # Apply pagination
        query = query.offset(skip).limit(limit)
        
        result = await self.db.execute(query)
        logs = list(result.scalars().all())
        
        return logs, total
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get log statistics.
        
        Returns:
            Dictionary with log statistics
        """
        # Total count
        total_query = select(func.count()).select_from(Log)
        total = await self.db.scalar(total_query) or 0
        
        # Count by level
        level_query = select(Log.level, func.count()).group_by(Log.level)
        level_result = await self.db.execute(level_query)
        by_level = {level: count for level, count in level_result.all()}
        
        # Count by source
        source_query = select(Log.source, func.count()).group_by(Log.source)
        source_result = await self.db.execute(source_query)
        by_source = {source: count for source, count in source_result.all()}
        
        # Count by type
        type_query = select(Log.log_type, func.count()).group_by(Log.log_type)
        type_result = await self.db.execute(type_query)
        by_type = {log_type: count for log_type, count in type_result.all()}
        
        # Recent activity (last 100 logs)
        recent_query = select(func.count()).select_from(Log).order_by(Log.timestamp.desc()).limit(100)
        recent_activity = await self.db.scalar(recent_query) or 0
        
        return {
            "total": total,
            "by_level": by_level,
            "by_source": by_source,
            "recent_activity": recent_activity,
            "frontend_logs": by_type.get("frontend", 0),
            "backend_logs": by_type.get("backend", 0),
        }
    
    async def get_sources(self) -> List[str]:
        """
        Get all unique log sources.
        
        Returns:
            List of unique sources
        """
        query = select(Log.source).distinct()
        result = await self.db.execute(query)
        return [row[0] for row in result.all()]
    
    async def delete_old_logs(self, days: int = 30) -> int:
        """
        Delete logs older than specified days.
        
        Args:
            days: Number of days to retain
            
        Returns:
            Number of logs deleted
        """
        from datetime import timedelta
        
        cutoff = datetime.now() - timedelta(days=days)
        query = select(Log).where(Log.timestamp < cutoff.isoformat())
        result = await self.db.execute(query)
        old_logs = result.scalars().all()
        
        deleted_count = len(old_logs)
        for log in old_logs:
            await self.db.delete(log)
        
        await self.db.flush()
        
        logger.info(f"Deleted {deleted_count} logs older than {days} days")
        
        return deleted_count
