import frappe
from frappe.model.document import Document
from frappe.utils import add_months, getdate, today


class Membership(Document):

    def validate(self):
        if not self.member:
            frappe.throw("Please select a Member.")

        if not self.membership_plan:
            frappe.throw("Please select a Membership Plan.")

        plan = frappe.get_doc(
            "Membership Plan",
            self.membership_plan
        )

        if not plan.active:
            frappe.throw(
                f"Membership Plan '{plan.plan_name}' is not active."
            )

        if not self.start_date:
            self.start_date = today()

        if not self.end_date:
            self.end_date = add_months(
                self.start_date,
                plan.duration_months
            )

        if getdate(self.end_date) < getdate(self.start_date):
            frappe.throw(
                "End Date cannot be before Start Date."
            )

        if self.status == "Active":
            self.validate_no_overlapping_membership()

    def validate_no_overlapping_membership(self):
        existing = frappe.get_all(
            "Membership",
            filters={
                "member": self.member,
                "status": "Active",
                "name": ["!=", self.name],
                "start_date": ["<=", self.end_date],
                "end_date": [">=", self.start_date],
            },
            fields=[
                "name",
                "start_date",
                "end_date"
            ],
            limit=1,
        )

        if existing:
            frappe.throw(
                f"Member already has an overlapping active membership "
                f"({existing[0].name}) from "
                f"{existing[0].start_date} to "
                f"{existing[0].end_date}."
            )

    def on_submit(self):
        if self.status != "Pending":
            frappe.throw(
                "A new membership must be submitted with status Pending."
            )

        self.create_sales_invoice()

    def create_sales_invoice(self):

        if self.sales_invoice:
            return

        plan = frappe.get_doc(
            "Membership Plan",
            self.membership_plan
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

        invoice.append("items", {
            "item_type": "Membership",
            "description": f"Membership - {plan.plan_name}",
            "qty": 1,
            "rate": plan.price
        })

        invoice.insert(ignore_permissions=True)

        self.db_set(
            "sales_invoice",
            invoice.name,
            update_modified=False
        )

    def activate_after_payment(self):

        if self.status == "Active":
            return

        if self.status in ["Cancelled", "Expired"]:
            frappe.throw(
                f"Membership {self.name} cannot be activated because "
                f"its status is {self.status}."
            )

        if not self.sales_invoice:
            frappe.throw(
                "Membership does not have a Sales Invoice."
            )

        invoice = frappe.get_doc(
            "Sales Invoice",
            self.sales_invoice
        )

        if invoice.docstatus != 1:
            frappe.throw(
                "The membership Sales Invoice must be submitted "
                "before activating the membership."
            )

        if invoice.payment_status != "Paid":
            frappe.throw(
                "Membership cannot be activated until the invoice "
                "is fully paid."
            )

        self.status = "Active"
        self.save(ignore_permissions=True)
