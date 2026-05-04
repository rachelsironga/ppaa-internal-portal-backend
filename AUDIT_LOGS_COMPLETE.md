# Complete Audit Logs Implementation

## Overview
All user actions across all tables are now captured in the `audit_logs` table in PostgreSQL. Every CREATE, UPDATE, DELETE, and important VIEW operation is logged.

## Database Table
The `audit_logs` table exists in your PostgreSQL database (`ppaa_portal_db`). To verify:

```sql
-- Check if table exists
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name = 'audit_logs';

-- View recent logs
SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 10;

-- Count total logs
SELECT COUNT(*) FROM audit_logs;
```

## Complete List of Logged Operations

### ✅ User Management
1. **User Create** - When a new user is created
2. **User Update** - When user details are updated
3. **User Delete** - When a user is deleted
4. **User Photo Upload** - When user photo is uploaded/changed
5. **User Signature Upload** - When user signature is uploaded/changed
6. **User Role Assignment** - When roles are assigned/removed from users (bulk)
7. **Single Role Assignment** - When a single role is assigned to a user
8. **Single Role Removal** - When a single role is removed from a user

### ✅ Authentication & Security
9. **User Login** - When a user logs in
10. **User Logout** - When a user logs out
11. **Password Change** - When a user changes their own password
12. **Admin Password Change** - When an admin changes a user's password

### ✅ User Profiles
13. **User Profile Create** - When a user profile is created
14. **User Profile Update** - When a user profile is updated
15. **User Profile Delete** - When a user profile is deleted
16. **Acting User Assignment** - When a user delegates to an acting user
17. **Acting User Removal** - When acting user delegation is removed

### ✅ Content Management
18. **Documents** - CREATE, UPDATE, DELETE, VIEW
19. **Document Categories** - CREATE, UPDATE, DELETE, VIEW
20. **Announcements** - CREATE, UPDATE, DELETE, VIEW
21. **Events** - CREATE, UPDATE, DELETE, VIEW
22. **FAQs** - CREATE, UPDATE, DELETE, VIEW
23. **Notifications** - CREATE, UPDATE, DELETE, VIEW
24. **Todo Lists** - CREATE, UPDATE, DELETE, VIEW
25. **Quick Links** - CREATE, UPDATE, DELETE, VIEW

### ✅ System Configuration
26. **Departments** - CREATE, UPDATE, DELETE, VIEW
27. **Department Bulk Import** - When departments are imported via Excel
28. **Positional Levels** - CREATE, UPDATE, DELETE
29. **System Roles** - CREATE, UPDATE, DELETE
30. **System Permissions** - VIEW (read-only)

## API Endpoint
- **GET** `/api/internal-portal/audit-logs` - List all audit logs (paginated)
- **GET** `/api/internal-portal/audit-logs/<uid>` - Get specific audit log details

### Query Parameters:
- `model_name` - Filter by model name (e.g., "User", "Document")
- `action` - Filter by action (CREATE, UPDATE, DELETE, VIEW, LOGIN, LOGOUT)
- `user` - Filter by user UID
- `department` - Filter by department UID
- `page` - Page number for pagination
- `page_size` - Number of items per page

## Frontend Display
- **Route**: `/ppaa-internal-portal/audit-logs`
- **Component**: `AuditLogPage` in `ppaa-internal-portal-frontend/src/pages/services/PPAA-INTERNAL-PORTAL/audit_logs/View.jsx`
- **Permissions Required**: `can_view_audit_log` permission or `admin`/`ICT` role

## Database Schema

The `audit_logs` table structure:
```sql
CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    uid UUID UNIQUE NOT NULL,
    user_id INTEGER REFERENCES auth_user(id),
    action VARCHAR(20) NOT NULL,  -- CREATE, UPDATE, DELETE, VIEW, LOGIN, LOGOUT, DOWNLOAD
    model_name VARCHAR(100) NOT NULL,  -- e.g., "User", "Document", "UserRoles"
    object_id UUID,  -- UUID of the affected object
    object_repr VARCHAR(200),  -- String representation of the object
    changes JSONB,  -- Before/after changes or additional data
    ip_address INET,  -- IP address of the user
    user_agent VARCHAR(500),  -- Browser/user agent
    department_id INTEGER REFERENCES departments(id),
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    created_by INTEGER,
    updated_by INTEGER,
    is_deleted BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE
);
```

## How It Works

1. **Automatic Logging**: Every time a user performs an action (create, update, delete), an audit log is automatically created
2. **Non-Blocking**: Audit log creation never interrupts the main request flow - if logging fails, the operation still succeeds
3. **Comprehensive Data**: Each log includes:
   - Who performed the action (user)
   - What action was performed (CREATE, UPDATE, DELETE, etc.)
   - What model/table was affected
   - Which specific record was affected (object_id)
   - What changed (changes JSON field)
   - When it happened (created_at)
   - Where it came from (IP address, user agent)
   - User's department (if applicable)

## Verification Steps

1. **Check Database**:
   ```sql
   SELECT COUNT(*) FROM audit_logs;
   SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 10;
   ```

2. **Perform Actions and Verify**:
   - Create a user → Check audit_logs table
   - Assign roles to user → Check audit_logs table
   - Update a document → Check audit_logs table
   - Delete an announcement → Check audit_logs table

3. **Check Frontend**:
   - Navigate to System Logs page
   - Verify logs appear in the table
   - Check filters work correctly

## Troubleshooting

### If audit logs are not showing:

1. **Check Database Connection**: Ensure Django can connect to PostgreSQL
2. **Check Table Exists**: Run migrations if needed
   ```bash
   python manage.py migrate ppaa_portal
   ```
3. **Check Permissions**: User needs `can_view_audit_log` permission
4. **Check API Response**: Open browser DevTools → Network tab → Check `/api/internal-portal/audit-logs` response
5. **Check Logs Are Being Created**: Perform an action and immediately check database:
   ```sql
   SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 1;
   ```

## Recent Additions

### Newly Added Audit Logging:
1. ✅ User Role Assignments (bulk and single)
2. ✅ User Create/Update/Delete
3. ✅ User Photo Upload
4. ✅ User Signature Upload
5. ✅ System Role Create/Update/Delete
6. ✅ Acting User Assignment/Removal
7. ✅ Department Bulk Import

All operations are now fully logged! 🎉
