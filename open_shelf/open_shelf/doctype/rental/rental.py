import frappe
from frappe.model.document import Document


class Rental(Document):

    def validate(self):
        # -----------------------------
        # Basic validation
        # -----------------------------
        if not self.book:
            frappe.throw("Please select a Book.")

        if not self.rental_plan:
            frappe.throw("Please select a Rental Plan.")

        if self.quantity <= 0:
            frappe.throw("Quantity must be greater than 0.")

        # -----------------------------
        # Check Book
        # -----------------------------
        book = frappe.get_doc("Book", self.book)

        if not book.rental_allowed:
            frappe.throw(
                f"'{book.book_title}' is not available for rental."
            )

        # Only check available stock for an active rental.
        if self.status != "Returned":
            if book.available_copies < self.quantity:
                frappe.throw(
                    f"Only {book.available_copies} copies of "
                    f"{book.book_title} are currently available."
                )

        # -----------------------------
        # Member membership validation
        # -----------------------------
        if self.member:
            today = frappe.utils.today()

            active_membership = frappe.db.exists(
                "Membership",
                {
                    "member": self.member,
                    "status": "Active",
                    "start_date": ["<=", today],
                    "end_date": [">=", today],
                },
            )

            if not active_membership:
                frappe.throw(
                    "This member does not have an active membership."
                )

        # -----------------------------
        # Rental date
        # -----------------------------
        if not self.rental_date:
            self.rental_date = frappe.utils.today()

        # -----------------------------
        # Due date
        # -----------------------------
        plan = frappe.get_doc(
            "Rental Plan",
            self.rental_plan
        )

        self.due_date = frappe.utils.add_days(
            self.rental_date,
            plan.duration_days
        )

        # -----------------------------
        # Default status
        # -----------------------------
        if not self.status:
            self.status = "Rented"

        # -----------------------------
        # Return date
        # -----------------------------
        if self.status == "Returned" and not self.return_date:
            self.return_date = frappe.utils.today()

    # ============================================================
    # RENTAL SUBMISSION
    # ============================================================

    def on_submit(self):

        if self.status != "Rented":
            return

        # Prevent duplicate Rental Out transactions.
        existing = frappe.db.exists(
            "Inventory Transaction",
            {
                "reference_doctype": "Rental",
                "reference_name": self.name,
                "transaction_type": "Rental Out",
                "docstatus": 1,
            },
        )

        if existing:
            return

        # Inventory Transaction is responsible for changing stock.
        tx = frappe.get_doc({
            "doctype": "Inventory Transaction",
            "book": self.book,
            "transaction_type": "Rental Out",
            "quantity": self.quantity,
            "transaction_date": self.rental_date,
            "reference_doctype": "Rental",
            "reference_name": self.name,
            "notes": (
                f"Rental of {self.quantity} copy/copies."
            ),
        })

        tx.insert(ignore_permissions=True)
        tx.submit()

    # ============================================================
    # RETURN AFTER SUBMISSION
    # ============================================================

    def on_update_after_submit(self):

        # Only process Returned rentals.
        if self.status != "Returned":
            return

        old_rental = self.get_doc_before_save()

        if not old_rental:
            return

        # Only process:
        #
        # Rented -> Returned
        #
        if old_rental.status != "Rented":
            return

        # Prevent duplicate Rental Return transactions.
        existing = frappe.db.exists(
            "Inventory Transaction",
            {
                "reference_doctype": "Rental",
                "reference_name": self.name,
                "transaction_type": "Rental Return",
                "docstatus": 1,
            },
        )

        if existing:
            return

        # Set return date before creating transaction.
        if not self.return_date:
            self.return_date = frappe.utils.today()

            frappe.db.set_value(
                "Rental",
                self.name,
                "return_date",
                self.return_date,
            )

        # Inventory Transaction restores the stock.
        tx = frappe.get_doc({
            "doctype": "Inventory Transaction",
            "book": self.book,
            "transaction_type": "Rental Return",
            "quantity": self.quantity,
            "transaction_date": self.return_date,
            "reference_doctype": "Rental",
            "reference_name": self.name,
            "notes": (
                f"Return of {self.quantity} copy/copies."
            ),
        })

        tx.insert(ignore_permissions=True)
        tx.submit()

    # ============================================================
    # RENTAL CANCELLATION
    # ============================================================

    def on_cancel(self):

        # A returned rental should not restore stock again.
        if self.status != "Rented":
            return

        # Prevent duplicate restoration transactions.
        existing = frappe.db.exists(
            "Inventory Transaction",
            {
                "reference_doctype": "Rental",
                "reference_name": self.name,
                "transaction_type": "Rental Return",
                "docstatus": 1,
            },
        )

        if existing:
            return

        # Restore stock through Inventory Transaction.
        tx = frappe.get_doc({
            "doctype": "Inventory Transaction",
            "book": self.book,
            "transaction_type": "Rental Return",
            "quantity": self.quantity,
            "transaction_date": frappe.utils.today(),
            "reference_doctype": "Rental",
            "reference_name": self.name,
            "notes": (
                f"Stock restored after cancelling "
                f"rental {self.name}."
            ),
        })

        tx.insert(ignore_permissions=True)
        tx.submit()
