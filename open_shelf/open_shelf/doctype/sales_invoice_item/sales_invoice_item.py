import frappe
from frappe.model.document import Document


class SalesInvoiceItem(Document):

    def validate(self):
        if not self.book:
            frappe.throw("Please select a Book.")

        if self.qty <= 0:
            frappe.throw("Quantity must be greater than 0.")

        if self.rate < 0:
            frappe.throw("Rate cannot be negative.")

        self.amount = self.qty * self.rate
