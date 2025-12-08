"""
Redis State Management for Telegram Dispatch Bot

Provides persistent storage for ORDER STATE using Upstash Redis.
Automatically serializes datetime objects and complex data structures.

Environment Variables Required:
- UPSTASH_REDIS_REST_URL: Redis REST API URL
- UPSTASH_REDIS_REST_TOKEN: Redis authentication token
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import redis

logger = logging.getLogger(__name__)

# Redis connection (initialized on first use)
_redis_client = None

def get_redis_client():
    """Get or create Redis client instance."""
    global _redis_client
    
    if _redis_client is None:
        redis_url = os.environ.get("UPSTASH_REDIS_REST_URL")
        redis_token = os.environ.get("UPSTASH_REDIS_REST_TOKEN")
        
        if not redis_url or not redis_token:
            logger.warning("Redis credentials not found - persistence disabled")
            return None
        
        try:
            _redis_client = redis.Redis(
                host=redis_url.replace("https://", "").replace("http://", ""),
                port=6379,
                password=redis_token,
                ssl=True,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            # Test connection
            _redis_client.ping()
            logger.info("✅ Redis connection established")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            _redis_client = None
    
    return _redis_client


def serialize_order(order_data: Dict[str, Any]) -> str:
    """
    Serialize order data to JSON string.
    Converts datetime objects to ISO format strings.
    """
    serializable = {}
    
    for key, value in order_data.items():
        if isinstance(value, datetime):
            serializable[key] = value.isoformat()
        elif isinstance(value, list):
            # Handle status_history with datetime timestamps
            serializable_list = []
            for item in value:
                if isinstance(item, dict):
                    serializable_item = {}
                    for k, v in item.items():
                        serializable_item[k] = v.isoformat() if isinstance(v, datetime) else v
                    serializable_list.append(serializable_item)
                else:
                    serializable_list.append(item)
            serializable[key] = serializable_list
        else:
            serializable[key] = value
    
    return json.dumps(serializable, ensure_ascii=False)


def deserialize_order(json_str: str) -> Dict[str, Any]:
    """
    Deserialize order data from JSON string.
    Converts ISO format strings back to datetime objects.
    """
    order_data = json.loads(json_str)
    
    # Convert ISO strings back to datetime objects
    for key, value in order_data.items():
        if isinstance(value, str) and "T" in value:
            try:
                order_data[key] = datetime.fromisoformat(value)
            except:
                pass  # Not a datetime, leave as string
        elif isinstance(value, list):
            # Handle status_history with datetime timestamps
            for item in value:
                if isinstance(item, dict):
                    for k, v in item.items():
                        if isinstance(v, str) and "T" in v:
                            try:
                                item[k] = datetime.fromisoformat(v)
                            except:
                                pass
    
    return order_data


def redis_save_order(order_id: str, order_data: Dict[str, Any]) -> bool:
    """
    Save single order to Redis.
    
    Args:
        order_id: Order identifier
        order_data: Full order dictionary
        
    Returns:
        True if saved successfully, False otherwise
    """
    client = get_redis_client()
    if not client:
        return False
    
    try:
        key = f"order:{order_id}"
        serialized = serialize_order(order_data)
        client.set(key, serialized)
        # Set expiration: 7 days (orders older than week auto-deleted)
        client.expire(key, 604800)
        return True
    except Exception as e:
        logger.error(f"Failed to save order {order_id} to Redis: {e}")
        return False


def redis_get_order(order_id: str) -> Optional[Dict[str, Any]]:
    """
    Get single order from Redis.
    
    Args:
        order_id: Order identifier
        
    Returns:
        Order data dict or None if not found
    """
    client = get_redis_client()
    if not client:
        return None
    
    try:
        key = f"order:{order_id}"
        data = client.get(key)
        if data:
            return deserialize_order(data)
        return None
    except Exception as e:
        logger.error(f"Failed to get order {order_id} from Redis: {e}")
        return None


def redis_delete_order(order_id: str) -> bool:
    """
    Delete single order from Redis.
    
    Args:
        order_id: Order identifier
        
    Returns:
        True if deleted successfully, False otherwise
    """
    client = get_redis_client()
    if not client:
        return False
    
    try:
        key = f"order:{order_id}"
        client.delete(key)
        return True
    except Exception as e:
        logger.error(f"Failed to delete order {order_id} from Redis: {e}")
        return False


def redis_get_all_orders() -> Dict[str, Dict[str, Any]]:
    """
    Get all orders from Redis.
    
    Returns:
        Dictionary mapping order_id -> order_data
    """
    client = get_redis_client()
    if not client:
        return {}
    
    try:
        # Get all keys matching "order:*"
        keys = client.keys("order:*")
        orders = {}
        
        for key in keys:
            order_id = key.replace("order:", "")
            data = client.get(key)
            if data:
                orders[order_id] = deserialize_order(data)
        
        return orders
    except Exception as e:
        logger.error(f"Failed to get all orders from Redis: {e}")
        return {}


def redis_get_order_count() -> int:
    """
    Get count of orders in Redis.
    
    Returns:
        Number of orders stored
    """
    client = get_redis_client()
    if not client:
        return 0
    
    try:
        keys = client.keys("order:*")
        return len(keys)
    except Exception as e:
        logger.error(f"Failed to get order count from Redis: {e}")
        return 0


def redis_cleanup_old_orders(days_to_keep: int = 2) -> int:
    """
    Delete orders older than specified days.
    Keeps orders from today and the specified number of previous days.
    
    Args:
        days_to_keep: Number of days to keep (default 2, keeps today + 2 previous days)
        
    Returns:
        Number of orders deleted
    """
    client = get_redis_client()
    if not client:
        logger.warning("Redis client not available - cleanup skipped")
        return 0
    
    try:
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        
        # Calculate cutoff date (beginning of day X days ago) - MUST be timezone-aware
        cutoff_date = datetime.now(ZoneInfo("Europe/Berlin")).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_to_keep)
        
        logger.info(f"Starting Redis cleanup: deleting orders older than {cutoff_date.strftime('%Y-%m-%d')}")
        
        # Get all order keys
        keys = client.keys("order:*")
        deleted_count = 0
        
        for key in keys:
            try:
                # Get order data
                data = client.get(key)
                if data:
                    order = deserialize_order(data)
                    
                    # Check if order has created_at field
                    if "created_at" in order and isinstance(order["created_at"], datetime):
                        # Delete if older than cutoff
                        if order["created_at"] < cutoff_date:
                            client.delete(key)
                            deleted_count += 1
                            order_id = key.replace("order:", "")
                            logger.info(f"Deleted old order {order_id} (created: {order['created_at'].strftime('%Y-%m-%d %H:%M')})")
            except Exception as e:
                logger.error(f"Error processing key {key} during cleanup: {e}")
                continue
        
        logger.info(f"✅ Redis cleanup complete: deleted {deleted_count} orders, {len(keys) - deleted_count} orders remaining")
        return deleted_count
        
    except Exception as e:
        logger.error(f"Failed to cleanup old orders: {e}")
        return 0
