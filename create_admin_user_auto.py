#!/usr/bin/env python
"""
Script to create a Django superuser automatically (non-interactive)
Usage: python create_admin_user_auto.py [username] [email] [password]
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ppaa_portal.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from ppaa_auth.models import User

def create_admin_user(username="admin", email="admin@ppaa.local", password="admin123", 
                     first_name="Admin", last_name="User"):
    """Create a superuser for Django admin"""
    print("Creating Django Admin Superuser...")
    print("-" * 50)
    
    # Check if user already exists
    if User.objects.filter(username=username).exists():
        print(f"\n⚠️  User with username '{username}' already exists!")
        user = User.objects.get(username=username)
        user.is_superuser = True
        user.is_staff = True
        user.is_active = True
        user.account_type = 'SUPER_USER'
        user.status = 'ACTIVE'
        user.set_password(password)
        user.save()
        print(f"✅ User '{username}' updated to superuser successfully!")
    elif User.objects.filter(email=email).exists():
        print(f"\n⚠️  User with email '{email}' already exists!")
        user = User.objects.get(email=email)
        user.is_superuser = True
        user.is_staff = True
        user.is_active = True
        user.account_type = 'SUPER_USER'
        user.status = 'ACTIVE'
        user.username = username
        user.set_password(password)
        user.save()
        print(f"✅ User '{email}' updated to superuser successfully!")
    else:
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
            print(f"✅ Superuser created successfully!")
        except Exception as e:
            print(f"\n❌ Error creating superuser: {str(e)}")
            sys.exit(1)
    
    print(f"\n📋 Admin User Details:")
    print(f"   Username: {username}")
    print(f"   Email: {email}")
    print(f"   Password: {password}")
    print(f"   Name: {first_name} {last_name}")
    print(f"\n🌐 Django Admin URL: http://127.0.0.1:8000/admin/")
    print(f"   Use the credentials above to login.")

if __name__ == "__main__":
    # Get arguments from command line or use defaults
    username = sys.argv[1] if len(sys.argv) > 1 else "admin"
    email = sys.argv[2] if len(sys.argv) > 2 else "admin@ppaa.local"
    password = sys.argv[3] if len(sys.argv) > 3 else "admin123"
    first_name = sys.argv[4] if len(sys.argv) > 4 else "Admin"
    last_name = sys.argv[5] if len(sys.argv) > 5 else "User"
    
    create_admin_user(username, email, password, first_name, last_name)
