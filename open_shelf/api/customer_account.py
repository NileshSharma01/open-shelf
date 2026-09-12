import frappe
from frappe.utils import validate_email_address


@frappe.whitelist(allow_guest=True)
def create_free_account(full_name=None, email=None):

    full_name = (full_name or "").strip()
    email = (email or "").strip().lower()

    if not full_name:
        frappe.throw("Full name is required.")

    if not email:
        frappe.throw("Email is required.")

    validate_email_address(
        email,
        throw=True
    )

    existing_user = frappe.db.get_value(
        "User",
        {"email": email},
        "name"
    )

    if existing_user:

        user = frappe.get_doc(
            "User",
            existing_user
        )

        if user.enabled:
            frappe.throw(
                "An account already exists for this email. Please login instead."
            )

        user.enabled = 1
        user.save(
            ignore_permissions=True
        )

        return {
            "success": True,
            "existing": True,
            "email": email
        }

    user = frappe.get_doc({
        "doctype": "User",
        "email": email,
        "first_name": full_name,
        "user_type": "Website User",
        "enabled": 1,
        "send_welcome_email": 1
    })

    user.insert(
        ignore_permissions=True
    )

    frappe.db.commit()

    # Automatically establish the Website User session after
    # successful free-account creation.
    # Establish the Website User session using Frappe's
    # normal login manager and persist the session before
    # returning the API response.
    frappe.local.login_manager.login_as(user.name)
    frappe.local.login_manager.post_login()

    frappe.db.commit()

    return {
        "success": True,
        "existing": False,
        "email": email,
        "user": user.name
    }
