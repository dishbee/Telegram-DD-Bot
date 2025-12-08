"""
Manual Redis Cleanup Script
Run this to immediately delete orders before Dec 7, 2025.
Keeps orders from Dec 7 onwards (Dec 7 + Dec 8).
"""
import os
from datetime import datetime
from redis_state import redis_cleanup_old_orders

if __name__ == "__main__":
    # Delete orders before Dec 7, 2025
    # days_to_keep=1 means: keep today (Dec 8) + 1 previous day (Dec 7)
    
    print(f"🗑️  Starting manual cleanup...")
    print(f"📅 Today: December 8, 2025")
    print(f"📅 Deleting: Orders before December 7, 2025")
    print(f"📅 Keeping: Dec 7 and Dec 8 only")
    print()
    
    deleted_count = redis_cleanup_old_orders(days_to_keep=1)
    
    print()
    print(f"✅ Cleanup complete! Deleted {deleted_count} orders.")
    print(f"📊 Remaining orders are from Dec 7-8 only.")
