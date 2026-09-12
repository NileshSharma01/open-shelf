import frappe
from frappe.model.document import Document
from frappe.utils import today, now_datetime, getdate, add_months


class CustomerApplication(Document):

    def validate(self):
        self.set_application_type_from_plan()
        self.validate_plan()
        self.validate_personal_information()
        self.validate_source()
        self.validate_consent()
        self.validate_activities()
        self.set_plan_price()

    def validate_plan(self):
        if self.application_type == "Membership":
            if not self.membership_plan:
                frappe.throw("Please select a Membership Plan.")

            if self.space_plan:
                frappe.throw(
                    "Space Plan must be empty for a Membership application."
                )

            plan = frappe.get_doc(
                "Membership Plan",
                self.membership_plan
            )

            if not plan.active:
                frappe.throw(
                    f"Membership Plan '{plan.plan_name}' is not active."
                )

        elif self.application_type == "Solo Working":
            if not self.space_plan:
                frappe.throw("Please select a Solo Working Plan.")

            if self.membership_plan:
                frappe.throw(
                    "Membership Plan must be empty for a Solo Working application."
                )

            plan = frappe.get_doc(
                "Space Plan",
                self.space_plan
            )

            if not plan.active:
                frappe.throw(
                    f"Space Plan '{plan.plan_name}' is not active."
                )

        else:
            frappe.throw("Please select a valid Application Type.")

    def set_application_type_from_plan(self):
        if self.membership_plan and not self.space_plan:
            self.application_type = "Membership"

        elif self.space_plan and not self.membership_plan:
            self.application_type = "Solo Working"

    def set_plan_price(self):
        if self.application_type == "Membership" and self.membership_plan:
            self.plan_price = frappe.db.get_value(
                "Membership Plan",
                self.membership_plan,
                "price"
            )

        elif self.application_type == "Solo Working" and self.space_plan:
            self.plan_price = frappe.db.get_value(
                "Space Plan",
                self.space_plan,
                "price"
            )

    def validate_personal_information(self):
        if not self.first_name:
            frappe.throw("First Name is required.")

        if not self.last_name:
            frappe.throw("Last Name is required.")

        if not self.email:
            frappe.throw("Email is required.")

        if not self.phone:
            frappe.throw("Phone is required.")

        if not self.address:
            frappe.throw("Address is required.")

    def validate_source(self):
        if (
            self.how_heard_about_us == "Other"
            and not self.how_heard_other
        ):
            frappe.throw(
                "Please specify how you heard about us."
            )

    def validate_consent(self):
        if not self.whatsapp_consent:
            frappe.throw(
                "WhatsApp community consent is required."
            )

        if not self.email_consent:
            frappe.throw(
                "Group email consent is required."
            )

    def validate_activities(self):
        seen = set()

        for row in self.activities or []:
            if not row.activity:
                continue

            if row.activity in seen:
                frappe.throw(
                    f"Activity '{row.activity}' has been selected more than once."
                )

            seen.add(row.activity)

    def before_insert(self):
        if not self.application_date:
            self.application_date = today()

        if not self.status:
            self.status = "Draft"

    def submit_application(self):
        if self.status not in ["Draft", "Rejected"]:
            frappe.throw(
                f"Application cannot be submitted from status '{self.status}'."
            )

        self.validate()

        self.status = "Pending Review"
        self.submitted_on = now_datetime()

        self.create_or_link_member()

        self.save(ignore_permissions=True)

        return {
            "success": True,
            "application": self.name,
            "status": self.status,
            "member": self.member,
            "plan_price": self.plan_price
        }

    def create_or_link_member(self):
        existing = frappe.db.get_value(
            "Member",
            {"email": self.email},
            "name"
        )

        if existing:
            self.member = existing

            frappe.db.set_value(
                "Member",
                existing,
                {
                    "full_name": f"{self.first_name} {self.last_name}".strip(),
                    "phone": self.phone,
                    "address": self.address,
                    "date_of_birth": self.date_of_birth
                },
                update_modified=False
            )

            return existing

        member = frappe.get_doc({
            "doctype": "Member",
            "full_name": f"{self.first_name} {self.last_name}".strip(),
            "email": self.email,
            "phone": self.phone,
            "address": self.address,
            "date_of_birth": self.date_of_birth,
            "join_date": today(),
            "status": "Active"
        })

        member.insert(ignore_permissions=True)

        self.member = member.name

        return member.name

    def create_or_link_user(self):
        """
        Create or link the customer's Frappe Website User account.

        This is intentionally separate from the existing approval and
        billing logic. It only ensures that the approved customer can
        receive account setup instructions and log in to the website.
        """
        if not self.member:
            frappe.throw(
                "Member is required before creating the customer account."
            )

        email = (self.email or "").strip().lower()

        if not email:
            frappe.throw(
                "Customer email is required before creating the user account."
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

            if not user.enabled:
                user.enabled = 1
                user.save(ignore_permissions=True)

        else:
            user = frappe.get_doc({
                "doctype": "User",
                "email": email,
                "first_name": self.first_name,
                "last_name": self.last_name,
                "phone": self.phone,
                "mobile_no": self.phone,
                "user_type": "Website User",
                "enabled": 1,
                "send_welcome_email": 1
            })

            user.insert(ignore_permissions=True)

        frappe.db.set_value(
            "Member",
            self.member,
            "user",
            user.name,
            update_modified=False
        )

        return user.name

    def approve(self):
        if self.status != "Pending Review":
            frappe.throw(
                "Only applications in Pending Review can be approved."
            )

        if not self.member:
            self.create_or_link_member()

        self.create_or_link_user()

        self.reviewed_by = frappe.session.user
        self.status = "Approved"
        self.save(ignore_permissions=True)

        self.create_billing_records()

        self.status = "Payment Pending"
        self.save(ignore_permissions=True)

        return {
            "success": True,
            "application": self.name,
            "status": self.status,
            "sales_invoice": self.sales_invoice,
            "membership": self.membership,
            "space_access": self.space_access,
            "payment": self.payment
        }

    def create_billing_records(self):
        if self.sales_invoice:
            return

        if self.application_type == "Membership":
            self.create_membership_billing()
        elif self.application_type == "Solo Working":
            self.create_space_billing()
        else:
            frappe.throw("Invalid application type.")

    def create_membership_billing(self):
        if not self.member:
            frappe.throw("Member is required.")

        if not self.membership_plan:
            frappe.throw("Membership Plan is required.")

        existing_membership = frappe.db.exists(
            "Membership",
            {
                "member": self.member,
                "membership_plan": self.membership_plan,
                "status": ["in", ["Pending", "Active"]]
            }
        )

        if existing_membership:
            membership = frappe.get_doc(
                "Membership",
                existing_membership
            )
        else:
            membership = frappe.get_doc({
                "doctype": "Membership",
                "member": self.member,
                "membership_plan": self.membership_plan,
                "start_date": today(),
                "status": "Pending"
            })

            membership.insert(ignore_permissions=True)

            membership.flags.ignore_permissions = True
            membership.submit()

            membership.reload()

        if not membership.sales_invoice:
            frappe.throw(
                "Membership Sales Invoice was not created."
            )

        invoice = frappe.get_doc(
            "Sales Invoice",
            membership.sales_invoice
        )

        if invoice.docstatus == 0:
            invoice.flags.ignore_permissions = True
            invoice.submit()

        invoice.reload()

        if invoice.docstatus != 1:
            frappe.throw(
                "Membership Sales Invoice could not be submitted."
            )

        self.membership = membership.name
        self.sales_invoice = invoice.name

        self.db_set(
            "membership",
            membership.name,
            update_modified=False
        )

        self.db_set(
            "sales_invoice",
            invoice.name,
            update_modified=False
        )

    def create_space_billing(self):
        if not self.member:
            frappe.throw("Member is required.")

        if not self.space_plan:
            frappe.throw("Solo Working Plan is required.")

        plan = frappe.get_doc(
            "Space Plan",
            self.space_plan
        )

        if not plan.active:
            frappe.throw(
                f"Space Plan '{plan.plan_name}' is not active."
            )

        member = frappe.get_doc(
            "Member",
            self.member
        )

        invoice = frappe.get_doc({
            "doctype": "Sales Invoice",
            "member": self.member,
            "customer_name": member.full_name,
            "invoice_date": today(),
            "discount": 0,
            "tax": 0
        })

        invoice.append(
            "items",
            {
                "item_type": "Space",
                "description": f"Space Plan - {plan.plan_name}",
                "qty": 1,
                "rate": plan.price
            }
        )

        invoice.insert(ignore_permissions=True)

        invoice.flags.ignore_permissions = True
        invoice.submit()

        invoice.reload()

        if invoice.docstatus != 1:
            frappe.throw(
                "Solo Working Sales Invoice could not be submitted."
            )

        self.sales_invoice = invoice.name

        self.db_set(
            "sales_invoice",
            invoice.name,
            update_modified=False
        )

    def activate_after_payment(self, payment_name=None):
        if self.status == "Activated":
            return {
                "success": True,
                "application": self.name,
                "status": self.status,
                "membership": self.membership,
                "space_access": self.space_access,
                "sales_invoice": self.sales_invoice,
                "payment": self.payment
            }

        if self.status in ["Cancelled", "Rejected"]:
            frappe.throw(
                f"Application {self.name} cannot be activated from status '{self.status}'."
            )

        if not self.sales_invoice:
            frappe.throw(
                "Application does not have a Sales Invoice."
            )

        invoice = frappe.get_doc(
            "Sales Invoice",
            self.sales_invoice
        )

        if invoice.docstatus != 1:
            frappe.throw(
                "Sales Invoice must be submitted before activation."
            )

        if invoice.payment_status != "Paid":
            frappe.throw(
                "Application cannot be activated until the invoice is fully paid."
            )

        if payment_name:
            self.db_set(
                "payment",
                payment_name,
                update_modified=False
            )

        elif not self.payment:
            payment = frappe.db.get_value(
                "Payment",
                {
                    "sales_invoice": self.sales_invoice,
                    "docstatus": 1,
                    "payment_status": "Paid"
                },
                "name"
            )

            if payment:
                self.db_set(
                    "payment",
                    payment,
                    update_modified=False
                )

        if self.application_type == "Membership":
            self.activate_membership()

        elif self.application_type == "Solo Working":
            self.activate_space_access()

        else:
            frappe.throw("Invalid application type.")

        self.db_set(
            "status",
            "Activated",
            update_modified=False
        )

        return {
            "success": True,
            "application": self.name,
            "status": "Activated",
            "membership": self.membership,
            "space_access": self.space_access,
            "sales_invoice": self.sales_invoice,
            "payment": self.payment
        }

    def activate_membership(self):
        if not self.membership:
            self.create_membership_billing()

        membership = frappe.get_doc(
            "Membership",
            self.membership
        )

        membership.activate_after_payment()

        self.db_set(
            "membership",
            membership.name,
            update_modified=False
        )

    def activate_space_access(self):
        if self.space_access:
            existing = frappe.get_doc(
                "Space Access",
                self.space_access
            )

            if existing.status == "Active":
                return

            if existing.status == "Cancelled":
                frappe.throw(
                    "Existing Space Access is cancelled."
                )

        plan = frappe.get_doc(
            "Space Plan",
            self.space_plan
        )

        start_date = getdate(today())

        if plan.billing_period == "Monthly":
            end_date = add_months(start_date, 1)
        else:
            end_date = start_date

        existing_access = frappe.db.exists(
            "Space Access",
            {
                "member": self.member,
                "space_plan": self.space_plan,
                "sales_invoice": self.sales_invoice,
                "status": ["in", ["Active", "Expired"]]
            }
        )

        if existing_access:
            access = frappe.get_doc(
                "Space Access",
                existing_access
            )
        else:
            access = frappe.get_doc({
                "doctype": "Space Access",
                "member": self.member,
                "space_plan": self.space_plan,
                "sales_invoice": self.sales_invoice,
                "payment": self.payment,
                "start_date": start_date,
                "end_date": end_date,
                "status": "Active"
            })

            access.insert(ignore_permissions=True)

        if self.payment and access.payment != self.payment:
            access.db_set(
                "payment",
                self.payment,
                update_modified=False
            )

        self.db_set(
            "space_access",
            access.name,
            update_modified=False
        )

    def reject(self, notes=None):
        if self.status not in ["Pending Review", "Approved"]:
            frappe.throw(
                "This application cannot be rejected in its current status."
            )

        self.status = "Rejected"
        self.reviewed_by = frappe.session.user

        if notes:
            self.review_notes = notes

        self.save(ignore_permissions=True)

        return {
            "success": True,
            "application": self.name,
            "status": self.status
        }
