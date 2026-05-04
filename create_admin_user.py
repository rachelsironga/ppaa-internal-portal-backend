#!/usr/bin/env python
"""
Script to create a Django superuser for admin panel access
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ppaa_portal.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from ppaa_auth.models import User

def create_admin_user():
    """Create a superuser for Django admin"""
    print("Creating Django Admin Superuser...")
    print("-" * 50)
    
    # Default admin credentials (you can change these)
    username = input("Enter username (or press Enter for 'admin'): ").strip() or "admin"
    email = input("Enter email (or press Enter for 'admin@ppaa.local'): ").strip() or "admin@ppaa.local"
    first_name = input("Enter first name (or press Enter for 'Admin'): ").strip() or "Admin"
    last_name = input("Enter last name (or press Enter for 'User'): ").strip() or "User"
    password = input("Enter password (or press Enter for 'admin123'): ").strip() or "admin123"
    
    # Check if user already exists
    if User.objects.filter(username=username).exists():
        print(f"\n❌ User with username '{username}' already exists!")
        update = input("Do you want to update this user to be a superuser? (y/n): ").strip().lower()
        if update == 'y':
            user = User.objects.get(username=username)
            user.is_superuser = True
            user.is_staff = True
            user.is_active = True
            user.account_type = 'SUPER_USER'
            user.status = 'ACTIVE'
            if password:
                user.set_password(password)
            user.save()
            print(f"\n✅ User '{username}' updated to superuser successfully!")
            print(f"   Username: {username}")
            print(f"   Email: {user.email}")
            print(f"   Password: {password}")
            return
        else:
            print("Cancelled.")
            return
    
    if User.objects.filter(email=email).exists():
        print(f"\n❌ User with email '{email}' already exists!")
        return
    
    try:
        # Create superuser
        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            account_type='SUPER_USER',
            status='ACTIVE',
        )
        
        print(f"\n✅ Superuser created successfully!")
        print(f"   Username: {username}")
        print(f"   Email: {email}")
        print(f"   Password: {password}")
        print(f"\n📝 You can now login to Django admin at: http://127.0.0.1:8000/admin/")
        print(f"   Use the credentials above to login.")
        
    except Exception as e:
        print(f"\n❌ Error creating superuser: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    create_admin_user()
