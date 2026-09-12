import frappe


ALLOWED_ROLES = {"System Manager"}


def require_admin():
    if frappe.session.user == "Administrator":
        return

    roles = set(frappe.get_roles(frappe.session.user))

    if not roles.intersection(ALLOWED_ROLES):
        frappe.throw(
            "You do not have permission to access Customer Applications."
        )


def get_plan_name(application):
    if application.application_type == "Membership":
        return frappe.db.get_value(
            "Membership Plan",
            application.membership_plan,
            "plan_name"
        )

    if application.application_type == "Solo Working":
        return frappe.db.get_value(
            "Space Plan",
            application.space_plan,
            "plan_name"
        )

    return None


def serialize_application(application):
    activities = []

    for row in application.activities or []:
        if row.activity:
            activities.append(row.activity)

    plan_name = get_plan_name(application)

    return {
        "name": application.name,
        "application_type": application.application_type,
        "status": application.status,

        "title": application.title,
        "first_name": application.first_name,
        "last_name": application.last_name,
        "full_name": (
            f"{application.first_name or ''} "
            f"{application.last_name or ''}"
        ).strip(),

        "address": application.address,
        "phone": application.phone,
        "email": application.email,
        "date_of_birth": application.date_of_birth,
        "gender": application.gender,
        "occupation": application.occupation,
        "organization_school": application.organization_school,

        "how_heard_about_us": application.how_heard_about_us,
        "how_heard_other": application.how_heard_other,

        "membership_plan": application.membership_plan,
        "space_plan": application.space_plan,
        "plan_name": plan_name,
        "plan_price": application.plan_price,

        "activities": activities,

        "whatsapp_consent": application.whatsapp_consent,
        "email_consent": application.email_consent,

        "application_date": application.application_date,
        "signature": application.signature,

        "user": application.user,
        "member": application.member,

        "submitted_on": application.submitted_on,
        "reviewed_by": application.reviewed_by,
        "review_notes": application.review_notes,

        "membership": application.membership,
        "space_access": application.space_access,
        "sales_invoice": application.sales_invoice,
        "payment": application.payment,

        "creation": application.creation,
        "modified": application.modified
    }


@frappe.whitelist()
def get_admin_application_stats():
    require_admin()

    statuses = [
        "Draft",
        "Submitted",
        "Pending Review",
        "Approved",
        "Payment Pending",
        "Paid",
        "Activated",
        "Rejected",
        "Cancelled",
        "Payment Failed"
    ]

    result = {
        "total": frappe.db.count("Customer Application"),
        "pending_review": 0,
        "approved": 0,
        "payment_pending": 0,
        "paid": 0,
        "activated": 0,
        "rejected": 0
    }

    for status in statuses:
        count = frappe.db.count(
            "Customer Application",
            {"status": status}
        )

        key = status.lower().replace(" ", "_")

        if key in result:
            result[key] = count

    return result


@frappe.whitelist()
def get_admin_applications(
    status=None,
    application_type=None,
    search=None,
    limit=100,
    offset=0
):
    require_admin()

    try:
        limit = min(max(int(limit), 1), 200)
    except (TypeError, ValueError):
        limit = 100

    try:
        offset = max(int(offset), 0)
    except (TypeError, ValueError):
        offset = 0

    filters = {}

    if status and status != "All":
        filters["status"] = status

    if application_type and application_type != "All":
        filters["application_type"] = application_type

    or_filters = None

    search = (search or "").strip()

    if search:
        search_like = f"%{search}%"

        or_filters = [
            ["Customer Application", "name", "like", search_like],
            ["Customer Application", "first_name", "like", search_like],
            ["Customer Application", "last_name", "like", search_like],
            ["Customer Application", "email", "like", search_like],
            ["Customer Application", "phone", "like", search_like]
        ]

    applications = frappe.get_all(
        "Customer Application",
        filters=filters,
        or_filters=or_filters,
        fields=[
            "name",
            "application_type",
            "status",
            "title",
            "first_name",
            "last_name",
            "email",
            "phone",
            "membership_plan",
            "space_plan",
            "plan_price",
            "application_date",
            "submitted_on",
            "member",
            "membership",
            "space_access",
            "sales_invoice",
            "payment",
            "creation",
            "modified"
        ],
        order_by="creation desc",
        limit_start=offset,
        limit_page_length=limit
    )

    for application in applications:
        application["full_name"] = (
            f"{application.get('first_name') or ''} "
            f"{application.get('last_name') or ''}"
        ).strip()

        if application.get("application_type") == "Membership":
            application["plan_name"] = frappe.db.get_value(
                "Membership Plan",
                application.get("membership_plan"),
                "plan_name"
            )
        else:
            application["plan_name"] = frappe.db.get_value(
                "Space Plan",
                application.get("space_plan"),
                "plan_name"
            )

    total = frappe.db.count(
        "Customer Application",
        filters
    )

    return {
        "applications": applications,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@frappe.whitelist()
def get_admin_application(name):
    require_admin()

    if not name:
        frappe.throw("Application name is required.")

    application = frappe.get_doc(
        "Customer Application",
        name
    )

    return serialize_application(application)


@frappe.whitelist()
def approve_application(name):
    require_admin()

    if not name:
        frappe.throw("Application name is required.")

    application = frappe.get_doc(
        "Customer Application",
        name
    )

    result = application.approve()

    frappe.db.commit()

    return result


@frappe.whitelist()
def reject_application(name, notes=None):
    require_admin()

    if not name:
        frappe.throw("Application name is required.")

    application = frappe.get_doc(
        "Customer Application",
        name
    )

    result = application.reject(notes=notes)

    frappe.db.commit()

    return result
