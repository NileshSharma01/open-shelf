import frappe
from frappe.utils import validate_email_address


@frappe.whitelist(allow_guest=True)
def submit_application(data):
    if isinstance(data, str):
        data = frappe.parse_json(data)

    if not isinstance(data, dict):
        frappe.throw("Invalid application data.")

    if frappe.session.user == "Guest":
        frappe.throw(
            "Please login or create a free Open Shelf account before submitting an application."
        )

    current_user = frappe.get_doc(
        "User",
        frappe.session.user
    )

    current_user_email = (
        current_user.email or ""
    ).strip().lower()

    if not current_user_email:
        frappe.throw(
            "Your Open Shelf account does not have an email address."
        )

    # The authenticated Open Shelf account is the authoritative
    # customer identity. The browser-submitted email is not trusted.
    email = current_user_email

    if not email:
        frappe.throw("Email is required.")

    validate_email_address(email, throw=True)

    application_type = data.get("application_type")

    if application_type not in ["Membership", "Solo Working"]:
        frappe.throw("Please select a valid application type.")

    if application_type == "Membership":
        plan = data.get("membership_plan")

        if not plan:
            frappe.throw("Please select a Membership Plan.")

        if not frappe.db.exists("Membership Plan", plan):
            frappe.throw("Selected Membership Plan does not exist.")

        if not frappe.db.get_value(
            "Membership Plan",
            plan,
            "active"
        ):
            frappe.throw("Selected Membership Plan is not active.")

        existing_filter = {
            "email": email,
            "membership_plan": plan,
            "status": [
                "in",
                [
                    "Submitted",
                    "Pending Review",
                    "Approved",
                    "Payment Pending",
                    "Paid",
                    "Activated"
                ]
            ]
        }

    else:
        plan = data.get("space_plan")

        if not plan:
            frappe.throw("Please select a Solo Working Plan.")

        if not frappe.db.exists("Space Plan", plan):
            frappe.throw("Selected Solo Working Plan does not exist.")

        if not frappe.db.get_value(
            "Space Plan",
            plan,
            "active"
        ):
            frappe.throw("Selected Solo Working Plan is not active.")

        existing_filter = {
            "email": email,
            "space_plan": plan,
            "status": [
                "in",
                [
                    "Submitted",
                    "Pending Review",
                    "Approved",
                    "Payment Pending",
                    "Paid",
                    "Activated"
                ]
            ]
        }

    existing = frappe.db.exists(
        "Customer Application",
        existing_filter
    )

    if existing:
        frappe.throw(
            f"An active application already exists for this email and plan: {existing}"
        )

    application = frappe.get_doc({
        "doctype": "Customer Application",
        "application_type": application_type,
        "user": frappe.session.user,
        "membership_plan": (
            data.get("membership_plan")
            if application_type == "Membership"
            else None
        ),
        "space_plan": (
            data.get("space_plan")
            if application_type == "Solo Working"
            else None
        ),
        "title": data.get("title"),
        "first_name": data.get("first_name"),
        "last_name": data.get("last_name"),
        "address": data.get("address"),
        "phone": data.get("phone"),
        "email": email,
        "date_of_birth": data.get("date_of_birth"),
        "gender": data.get("gender"),
        "occupation": data.get("occupation"),
        "organization_school": data.get("organization_school"),
        "how_heard_about_us": data.get("how_heard_about_us"),
        "how_heard_other": data.get("how_heard_other"),
        "whatsapp_consent": 1 if data.get("whatsapp_consent") else 0,
        "email_consent": 1 if data.get("email_consent") else 0,
        "application_date": data.get("application_date"),
        "signature": data.get("signature")
    })

    for activity in data.get("activities", []) or []:
        if isinstance(activity, str):
            activity_name = activity
        else:
            activity_name = activity.get("activity")

        if activity_name:
            application.append(
                "activities",
                {
                    "activity": activity_name
                }
            )

    application.insert(ignore_permissions=True)

    result = application.submit_application()

    frappe.db.commit()

    return result


@frappe.whitelist(allow_guest=True)
def get_active_plans():
    membership_plans = frappe.get_all(
        "Membership Plan",
        filters={"active": 1},
        fields=[
            "name",
            "plan_name",
            "duration_months",
            "price",
            "max_hours_per_day",
            "additional_hour_fee",
            "wifi_included",
            "cafe_voucher_amount",
            "description"
        ],
        order_by="price asc"
    )

    space_plans = frappe.get_all(
        "Space Plan",
        filters={"active": 1},
        fields=[
            "name",
            "plan_name",
            "billing_period",
            "price",
            "max_hours_per_day",
            "additional_hour_fee",
            "wifi_included",
            "cafe_voucher_amount",
            "description"
        ],
        order_by="price asc"
    )

    return {
        "membership_plans": membership_plans,
        "space_plans": space_plans
    }
