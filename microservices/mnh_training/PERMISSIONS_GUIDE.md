# Training Permissions & Roles Guide

## Overview
This guide explains the permission system and user roles for the MNH Training module.

## Setup

### Running the Permissions Command

To create all permissions and groups, run:

```bash
python manage.py training_permissions
```

This command will:
1. Create standard Django permissions for all Training models
2. Create custom permissions for specialized operations
3. Create 6 user groups with appropriate permission sets
4. Assign all Training permissions to superusers

## User Roles

### 1. **Training Head** (Full Authority)
**Group Name:** `Training_Head`

**Responsibilities:**
- Oversee all training programs and operations
- Approve or reject training applications
- Manage MOUs with institutions
- Create and finalize training batches
- Manage all student records and affiliations
- Approve bulk operations
- View all reports and analytics

**Permissions:**
- ✓ Full CRUD on all Training models
- ✓ Approve/Reject applications
- ✓ Bulk enroll and update students
- ✓ Create, finalize, cancel training batches
- ✓ Create and renew MOUs
- ✓ Manage institutions and MOUs
- ✓ Allocate departments and assign supervisors
- ✓ Export all training data
- ✓ Generate and view all reports
- ✓ Access student, institution, and MOU lookups

**Key Operations:**
```
POST /applications/<uid>/approve
POST /training-batches/<uid>/finalize
POST /mous/renew
PUT /institutions/<uid>
POST /department-allocations (bulk)
```

---

### 2. **Head of Training Secretary** (Administrative Authority)
**Group Name:** `Head_of_Training_Secretary`

**Responsibilities:**
- Manage administrative aspects of training
- Process and approve training applications (delegated)
- Create and manage MOUs
- Schedule department allocations
- Prepare training batches for finalization
- Manage training data and generate reports

**Permissions:**
- ✓ View all student records (can update)
- ✓ Add/View/Edit affiliations
- ✓ Add/View/Edit/Approve applications
- ✓ Create/View/Edit department allocations
- ✓ View/Edit supervisors
- ✓ Create/View/Edit institutions
- ✓ Create/View/Edit MOUs with renewal capability
- ✓ Create/View/Edit training batches
- ✓ Generate and view reports
- ✓ Export student and application data
- ✓ Access all lookups

**Key Operations:**
```
POST /applications
PUT /applications/<uid>
POST /mous
PUT /department-allocations/<uid>
POST /training-batches
```

---

### 3. **Training Coordinator** (Operational Authority)
**Group Name:** `Training_Coordinator`

**Responsibilities:**
- Day-to-day coordination of training activities
- Enroll students and maintain records
- Create and manage training applications
- Add department allocations and supervisors
- Track training batch progress
- Support students and management with data

**Permissions:**
- ✓ View and create student records
- ✓ View/Create affiliations
- ✓ Create/View/Edit applications (limited)
- ✓ View/Create department allocations
- ✓ View/Create supervisors
- ✓ View institutions and MOUs (read-only)
- ✓ View and edit training batches
- ✓ View dashboard and reports
- ✓ Export training data
- ✓ Access lookups for reference data

**Key Operations:**
```
POST /students
POST /applications
POST /department-allocations
PUT /training-batches/<uid>
GET /students?search=
GET /training-batches
```

---

### 4. **Training Auditor** (Oversight Role)
**Group Name:** `Training_Auditor`

**Responsibilities:**
- Audit training operations and compliance
- Review training records and processes
- Generate audit reports
- Monitor training batch completion
- Verify data integrity

**Permissions:**
- ✓ View all Training models (read-only)
- ✓ Generate training reports
- ✓ Export student, application, and training data
- ✓ Access dashboard with analytics

**Key Operations:**
```
GET /students
GET /applications
GET /training-batches
GET /mous
Generate Reports
```

---

### 5. **Department Training User** (Limited Department Access)
**Group Name:** `Department_Training_User`

**Responsibilities:**
- Manage training operations at department level
- View student records assigned to department
- Track department allocations
- Access relevant training information

**Permissions:**
- ✓ View students (department-filtered)
- ✓ View applications assigned to department
- ✓ View department allocations
- ✓ View supervisors in department
- ✓ View training batches
- ✓ Access dashboard

**Key Operations:**
```
GET /students?department=
GET /applications?department=
GET /department-allocations
GET /training-batches
```

---

### 6. **Training ReadOnly User** (General Read Access)
**Group Name:** `Training_ReadOnly_User`

**Responsibilities:**
- Access training information for reference
- View reports and analytics
- Support organizational visibility into training

**Permissions:**
- ✓ View all Training models (read-only)
- ✓ Access dashboard
- ✓ Export training data

**Key Operations:**
```
GET /students
GET /applications
GET /institutions
GET /mous
GET /training-batches
```

---

## Permission Categories

### Model Permissions (Standard CRUD)
For each model (Student, Application, Institution, etc.):
- `add_<model>` - Create new records
- `view_<model>` - View records
- `change_<model>` - Edit records
- `delete_<model>` - Delete records

### Custom Permissions

#### Student Management
- `bulk_enroll_students` - Enroll multiple students at once
- `bulk_update_students` - Update multiple student records
- `export_students` - Export student data

#### Application Management
- `approve_application` - Approve training applications
- `reject_application` - Reject applications
- `bulk_approve_applications` - Approve multiple applications
- `export_applications` - Export application data

#### Training Batch
- `create_training_batch` - Create new batches
- `finalize_training_batch` - Mark batch as complete
- `cancel_training_batch` - Cancel batch

#### MOU Management
- `create_mou` - Create new MOUs
- `renew_mou` - Renew expiring MOUs
- `track_mou_expiry` - Monitor MOU expirations

#### Institution Management
- `manage_institutions` - Full institution control
- `create_institution` - Create new institutions

#### Allocation & Scheduling
- `allocate_departments` - Assign departments to training
- `assign_supervisors` - Assign supervisors to allocations

#### Reporting & Analytics
- `view_training_dashboard` - Access training dashboard
- `view_training_reports` - View training reports
- `generate_training_report` - Create custom reports
- `export_training_data` - Export all training data

#### Lookup Permissions
- `view_student_lookup` - Search students
- `view_institution_lookup` - Search institutions
- `view_mou_lookup` - Search MOUs

---

## Assigning Users to Groups

### Add User to Group (Django Admin)
1. Go to Users section
2. Select user
3. Under "Groups" section, add desired group(s)
4. Save

### Add User to Group (Programmatically)
```python
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.get(username='john_doe')
group = Group.objects.get(name='Training_Coordinator')
user.groups.add(group)
```

---

## Checking Permissions

### View User Permissions
```python
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.get(username='john_doe')

# Check if user is in group
print(user.groups.all())  # All groups user belongs to

# Check specific permission
print(user.has_perm('mnh_training.view_student'))
print(user.has_perm('mnh_training.approve_application'))

# Check all permissions
print(user.get_all_permissions())
```

### In Views/API Endpoints
Permissions are automatically checked via:
- `IsAuthenticated` - User must be logged in
- `HasMethodPermission` - User must have method-specific permission

Example permission check in endpoint:
```python
required_permissions = {
    "get": ["view_application"],
    "post": ["add_application", "change_application"],
    "delete": ["delete_application"],
}
```

---

## Permission Hierarchy

```
Superuser
├── Training_Head (Full Access)
├── Head_of_Training_Secretary (Administrative)
├── Training_Coordinator (Operational)
├── Training_Auditor (Read-Only with Reports)
├── Department_Training_User (Department-Limited)
└── Training_ReadOnly_User (General Read)
```

---

## Common Workflows by Role

### Training Head
1. Review training requests
2. Approve/reject applications
3. Manage MOUs with institutions
4. Create training batches
5. Generate strategic reports

### Head of Training Secretary
1. Process applications
2. Prepare training materials
3. Manage MOUs and institutions
4. Schedule department allocations
5. Prepare batches for launch

### Training Coordinator
1. Enroll new students
2. Create training applications
3. Assign departments and supervisors
4. Monitor batch progress
5. Provide student support

### Training Auditor
1. Audit training records
2. Verify compliance
3. Generate audit reports
4. Monitor data integrity

---

## Troubleshooting

### User Cannot Perform Action
1. Check user is in appropriate group
2. Verify group has required permission
3. Check permission codename is correct
4. Run `python manage.py training_permissions` to resync

### Permission Command Fails
- Ensure all Training models are properly defined
- Check that mnh_auth models (Department, etc.) are accessible
- Run migrations first: `python manage.py migrate`

### Missing Permissions
If some permissions don't show up after running the command:
1. Ensure models are registered in Django
2. Check ContentType cache
3. Run: `python manage.py migrate contenttypes`

---

## Security Notes

- ✓ Superusers automatically get all permissions
- ✓ Permissions are checked at API endpoint level
- ✓ Groups can be combined for users with multiple roles
- ✓ Custom permissions allow granular control
- ✓ Soft delete respected in all queries (is_deleted=False)

---

## Need Help?

For questions about specific permissions or role assignments, refer to the permissions command output or check the group definitions in `training_permissions.py`.
