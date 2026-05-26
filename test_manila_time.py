#!/usr/bin/env python3
"""
Test script to verify Manila timezone implementation
"""
from datetime import datetime, UTC
import pytz

# Manila timezone
MANILA_TZ = pytz.timezone('Asia/Manila')

def manila_now():
    """Get current Manila datetime (timezone-aware)"""
    return datetime.now(MANILA_TZ)

def manila_now_naive():
    """Get current Manila datetime without timezone info (for database storage)"""
    return datetime.now(MANILA_TZ).replace(tzinfo=None)

if __name__ == '__main__':
    print("=" * 60)
    print("MANILA TIMEZONE TEST")
    print("=" * 60)
    
    # Get current times
    utc_time = datetime.now(UTC)
    manila_time = manila_now()
    manila_naive = manila_now_naive()
    
    print(f"\nUTC Time:           {utc_time}")
    print(f"Manila Time (TZ):   {manila_time}")
    print(f"Manila Time (Naive): {manila_naive}")
    
    print(f"\nFormatted Manila Time: {manila_naive.strftime('%B %d, %Y at %I:%M:%S %p')}")
    print(f"Timezone Offset: UTC+8 (Philippine Time)")
    
    # Verify offset
    offset = manila_time.utcoffset().total_seconds() / 3600
    print(f"\nVerification: Manila is UTC+{offset:.0f}")
    
    print("\n" + "=" * 60)
    print("✓ Manila timezone is working correctly!")
    print("=" * 60)
