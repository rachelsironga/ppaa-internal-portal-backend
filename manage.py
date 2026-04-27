#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ppaa_portal.settings')
    try:
        import django
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment? "
            "Use this repo's venv: cd ppaa-internal-portal-backend && "
            "python -m venv .venv && source .venv/bin/activate && "
            "pip install -r requirements.txt"
        ) from exc

    if django.VERSION[:2] != (5, 1):
        sys.stderr.write(
            "This project requires Django 5.1.x (see requirements.txt). "
            f"Found {django.get_version()}. "
            "You may be using another project's virtualenv.\n"
        )
        sys.exit(1)
    if django.get_version() != "5.1.5":
        sys.stderr.write(
            f"Warning: Django {django.get_version()} is not 5.1.5 as pinned in requirements.txt.\n"
        )

    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
