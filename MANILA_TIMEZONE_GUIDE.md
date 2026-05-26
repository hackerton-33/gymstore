# Manila Timezone Implementation Guide

## Overview
All datetime functions in this application now use **Asia/Manila timezone** (Philippine Time - PHT, UTC+8).

## Changes Made

### 1. Added pytz Library
- Added `pytz==2024.1` to requirements.txt
- Imported pytz in app.py

### 2. Updated Helper Functions

#### New Functions:
```python
manila_now()           # Returns timezone-aware Manila datetime
manila_now_naive()     # Returns naive Manila datetime (for database)
```

#### Updated Legacy Functions:
```python
utc_now()             # Now returns Manila time (backward compatible)
utc_now_naive()       # Now returns Manila time (backward compatible)
```

### 3. Template Filter & Context Processor
Added `manila_time` filter for templates:
```html
{{ order.created_at|manila_time }}
{{ user.created_at.strftime('%B %d, %Y %I:%M %p') }}  <!-- Already in Manila time -->
```

Added context processor to make Manila time functions available in all templates:
```html
{{ manila_now_naive() }}  <!-- Current Manila time in templates -->
```

## Usage in Code

### Creating New Records
All datetime fields automatically use Manila time:
```python
# Models use default=utc_now which now returns Manila time
user = User(
    username='john',
    created_at=utc_now()  # Manila time
)
```

### Getting Current Time
```python
# Use these functions anywhere you need current time
current_time = manila_now_naive()  # For database operations
current_time_aware = manila_now()   # For timezone-aware operations
```

### Comparing Times
```python
# All times are now in Manila timezone
if order.created_at > manila_now_naive() - timedelta(hours=24):
    # Order is less than 24 hours old
    pass
```

## Database Considerations

- All existing datetime records are treated as Manila time
- New records automatically use Manila time
- No migration needed - times are stored as naive datetimes

## Display in Templates

Times will automatically display in Manila timezone. Examples:
```html
<!-- Order created time -->
<p>Order placed: {{ order.created_at.strftime('%B %d, %Y at %I:%M %p') }}</p>

<!-- User registration -->
<p>Member since: {{ user.created_at.strftime('%B %Y') }}</p>

<!-- Relative time (you can add a custom filter for this) -->
<p>{{ order.created_at.strftime('%Y-%m-%d %H:%M:%S') }} PHT</p>
```

## Testing

To verify Manila time is working:
```python
from app import manila_now, manila_now_naive
print(f"Current Manila time: {manila_now()}")
print(f"Current Manila time (naive): {manila_now_naive()}")
```

## Notes

- Manila timezone is UTC+8 (no daylight saving time)
- All times in the system are now consistent with Philippine time
- Legacy function names (`utc_now`, `utc_now_naive`) still work but return Manila time
- Database stores naive datetimes (without timezone info) in Manila time
