import frappe
from frappe.model.document import Document


class Payment(Document):

    def validate(self):
        if self.amount is None or self.amount <= 0:
            frappe.throw("Payment amount must be greater than zero.")

        if self.payment_method == "Razorpay":
            if self.payment_status not in ["Initiated", "Paid", "Failed", "Cancelled"]:
                frappe.throw("Invalid Razorpay payment status.")

            if self.docstatus == 1 and self.payment_status != "Paid":
                frappe.throw(
                    "A Razorpay payment can only be submitted after successful verification."
                )

        if self.sales_invoice:
            invoice = frappe.get_doc("Sales Invoice", self.sales_invoice)

            if invoice.docstatus != 1:
                frappe.throw("Sales Invoice must be submitted before recording payment.")

            paid_amount = frappe.db.sql(
                """
                SELECT COALESCE(SUM(amount), 0)
                FROM `tabPayment`
                WHERE sales_invoice = %s
                  AND docstatus = 1
                  AND payment_status = 'Paid'
                  AND name != %s
                """,
                (self.sales_invoice, self.name),
            )[0][0]

            remaining = invoice.grand_total - paid_amount

            if self.amount > remaining:
                frappe.throw(
                    f"Payment amount cannot exceed the remaining invoice amount of {remaining:.2f}."
                )

    def on_submit(self):
        self.update_invoice_payment_status()
        self.activate_customer_application()

    def activate_customer_application(self):
        if not self.sales_invoice:
            return

        invoice = frappe.get_doc(
            "Sales Invoice",
            self.sales_invoice
        )

        if invoice.payment_status != "Paid":
            return

        application_name = frappe.db.get_value(
            "Customer Application",
            {
                "sales_invoice": self.sales_invoice,
                "status": [
                    "in",
                    [
                        "Payment Pending",
                        "Paid"
                    ]
                ]
            },
            "name"
        )

        if not application_name:
            return

        application = frappe.get_doc(
            "Customer Application",
            application_name
        )

        application.db_set(
            "status",
            "Paid",
            update_modified=False
        )

        application.db_set(
            "payment",
            self.name,
            update_modified=False
        )

        application.activate_after_payment(
            payment_name=self.name
        )


    def on_cancel(self):
        self.update_invoice_payment_status()

    def update_invoice_payment_status(self):
        if not self.sales_invoice:
            return

        invoice = frappe.get_doc("Sales Invoice", self.sales_invoice)

        paid_amount = frappe.db.sql(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM `tabPayment`
            WHERE sales_invoice = %s
              AND docstatus = 1
              AND payment_status = 'Paid'
            """,
            self.sales_invoice,
        )[0][0]

        if paid_amount <= 0:
            status = "Unpaid"
        elif paid_amount < invoice.grand_total:
            status = "Partly Paid"
        else:
            status = "Paid"

        frappe.db.set_value(
            "Sales Invoice",
            self.sales_invoice,
            "payment_status",
            status,
        )
