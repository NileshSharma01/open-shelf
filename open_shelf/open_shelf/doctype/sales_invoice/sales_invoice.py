import frappe
from frappe.model.document import Document


class SalesInvoice(Document):

    def validate(self):
        subtotal = 0

        for item in self.items:
            if item.qty <= 0:
                frappe.throw("Quantity must be greater than 0.")

            if item.rate < 0:
                frappe.throw("Rate cannot be negative.")

            item.amount = item.qty * item.rate

            subtotal += item.amount

        self.subtotal = subtotal

        discount = self.discount or 0
        tax = self.tax or 0

        self.grand_total = subtotal - discount + tax

        if self.grand_total < 0:
            frappe.throw("Grand Total cannot be negative.")

    def on_submit(self):
        self.create_sale_transactions()

    def on_cancel(self):
        self.cancel_sale_transactions()

    def create_sale_transactions(self):
        for item in self.items:

            if item.item_type != "Book":
                continue

            if not item.book:
                frappe.throw(
                    "Book is required for a Book invoice item."
                )

            transaction = frappe.get_doc({
                "doctype": "Inventory Transaction",
                "book": item.book,
                "transaction_type": "Sale",
                "quantity": item.qty,
                "transaction_date": self.invoice_date,
                "reference_doctype": "Sales Invoice",
                "reference_name": self.name
            })

            transaction.insert(ignore_permissions=True)
            transaction.submit()

    def cancel_sale_transactions(self):
        transactions = frappe.get_all(
            "Inventory Transaction",
            filters={
                "reference_doctype": "Sales Invoice",
                "reference_name": self.name,
                "transaction_type": "Sale",
                "docstatus": 1
            },
            pluck="name"
        )

        for transaction_name in transactions:
            transaction = frappe.get_doc(
                "Inventory Transaction",
                transaction_name
            )

            transaction.cancel()
