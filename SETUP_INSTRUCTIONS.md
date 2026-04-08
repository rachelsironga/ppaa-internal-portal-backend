# PPAA Internal Portal - Setup Instructions

## Backend Setup

### 1. Initialize MinIO Buckets

Run the following command to create and initialize MinIO buckets:

```bash
cd ppaa-internal-portal-backend
python manage.py init_minio_buckets
```

This will:
- Create the main bucket if it doesn't exist
- Create folder structure: `documents/`, `announcements/`, `events/`, `links/`, `user_photos/`

### 2. Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 3. Create Custom Permissions

```bash
python manage.py custom_permissions
```

This creates all the custom permissions for:
- Document Categories
- Documents
- Announcements
- Events
- FAQs
- Notifications
- Todo Lists
- Audit Logs
- Departments

### 4. Environment Variables

Ensure your `.env` file has:

```env
AWS_S3_ENDPOINT_URL=http://minio:9000  # or your MinIO endpoint
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_STORAGE_BUCKET_NAME=ppaa-portal  # or your bucket name
AWS_S3_REGION_NAME=us-east-1
```

### 5. Start Backend Server

```bash
python manage.py runserver
```

## API Endpoints

### System Management
- `GET/POST /api/system/roles` - Role management
- `GET /api/system/system-permissions` - List all permissions
- `GET /api/system/system-groups` - List all groups
- `POST /api/system/roles-assign-users` - Assign role to user
- `DELETE /api/system/roles-assign-users?user={uid}&role={id}` - Remove user from role

### Department Management
- `GET/POST /api/internal-portal/departments` - List/Create departments
- `GET/PUT/DELETE /api/internal-portal/departments/{uid}` - Department operations

### Document Management
- `GET/POST /api/internal-portal/documents` - List/Create documents
- `GET/PUT/DELETE /api/internal-portal/documents/{uid}` - Document operations
- **File Upload**: Include `file_base64` and `file_name` in POST/PUT request

### Document Categories
- `GET/POST /api/internal-portal/document-categories` - List/Create categories
- `GET/PUT/DELETE /api/internal-portal/document-categories/{uid}` - Category operations

### Announcements
- `GET/POST /api/internal-portal/announcements` - List/Create announcements
- `GET/PUT/DELETE /api/internal-portal/announcements/{uid}` - Announcement operations

### Events
- `GET/POST /api/internal-portal/events` - List/Create events
- `GET/PUT/DELETE /api/internal-portal/events/{uid}` - Event operations

### FAQs
- `GET/POST /api/internal-portal/faqs` - List/Create FAQs
- `GET/PUT/DELETE /api/internal-portal/faqs/{uid}` - FAQ operations

### Notifications
- `GET/POST /api/internal-portal/notifications` - List/Create notifications
- `GET/PUT/DELETE /api/internal-portal/notifications/{uid}` - Notification operations

### Todo Lists
- `GET/POST /api/internal-portal/todos` - List/Create todos
- `GET/PUT/DELETE /api/internal-portal/todos/{uid}` - Todo operations

### Audit Logs
- `GET /api/internal-portal/audit-logs` - View audit logs

## File Upload Format

When uploading files to MinIO, use base64 encoding:

```json
{
  "title": "Document Title",
  "description": "Document description",
  "file_base64": "data:image/png;base64,iVBORw0KGgoAAAANS...",
  "file_name": "document.pdf",
  "category_uid": "uuid-here",
  "department_uid": "uuid-here",
  "status": "PUBLISHED",
  "is_public": true
}
```

## Frontend Setup

See the frontend directory for React components. The frontend should be configured to:
1. Connect to the backend API
2. Handle JWT authentication
3. Display role-based permissions
4. Support file uploads using base64 encoding

## Next Steps

1. ✅ Backend API endpoints are ready
2. ✅ MinIO bucket initialization command created
3. ✅ Document upload with MinIO integration
4. ⏳ Frontend pages for:
   - Role & Permission Management
   - Department Management
   - Document Management with file uploads

