import frappe


@frappe.whitelist(allow_guest=True)
def get_current_user():
    """
    Return the current Frappe session user.

    This endpoint is public so the frontend can determine
    whether the visitor is logged in before opening the
    rental modal.
    """

    return {
        "logged_in": frappe.session.user != "Guest",
        "user": frappe.session.user,
    }


@frappe.whitelist(allow_guest=True)
def get_rental_plans():
    """
    Return all available rental plans for the frontend.
    """

    return frappe.get_all(
        "Rental Plan",
        fields=[
            "name",
            "duration_days",
        ],
        order_by="name asc",
        limit_page_length=100,
    )


@frappe.whitelist()
def create_rental(book, rental_plan, quantity=1):
    """
    Create and submit a Rental for the currently logged-in user.
    """

    # ---------------------------------------------------------
    # LOGIN CHECK
    # ---------------------------------------------------------

    if frappe.session.user == "Guest":
        frappe.throw(
            "Please log in before renting a book."
        )

    # ---------------------------------------------------------
    # QUANTITY
    # ---------------------------------------------------------

    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        frappe.throw("Invalid quantity.")

    if quantity <= 0:
        frappe.throw(
            "Quantity must be greater than 0."
        )

    # ---------------------------------------------------------
    # BOOK
    # ---------------------------------------------------------

    if not book:
        frappe.throw(
            "Please select a book."
        )

    book_doc = frappe.get_doc(
        "Book",
        book
    )

    if not book_doc.rental_allowed:
        frappe.throw(
            f"'{book_doc.book_title}' is not available for rental."
        )

    if book_doc.available_copies < quantity:
        frappe.throw(
            f"Only {book_doc.available_copies} copies of "
            f"{book_doc.book_title} are currently available."
        )

    # ---------------------------------------------------------
    # RENTAL PLAN
    # ---------------------------------------------------------

    if not rental_plan:
        frappe.throw(
            "Please select a rental plan."
        )

    plan = frappe.get_doc(
        "Rental Plan",
        rental_plan
    )

    if not plan.duration_days or plan.duration_days <= 0:
        frappe.throw(
            "The selected rental plan has an invalid duration."
        )

    # ---------------------------------------------------------
    # MEMBER
    # ---------------------------------------------------------

    member = frappe.db.get_value(
        "Member",
        {
            "email": frappe.session.user
        },
        "name",
    )

    if not member:
        frappe.throw(
            "No Member account is linked to your login. "
            "Please contact Open Shelf."
        )

    # ---------------------------------------------------------
    # CREATE RENTAL
    # ---------------------------------------------------------

    rental = frappe.get_doc({
        "doctype": "Rental",
        "book": book,
        "member": member,
        "rental_plan": rental_plan,
        "quantity": quantity,
        "rental_date": frappe.utils.today(),
        "status": "Rented",
    })

    rental.insert(
        ignore_permissions=True
    )

    rental.submit()

    # ---------------------------------------------------------
    # RESPONSE
    # ---------------------------------------------------------

    return {
        "success": True,
        "rental": rental.name,
        "book": book_doc.book_title,
        "quantity": quantity,
        "rental_plan": rental_plan,
        "rental_date": rental.rental_date,
        "due_date": rental.due_date,
        "status": rental.status,
    }
