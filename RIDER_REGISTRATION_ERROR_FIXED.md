# Rider Registration Error - FIXED

## Issue
When registering as a rider, a white modal appears showing just "error" with no details, preventing successful registration.

## Root Cause
The registration form was using `"raider"` as the role value, but the database and backend expect `"rider"`.

**Mismatch:**
- Frontend form: `value="raider"` ❌
- Backend/Database: expects `"rider"` ✅

This caused the backend to reject the registration because "raider" is not a valid role in the database enum.

## Locations Fixed

### templates/auth/register.html

**Line 92-93**: Role selection radio button
```html
<!-- BEFORE -->
<input type="radio" name="role" value="raider" id="role_raider">

<!-- AFTER -->
<input type="radio" name="role" value="rider" id="role_rider">
```

**Line 486**: JavaScript role check
```javascript
// BEFORE
} else if (role === 'raider') {

// AFTER
} else if (role === 'rider') {
```

**Line 649**: Form validation
```javascript
// BEFORE
} else if (selectedRole === 'raider') {

// AFTER
} else if (selectedRole === 'rider') {
```

## Database Role Enum
```python
role = db.Column(db.Enum('buyer', 'seller', 'admin', 'rider'), ...)
# Valid values: buyer, seller, admin, rider
# NOT: raider ❌
```

## Testing

After this fix, rider registration should work:

1. ✅ Go to /register
2. ✅ Select "Rider" role
3. ✅ Fill all required fields
4. ✅ Upload valid ID document
5. ✅ Submit form
6. ✅ Should redirect to pending approval page
7. ✅ No "error" modal should appear

## Why It Showed "error"
The backend validation failed because:
1. Form submitted with `role="raider"`
2. Backend tried to save to database
3. Database rejected because "raider" is not in the enum
4. Backend returned generic error
5. Frontend showed alert("error") with no details

## Prevention
Always ensure frontend form values match backend enum values exactly:
- ✅ Use consistent naming
- ✅ Validate enum values
- ✅ Show descriptive error messages
- ✅ Test all role registrations

## Related Fix
The same issue would have affected seller registration if "seller" was misspelled. All role values are now verified to match the database enum.

## Status
✅ **FIXED** - All occurrences of "raider" changed to "rider"

---
**Date Fixed**: November 24, 2025
**Files Modified**: templates/auth/register.html (3 locations)
