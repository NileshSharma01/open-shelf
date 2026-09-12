import frappe
from frappe.model.document import Document


class Book(Document):
    def validate(self):
        if self.total_copies < 0:
            frappe.throw("Total Copies cannot be negative.")

        if self.available_copies < 0:
            frappe.throw("Available Copies cannot be negative.")

        if self.available_copies > self.total_copies:
            frappe.throw(
                "Available Copies cannot be greater than Total Copies."
            )
