"""
SPISM: Strategic Performance Management Information System.
Role names (Django Group names) for role-based access.
Assign these groups to users in the auth module (Users & Roles / System Groups).
"""
# Django Group names for SPISM – create these in Administration > Users & Roles
# NOTE: These are the canonical role/group names used by SPISM. They are human-facing
# labels but also act as Django Group identifiers, so renames should be done carefully
# (rename existing groups in the DB rather than dropping migrations).
SPISM_ROLE_HEAD_OF_PLANNING = "SPISM Planning Manager"
SPISM_ROLE_HEAD_OF_UNIT = "SPISM Performance Officer"
SPISM_ROLE_EXECUTIVE_SECRETARY = "SPISM Approver"
SPISM_ROLE_ICT_ADMINISTRATOR = "SPISM System Administrator"
SPISM_ROLE_INTERNAL_AUDIT = "SPISM Audit Officer"
SPISM_ROLE_READ_ONLY = "SPISM Viewer"

SPISM_ROLES = [
    SPISM_ROLE_HEAD_OF_PLANNING,
    SPISM_ROLE_HEAD_OF_UNIT,
    SPISM_ROLE_EXECUTIVE_SECRETARY,
    SPISM_ROLE_ICT_ADMINISTRATOR,
    SPISM_ROLE_INTERNAL_AUDIT,
    SPISM_ROLE_READ_ONLY,
]

# Display name for the system (replaces "Performance Dashboard")
SPISM_SYSTEM_NAME = "Strategic Performance Management Information System (SPISM)"
