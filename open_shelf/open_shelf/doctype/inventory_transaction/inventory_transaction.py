import frappe
from frappe.model.document import Document


class InventoryTransaction(Document):

    def validate(self):
        if self.quantity <= 0:
            frappe.throw("Quantity must be greater than 0.")

        if not self.book:
            frappe.throw("Please select a Book.")

    def on_submit(self):
        self.update_stock()

    def on_cancel(self):
        self.update_stock(reverse=True)

    def update_stock(self, reverse=False):
        book = frappe.get_doc("Book", self.book)

        if self.transaction_type in ["Purchase", "Rental Return"]:
            available_change = self.quantity
            total_change = self.quantity if self.transaction_type == "Purchase" else 0

        elif self.transaction_type in ["Sale", "Rental Out"]:
            available_change = -self.quantity
            total_change = -self.quantity if self.transaction_type == "Sale" else 0

        elif self.transaction_type == "Adjustment":
            frappe.throw(
                "Adjustment transactions are not implemented yet."
            )

        else:
            frappe.throw(
                f"Unknown transaction type: {self.transaction_type}"
            )

        if reverse:
            available_change = -available_change
            total_change = -total_change

        new_available = book.available_copies + available_change
        new_total = book.total_copies + total_change

        if new_available < 0:
            frappe.throw(
                f"Not enough available stock for {book.book_title}."
            )

        if new_total < 0:
            frappe.throw(
                f"Total stock cannot be negative for {book.book_title}."
            )

        if new_available > new_total:
            frappe.throw(
                f"Available copies cannot exceed total copies for "
                f"{book.book_title}."
            )

        book.available_copies = new_available
        book.total_copies = new_total

        book.save(ignore_permissions=True)
