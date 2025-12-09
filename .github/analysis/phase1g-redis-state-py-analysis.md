# Phase 1G: redis_state.py Analysis

**File**: `redis_state.py`
**Total Lines**: 232
**Purpose**: Redis state persistence layer for ORDER STATE backup/restore

---

## File Overview

This module provides persistent storage for order data using Upstash Redis:
- Backup STATE to Redis after every order update
- Restore STATE from Redis after Render restart
- Automatic datetime serialization/deserialization
- 7-day auto-expiration for old orders
- Graceful degradation (app works without Redis)

**Critical Pattern**: Redis is a BACKUP system, not primary storage. In-memory STATE is source of truth.

---

## Imports & Dependencies

### Standard Library (Lines 13-16)
```python
import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
```

### Third-Party Library (Line 17)
```python
import redis
```

**Installation**: `redis` package in requirements.txt

---

## Module-Level State (Lines 20-21)

```python
_redis_client = None  # Global Redis connection (singleton)
```

**Pattern**: Lazy initialization - client created on first use

---

## Function Catalog (8 Functions)

### 1. `get_redis_client()` - Line 24
**Purpose**: Get or create Redis client instance (singleton pattern)

**Logic** (Lines 26-51):
1. Check if `_redis_client` already initialized
2. If None: Load credentials from environment
3. If credentials missing: Log warning, return None
4. Create Redis connection with SSL, timeouts
5. Test connection with `ping()`
6. If connection fails: Log error, return None
7. Store in `_redis_client` global
8. Return client

**Configuration** (Lines 37-45):
```python
_redis_client = redis.Redis(
    host=redis_url.replace("https://", "").replace("http://", ""),
    port=6379,
    password=redis_token,
    ssl=True,
    decode_responses=True,  # Auto-decode bytes to strings
    socket_timeout=5,
    socket_connect_timeout=5
)
```

**Environment Variables**:
- `UPSTASH_REDIS_REST_URL`: Redis server URL
- `UPSTASH_REDIS_REST_TOKEN`: Authentication token

**Graceful Degradation** (Lines 32-34, 48-50):
```python
if not redis_url or not redis_token:
    logger.warning("Redis credentials not found - persistence disabled")
    return None

except Exception as e:
    logger.error(f"Failed to connect to Redis: {e}")
    _redis_client = None
```

**Result**: App continues running without persistence if Redis unavailable

**Returns**: Redis client instance or None

**Usage**: Called by all Redis functions (save, get, delete, get_all)

---

### 2. `serialize_order(order_data)` - Line 56
**Purpose**: Convert order dict to JSON string (datetime → ISO format)

**Problem Solved**: JSON can't serialize datetime objects

**Logic** (Lines 63-81):
1. Create empty `serializable` dict
2. Iterate through order_data items
3. If value is datetime: Convert to `.isoformat()` string
4. If value is list: Check each item (handle status_history dicts)
5. If list item is dict: Convert any datetime values to ISO strings
6. Otherwise: Copy value as-is
7. Return JSON string

**Critical Datetime Fields** (Lines 64-66):
```python
if isinstance(value, datetime):
    serializable[key] = value.isoformat()
```

**Examples**:
- `created_at`: datetime → "2024-12-06T14:30:00+00:00"
- `requested_time`: "14:30" (already string, no conversion)
- `confirmed_times`: {"JS": "14:35"} (strings, no conversion)

**Status History Handling** (Lines 67-79):
```python
elif isinstance(value, list):
    serializable_list = []
    for item in value:
        if isinstance(item, dict):
            serializable_item = {}
            for k, v in item.items():
                # Convert datetime timestamps to ISO strings
                serializable_item[k] = v.isoformat() if isinstance(v, datetime) else v
            serializable_list.append(serializable_item)
        else:
            serializable_list.append(item)
    serializable[key] = serializable_list
```

**Why Needed**: status_history contains dicts with `timestamp` field (datetime)

**Example status_history**:
```python
# Before serialization
[
    {"type": "time_sent", "time": "14:30", "timestamp": datetime(2024, 12, 6, 14, 30)},
    {"type": "time_confirmed", "time": "14:35", "timestamp": datetime(2024, 12, 6, 14, 31)}
]

# After serialization
[
    {"type": "time_sent", "time": "14:30", "timestamp": "2024-12-06T14:30:00+00:00"},
    {"type": "time_confirmed", "time": "14:35", "timestamp": "2024-12-06T14:31:00+00:00"}
]
```

**Parameters**:
- `order_data`: Full order dictionary from STATE

**Returns**: JSON string (UTF-8, non-ASCII preserved via `ensure_ascii=False`)

**Usage**: Called by `redis_save_order()` before storing to Redis

---

### 3. `deserialize_order(json_str)` - Line 84
**Purpose**: Convert JSON string back to order dict (ISO string → datetime)

**Inverse Operation**: Reverses `serialize_order()`

**Logic** (Lines 90-109):
1. Parse JSON string to dict
2. Iterate through order_data items
3. If value is string with "T" (ISO format): Try converting to datetime
4. If value is list: Check each item (handle status_history)
5. If list item is dict: Try converting any ISO strings to datetime
6. Return reconstructed order dict

**Datetime Detection** (Lines 93-97):
```python
if isinstance(value, str) and "T" in value:
    try:
        order_data[key] = datetime.fromisoformat(value)
    except:
        pass  # Not a datetime, leave as string
```

**Heuristic**: If string contains "T", attempt datetime parsing

**Why "T"**: ISO 8601 format uses "T" as date/time separator: "2024-12-06T14:30:00"

**Status History Reconstruction** (Lines 98-107):
```python
elif isinstance(value, list):
    for item in value:
        if isinstance(item, dict):
            for k, v in item.items():
                if isinstance(v, str) and "T" in v:
                    try:
                        item[k] = datetime.fromisoformat(v)
                    except:
                        pass
```

**Parameters**:
- `json_str`: JSON string from Redis

**Returns**: Order dictionary with datetime objects restored

**Usage**: Called by `redis_get_order()` and `redis_get_all_orders()` after fetching from Redis

---

### 4. `redis_save_order(order_id, order_data)` - Line 112
**Purpose**: Save single order to Redis with 7-day expiration

**Logic** (Lines 124-135):
1. Get Redis client (returns None if unavailable)
2. If no client: Return False
3. Build key: `f"order:{order_id}"`
4. Serialize order data to JSON
5. Set key in Redis with `client.set()`
6. Set expiration: 604800 seconds (7 days)
7. Return True on success, False on error

**Key Format** (Line 125):
```python
key = f"order:{order_id}"
# Example: "order:5866" or "order:dishbee_02"
```

**Expiration** (Line 128):
```python
client.expire(key, 604800)  # 7 days in seconds
```

**Why 7 Days**: Orders older than a week are irrelevant (delivery long complete)

**Auto-Cleanup**: Redis automatically deletes expired keys (no manual cleanup needed)

**Error Handling** (Lines 129-132):
```python
except Exception as e:
    logger.error(f"Failed to save order {order_id} to Redis: {e}")
    return False
```

**Graceful Degradation**: App continues if Redis save fails (in-memory STATE unaffected)

**Parameters**:
- `order_id`: Order identifier
- `order_data`: Full order dictionary from STATE

**Returns**: Boolean (True = saved, False = failed or Redis unavailable)

**Usage**: Called from main.py after every STATE update (webhook, callback, status change)

---

### 5. `redis_get_order(order_id)` - Line 139
**Purpose**: Retrieve single order from Redis

**Logic** (Lines 151-161):
1. Get Redis client (returns None if unavailable)
2. If no client: Return None
3. Build key: `f"order:{order_id}"`
4. Get value from Redis with `client.get(key)`
5. If data exists: Deserialize and return
6. If not found: Return None
7. If error: Log error, return None

**Key Lookup** (Lines 154-157):
```python
key = f"order:{order_id}"
data = client.get(key)
if data:
    return deserialize_order(data)
return None
```

**Parameters**:
- `order_id`: Order identifier

**Returns**: Order dictionary or None (if not found or Redis unavailable)

**Usage**: Called during STATE restoration after Render restart (if in-memory STATE empty)

---

### 6. `redis_delete_order(order_id)` - Line 164
**Purpose**: Delete single order from Redis

**Logic** (Lines 176-186):
1. Get Redis client (returns None if unavailable)
2. If no client: Return False
3. Build key: `f"order:{order_id}"`
4. Delete key with `client.delete(key)`
5. Return True on success, False on error

**When Used**: Potentially after order delivery (to conserve Redis storage)

**Currently**: Not called in main.py (orders expire after 7 days automatically)

**Parameters**:
- `order_id`: Order identifier

**Returns**: Boolean (True = deleted, False = failed or Redis unavailable)

**Usage**: Available for manual cleanup or future features

---

### 7. `redis_get_all_orders()` - Line 187
**Purpose**: Retrieve all orders from Redis (STATE restoration)

**Logic** (Lines 197-211):
1. Get Redis client (returns None if unavailable)
2. If no client: Return empty dict
3. Get all keys matching pattern: `client.keys("order:*")`
4. For each key:
   - Extract order_id (remove "order:" prefix)
   - Get value from Redis
   - Deserialize to dict
   - Add to orders dict
5. Return orders dict
6. If error: Log error, return empty dict

**Key Pattern Matching** (Line 201):
```python
keys = client.keys("order:*")
# Returns: ["order:5866", "order:dishbee_02", "order:smoothr_123"]
```

**Order ID Extraction** (Line 205):
```python
order_id = key.replace("order:", "")
# "order:5866" → "5866"
```

**Returns**: Dictionary mapping `order_id` → `order_data` (same structure as STATE)

**Usage**: Called during app startup to restore STATE after Render restart

**Example**:
```python
{
    "5866": {"name": "dishbee #26", "vendors": ["JS"], ...},
    "dishbee_02": {"name": "dishbee #02", "vendors": ["LR"], ...},
}
```

---

### 8. `redis_get_order_count()` - Line 215
**Purpose**: Get count of orders in Redis (monitoring)

**Logic** (Lines 225-232):
1. Get Redis client (returns None if unavailable)
2. If no client: Return 0
3. Get all keys matching pattern: `client.keys("order:*")`
4. Return count: `len(keys)`
5. If error: Log error, return 0

**Returns**: Integer (number of orders stored in Redis)

**Usage**: Health check, monitoring, debugging

---

## Critical Patterns

### 1. Singleton Redis Client
**Pattern** (Lines 24-51):

```python
_redis_client = None  # Module-level global

def get_redis_client():
    global _redis_client
    
    if _redis_client is None:
        # Initialize once
        _redis_client = redis.Redis(...)
    
    return _redis_client
```

**Benefits**:
- Connection reuse (avoid creating multiple connections)
- Lazy initialization (only connect when needed)
- Performance (single connection shared across all operations)

### 2. Graceful Degradation
**All functions handle Redis unavailability**:

```python
client = get_redis_client()
if not client:
    return False  # or None or {} depending on function
```

**Result**: App works without persistence if Redis credentials missing or connection fails

**User Experience**: No crashes, just missing persistence feature

### 3. Key Prefixing
**All keys use `order:` prefix** (Lines 125, 154, 180, 201):

```python
key = f"order:{order_id}"
```

**Benefits**:
- Namespace isolation (won't conflict with other Redis data)
- Pattern matching (`keys("order:*")` finds all orders)
- Clarity (immediately obvious what data type key stores)

### 4. Automatic Datetime Serialization
**Problem**: JSON can't serialize Python datetime objects

**Solution**: Custom serialize/deserialize functions (Lines 56-109)

**Approach**:
- Serialize: datetime → ISO string
- Deserialize: ISO string → datetime

**Detection**: If string contains "T", try parsing as datetime

**Example**:
```python
# Python
created_at = datetime(2024, 12, 6, 14, 30, 0)

# JSON (stored in Redis)
"created_at": "2024-12-06T14:30:00"

# Python (after deserialize)
created_at = datetime(2024, 12, 6, 14, 30, 0)
```

### 5. 7-Day Auto-Expiration
**TTL (Time To Live)** (Line 128):

```python
client.expire(key, 604800)  # 7 days = 604800 seconds
```

**Benefits**:
- Automatic cleanup (no manual deletion needed)
- Storage efficiency (old orders removed automatically)
- Cost savings (Upstash Redis charges by storage)

**Trade-off**: Orders older than 7 days lost (acceptable for dispatch system)

### 6. Error Logging Without Exceptions
**All functions catch exceptions and log** (Lines 129-132, 158-161, 183-186, 208-211, 229-232):

```python
try:
    # Redis operation
    return True
except Exception as e:
    logger.error(f"Failed to ... Redis: {e}")
    return False  # or None or {}
```

**Result**: App continues running even if Redis operation fails

---

## Data Flow Diagrams

### Save Order Flow
```
main.py: STATE[order_id] updated
  ↓
redis_save_order(order_id, order_data)
  ├→ get_redis_client()
  │   ├→ Check if _redis_client initialized
  │   └→ If None: Create connection, test ping()
  ├→ serialize_order(order_data)
  │   ├→ Convert datetime → ISO string
  │   ├→ Convert status_history timestamps → ISO strings
  │   └→ Return JSON string
  ├→ client.set(f"order:{order_id}", serialized)
  ├→ client.expire(f"order:{order_id}", 604800)
  └→ Return True
```

### Restore STATE Flow (App Startup)
```
main.py: App starts, STATE is empty
  ↓
redis_get_all_orders()
  ├→ get_redis_client()
  ├→ client.keys("order:*")
  │   └→ Returns: ["order:5866", "order:dishbee_02"]
  ├→ For each key:
  │   ├→ Extract order_id: "5866", "dishbee_02"
  │   ├→ client.get(key)
  │   └→ deserialize_order(json_str)
  │       ├→ Parse JSON
  │       ├→ Convert ISO strings → datetime
  │       └→ Return order dict
  └→ Return: {"5866": {...}, "dishbee_02": {...}}
  ↓
main.py: STATE = redis_get_all_orders()
  ↓
STATE restored with all persisted orders
```

### Get Single Order Flow
```
main.py: Need to retrieve specific order
  ↓
redis_get_order(order_id)
  ├→ get_redis_client()
  ├→ client.get(f"order:{order_id}")
  ├→ If found: deserialize_order(data)
  └→ Return order dict or None
```

---

## Usage Map (What Calls What)

### Called By main.py:
- `redis_save_order()` - After every STATE update
- `redis_get_all_orders()` - During app startup (STATE restoration)
- `redis_get_order()` - Potentially for single order retrieval (not currently used)
- `redis_get_order_count()` - Health check endpoint (if implemented)

### Internal Call Chains:
```
redis_save_order()
  ├→ get_redis_client()
  └→ serialize_order()

redis_get_order()
  ├→ get_redis_client()
  └→ deserialize_order()

redis_get_all_orders()
  ├→ get_redis_client()
  └→ deserialize_order() (for each order)

redis_delete_order()
  └→ get_redis_client()

redis_get_order_count()
  └→ get_redis_client()
```

---

## Environment Variables

### UPSTASH_REDIS_REST_URL
**Example**: `https://epic-falcon-12345.upstash.io`

**Usage**: Redis server endpoint

**Required**: No (app works without Redis)

### UPSTASH_REDIS_REST_TOKEN
**Example**: `AaBbCcDd12345...`

**Usage**: Authentication token for Redis connection

**Required**: No (app works without Redis)

---

## Critical Logic Deep Dives

### Datetime Detection Heuristic (Lines 93-97, 101-107)
**Problem**: After JSON deserialization, all values are primitives (string, number, dict, list)

**Need**: Identify which strings are datetime values that need conversion

**Solution**: Check if string contains "T"

```python
if isinstance(value, str) and "T" in value:
    try:
        order_data[key] = datetime.fromisoformat(value)
    except:
        pass  # Not a datetime, leave as string
```

**Why "T"**: ISO 8601 datetime format uses "T" as separator: "2024-12-06T14:30:00"

**Accuracy**: Very high (fields like "requested_time" are "14:30" without "T", won't be converted)

**False Positives**: Rare (strings containing "T" that aren't datetimes will fail `fromisoformat()` and stay as strings)

### Status History Nested Serialization (Lines 67-79, 98-107)
**Problem**: status_history is a list of dicts, each dict may contain datetime values

**Structure**:
```python
status_history = [
    {"type": "time_sent", "time": "14:30", "timestamp": datetime(...)},
    {"type": "time_confirmed", "time": "14:35", "timestamp": datetime(...)},
    {"type": "assigned", "assigned_to": 123456, "timestamp": datetime(...)}
]
```

**Serialization Approach**:
1. Check if value is list
2. For each item in list:
   - If item is dict: Create new dict with converted values
   - Else: Copy item as-is

**Deserialization Approach**:
1. Check if value is list
2. For each item in list:
   - If item is dict: Modify in-place, converting ISO strings to datetime
   - Else: Leave as-is

**Why Different**: Serialization creates new structure, deserialization modifies existing

### Singleton Pattern with Lazy Init (Lines 24-51)
**Implementation**:

```python
_redis_client = None  # Module-level

def get_redis_client():
    global _redis_client
    
    if _redis_client is None:
        # First call: initialize
        _redis_client = redis.Redis(...)
        _redis_client.ping()  # Test connection
    
    return _redis_client
```

**Benefits**:
- **Lazy**: Connection only created when first needed (not at import time)
- **Singleton**: Single connection reused across all operations
- **Thread-safe**: Python GIL ensures single initialization (for this use case)

**Trade-off**: Not thread-safe for true multi-threaded apps (would need lock)

---

## Stats Summary

**Total Functions**: 8
- Connection management: 1 (`get_redis_client`)
- Serialization: 2 (`serialize_order`, `deserialize_order`)
- CRUD operations: 4 (`save`, `get`, `delete`, `get_all`)
- Monitoring: 1 (`get_order_count`)

**Total Lines**: 232

**Most Complex Function**: `serialize_order()` (56-82, 27 lines) - Handles datetime conversion, nested list traversal, dict item conversion

**Critical Dependencies**:
- redis package (Python Redis client)
- Upstash Redis (cloud Redis service)

**Environment Dependencies**: 2 (UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN)

**Error Handling**: All functions gracefully handle Redis unavailability

**Async Functions**: 0 (all operations are synchronous)

---

## Design Decisions

### 1. In-Memory STATE as Primary, Redis as Backup
**Decision**: STATE dict in main.py is source of truth, Redis is persistence layer

**Rationale**:
- Fast access (no network latency)
- Simple logic (no cache invalidation)
- Graceful degradation (app works without Redis)

**Trade-off**: State lost on restart if Redis unavailable, but acceptable for dispatch system

### 2. 7-Day Expiration
**Decision**: Auto-delete orders after 7 days

**Rationale**:
- Dispatch system doesn't need old data
- Storage cost optimization
- Automatic cleanup (no manual maintenance)

**Trade-off**: No historical data beyond 7 days, but sufficient for operational needs

### 3. Graceful Degradation
**Decision**: All functions return None/False/{} if Redis unavailable

**Rationale**:
- App must work without persistence
- Render restarts common on free tier
- Better UX (no crashes)

**Trade-off**: Silent failures (could add monitoring alerts)

### 4. Key Prefixing
**Decision**: All keys use `order:` prefix

**Rationale**:
- Namespace isolation (avoid conflicts)
- Pattern matching (easy to get all orders)
- Clarity (obvious data type)

**Trade-off**: Slightly longer keys, but negligible storage impact

### 5. Datetime Heuristic ("T" Detection)
**Decision**: Detect datetime strings by checking for "T" character

**Rationale**:
- Simple and fast
- Accurate for ISO 8601 format
- No need to track which fields are datetime

**Trade-off**: Potential false positives (mitigated by try/except)

---

## Phase 1G Complete ✅

**redis_state.py Analysis**: Complete documentation of all 8 Redis persistence functions. Comprehensive coverage of serialization/deserialization logic, singleton pattern, graceful degradation, 7-day auto-expiration, and datetime conversion. Ready to proceed to Phase 1H (ocr.py) - the final support module.
