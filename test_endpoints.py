#!/usr/bin/env python
"""Test script for mnh_training endpoints"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mnh_approval.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model

User = get_user_model()

client = Client()

# Test endpoints
endpoints = [
    ('GET', '/api/training/students'),
    ('GET', '/api/training/affiliations'),
    ('GET', '/api/training/institutions'),
    ('GET', '/api/training/mous'),
    ('GET', '/api/training/training-batches'),
    ('GET', '/api/training/applications'),
    ('GET', '/api/training/department-allocations'),
    ('GET', '/api/training/supervisors'),
]

print("Testing mnh_training endpoints...\n")

for method, path in endpoints:
    if method == 'GET':
        response = client.get(path)
    elif method == 'POST':
        response = client.post(path, {})
    
    status = response.status_code
    print(f"{method:6} {path:50} => {status}")
    
    # Show error if it occurred
    if status >= 400:
        try:
            content = response.content.decode()[:300]
            print(f"       Error: {content}")
        except:
            pass

print("\nDone!")
