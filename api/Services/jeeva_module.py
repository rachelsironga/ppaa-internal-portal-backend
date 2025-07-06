import time
import requests
from django.db import transaction
from mnh_model.models import JeevaRole, JeevaPermission

BASE_URL = "http://192.168.29.88/dev/mst_apis"

BASE_URL_ROLES = f"{BASE_URL}/jeeva_module/"
BASE_URL_PERMISSIONS = f"{BASE_URL}/jeeva_access/?MODULEID={{}}"

def fetch_roles():
    """
    Fetch all roles from the Jeeva API.
    """
    print("[INFO] Fetching roles...")
    response = requests.get(BASE_URL_ROLES, timeout=10)
    response.raise_for_status()
    data = response.json()
    if data.get('status') != 'success':
        raise Exception("Failed to fetch roles: status not success.")
    return data.get('data', [])

def update_roles_and_permissions():
    """
    Fetch roles and their permissions, update or create them in the database.
    """
    try:
        roles_data = fetch_roles()
    except Exception as e:
        print(f"[ERROR] Could not fetch roles: {e}")
        return

    if not roles_data:
        print("[WARNING] No roles returned from API.")
        return

    print(f"[INFO] Retrieved {len(roles_data)} roles.")

    for idx, role in enumerate(roles_data, start=1):
        group_code = role.get('GROUPCODE')
        group_name = role.get('GROUPNAME')

        if not group_code or not group_name:
            print(f"[WARNING] Skipping invalid role data: {role}")
            continue

        print(f"[INFO] [{idx}/{len(roles_data)}] Processing role {group_code}: {group_name}")

        role_obj, created = JeevaRole.objects.update_or_create(
            code=group_code,
            defaults={'name': group_name, 'is_updated': True}
        )

        if created:
            print(f"[INFO] Created new role: {group_name}")
        else:
            print(f"[INFO] Updated role: {group_name}")

        # Fetch permissions for this role
        try:
            permissions_url = BASE_URL_PERMISSIONS.format(group_code)
            permissions_response = requests.get(permissions_url, timeout=10)
            permissions_response.raise_for_status()
            permissions_data = permissions_response.json().get('data', [])
        except Exception as e:
            print(f"[ERROR] Failed to fetch permissions for role {group_code}: {e}")
            continue

        if not permissions_data:
            print(f"[INFO] No permissions found for role {group_code}")
            continue

        # Map existing permissions
        existing_perms_qs = JeevaPermission.objects.filter(
            role=role_obj,
            code__in=[perm['MODULEID'] for perm in permissions_data]
        )
        existing_perms_map = {p.code: p for p in existing_perms_qs}

        new_perms = []
        updated_perms = []

        for perm in permissions_data:
            code = perm.get('MODULEID')
            name = perm.get('MODULEDESC')

            if not code or not name:
                print(f"[WARNING] Skipping invalid permission data: {perm}")
                continue

            if code in existing_perms_map:
                obj = existing_perms_map[code]
                if obj.name != name:
                    obj.name = name
                    updated_perms.append(obj)
            else:
                new_perms.append(JeevaPermission(code=code, name=name, role=role_obj))

        with transaction.atomic():
            if new_perms:
                JeevaPermission.objects.bulk_create(new_perms, ignore_conflicts=True)
                print(f"[INFO] Created {len(new_perms)} new permissions for {group_name}")

            if updated_perms:
                JeevaPermission.objects.bulk_update(updated_perms, ['name'])
                print(f"[INFO] Updated {len(updated_perms)} permissions for {group_name}")

        # Optional: short delay to avoid hammering the API
        time.sleep(0.2)

    print("[SUCCESS] Roles and permissions update completed.")
