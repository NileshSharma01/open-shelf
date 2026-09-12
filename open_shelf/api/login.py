import frappe


@frappe.whitelist(allow_guest=True)
def resolve_username(usr):
    usr = (usr or "").strip()

    if not usr:
        frappe.throw("Email or username is required.")

    # If the user entered an email, resolve it to the actual Frappe username.
    if "@" in usr:
        username = frappe.db.get_value(
            "User",
            {"email": usr.lower()},
            "name"
        )

        if not username:
            frappe.throw("Invalid login credentials.")

        return {
            "username": username
        }

    # Otherwise use the username directly.
    if not frappe.db.exists("User", usr):
        frappe.throw("Invalid login credentials.")

    return {
        "username": usr
    }
