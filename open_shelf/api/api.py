import frappe
import razorpay

from frappe.utils import today, add_days, getdate, add_months


# ============================================================
# BOOK / CATALOGUE
# ============================================================

# Maximum number of books visible to guests and users who do not
# currently have an active Open Shelf membership.
PUBLIC_CATALOGUE_LIMIT = 12


def _has_active_membership_for_catalogue():
    """
    Return True only when the current logged-in user has:
      1. an active Open Shelf Member account, and
      2. an active Membership whose dates include today.

    This helper never throws for normal non-member users.
    """

    if frappe.session.user == "Guest":
        return False

    member_name = frappe.db.get_value(
        "Member",
        {"user": frappe.session.user},
        "name",
    )

    if not member_name:
        return False

    member_status = frappe.db.get_value(
        "Member",
        member_name,
        "status",
    )

    if member_status != "Active":
        return False

    current_date = getdate(today())

    active_membership = frappe.db.exists(
        "Membership",
        {
            "member": member_name,
            "status": "Active",
            "start_date": ["<=", current_date],
            "end_date": [">=", current_date],
        },
    )

    return bool(active_membership)


def _get_catalogue_access():
    """
    Determine the catalogue access level for the current session.

    Guests and non-members receive the limited public catalogue.
    Active members receive the complete catalogue.
    """

    if _has_active_membership_for_catalogue():
        return {
            "is_member": True,
            "limit": None,
        }

    return {
        "is_member": False,
        "limit": PUBLIC_CATALOGUE_LIMIT,
    }


@frappe.whitelist(allow_guest=True)
def get_books(search=None, category=None, author=None):
    access = _get_catalogue_access()

    filters = {}

    # Category and author filters use the DocType record name/ID.
    # Resolve human-readable names to IDs as a fallback so the
    # catalogue works with either value coming from the frontend.

    if category:
        category = str(category).strip()

        category_id = frappe.db.get_value(
            "Category",
            {"category_name": category},
            "name",
        )

        filters["category"] = category_id or category

    if author:
        author = str(author).strip()

        author_id = frappe.db.get_value(
            "Author",
            {"author_name": author},
            "name",
        )

        filters["author"] = author_id or author

    books = frappe.get_all(
        "Book",
        filters=filters,
        fields=[
            "name",
            "book_title",
            "isbn",
            "author",
            "publisher",
            "category",
            "description",
            "publication_year",
            "language",
            "edition",
            "total_copies",
            "available_copies",
            "selling_price",
            "rental_allowed",
            "image",
        ],
        order_by="book_title asc",
        limit_page_length=(
            access["limit"]
            if access["limit"] is not None
            else 0
        ),
    )

    if search:
        search = str(search).strip().lower()

        if search:
            books = [
                book
                for book in books
                if search in (book.book_title or "").lower()
                or search in (book.isbn or "").lower()
            ]

    author_ids = {book.author for book in books if book.author}
    publisher_ids = {book.publisher for book in books if book.publisher}
    category_ids = {book.category for book in books if book.category}

    author_names = {}
    publisher_names = {}
    category_names = {}

    if author_ids:
        author_names = {
            row.name: row.author_name
            for row in frappe.get_all(
                "Author",
                filters={"name": ["in", list(author_ids)]},
                fields=["name", "author_name"],
            )
        }

    if publisher_ids:
        publisher_names = {
            row.name: row.publisher_name
            for row in frappe.get_all(
                "Publisher",
                filters={"name": ["in", list(publisher_ids)]},
                fields=["name", "publisher_name"],
            )
        }

    if category_ids:
        category_names = {
            row.name: row.category_name
            for row in frappe.get_all(
                "Category",
                filters={"name": ["in", list(category_ids)]},
                fields=["name", "category_name"],
            )
        }

    for book in books:
        author_id = book.author
        publisher_id = book.publisher
        category_id = book.category

        book.author_id = author_id
        book.publisher_id = publisher_id
        book.category_id = category_id

        book.author = author_names.get(author_id, author_id or "")
        book.publisher = publisher_names.get(
            publisher_id,
            publisher_id or "",
        )
        book.category = category_names.get(
            category_id,
            category_id or "",
        )

    return books


@frappe.whitelist(allow_guest=True)
def get_book(book):
    if not book:
        frappe.throw("Book is required.")

    access = _get_catalogue_access()

    if not access["is_member"]:
        public_books = frappe.get_all(
            "Book",
            fields=["name"],
            order_by="book_title asc",
            limit_page_length=PUBLIC_CATALOGUE_LIMIT,
        )

        allowed_books = {
            row.name
            for row in public_books
        }

        if book not in allowed_books:
            frappe.throw(
                "This book is not available in the public catalogue."
            )

    book_doc = frappe.get_doc("Book", book).as_dict()

    author_id = book_doc.get("author")
    publisher_id = book_doc.get("publisher")
    category_id = book_doc.get("category")

    if author_id:
        book_doc["author_id"] = author_id
        book_doc["author"] = (
            frappe.db.get_value(
                "Author",
                author_id,
                "author_name",
            )
            or author_id
        )

    if publisher_id:
        book_doc["publisher_id"] = publisher_id
        book_doc["publisher"] = (
            frappe.db.get_value(
                "Publisher",
                publisher_id,
                "publisher_name",
            )
            or publisher_id
        )

    if category_id:
        book_doc["category_id"] = category_id
        book_doc["category"] = (
            frappe.db.get_value(
                "Category",
                category_id,
                "category_name",
            )
            or category_id
        )

    return book_doc


# ============================================================
# CATEGORIES
# ============================================================

@frappe.whitelist(allow_guest=True)
def get_categories():
    return frappe.get_all(
        "Category",
        fields=[
            "name",
            "category_name",
        ],
        order_by="category_name asc",
    )


# ============================================================
# AUTHORS
# ============================================================

@frappe.whitelist(allow_guest=True)
def get_authors():
    return frappe.get_all(
        "Author",
        fields=[
            "name",
            "author_name",
        ],
        order_by="author_name asc",
    )


# ============================================================
# MEMBERSHIP PLANS
# ============================================================

@frappe.whitelist()
def debug_current_member_status():
    """
    Diagnostic helper for the currently logged-in Frappe user.
    """

    if frappe.session.user == "Guest":
        return {
            "user": "Guest",
            "member": None,
            "memberships": [],
        }

    member = frappe.db.get_value(
        "Member",
        {"user": frappe.session.user},
        ["name", "status"],
        as_dict=True,
    )

    memberships = []

    if member:
        memberships = frappe.get_all(
            "Membership",
            filters={"member": member.name},
            fields=[
                "name",
                "membership_plan",
                "status",
                "start_date",
                "end_date",
            ],
            order_by="start_date desc",
        )

    return {
        "user": frappe.session.user,
        "member": member,
        "memberships": memberships,
    }


@frappe.whitelist()
def get_open_shelf_csrf_token():
    """
    Return the current Frappe CSRF token for the Open Shelf frontend.
    """
    return frappe.sessions.get_csrf_token()


@frappe.whitelist()
def get_membership_plans():
    """
    Return active membership plans for the public website.
    """

    return frappe.get_all(
        "Membership Plan",
        filters={
            "active": 1,
        },
        fields=[
            "name",
            "plan_name",
            "duration_months",
            "price",
            "max_hours_per_day",
            "additional_hour_fee",
            "wifi_included",
            "cafe_voucher_amount",
            "description",
            "active",
        ],
        order_by="price asc",
    )


# ============================================================
# MEMBER
# ============================================================

def _get_current_member():
    if frappe.session.user == "Guest":
        frappe.throw("Please login to continue.")

    member_name = frappe.db.get_value(
        "Member",
        {"user": frappe.session.user},
        "name",
    )

    # Free Website Users are valid Open Shelf accounts but are not
    # members. Returning None allows the customer profile to load
    # without creating a fake Member record.
    if not member_name:
        return None

    member_doc = frappe.get_doc(
        "Member",
        member_name
    )

    if member_doc.status != "Active":
        frappe.throw(
            "Your Open Shelf member account is not active."
        )

    return member_doc


@frappe.whitelist()
def get_member():
    """
    Return the current Open Shelf account.

    Free Website Users are valid accounts but do not have a Member
    record yet. Members receive their normal Member information.
    """

    if frappe.session.user == "Guest":
        frappe.throw("Please login to continue.")

    user = frappe.get_doc(
        "User",
        frappe.session.user
    )

    member_name = frappe.db.get_value(
        "Member",
        {"user": frappe.session.user},
        "name"
    )

    # Free Website User
    if not member_name:
        return {
            "is_free_account": True,
            "is_member": False,
            "name": None,
            "member_id": None,
            "full_name": (
                user.full_name
                or user.first_name
                or frappe.session.user
            ),
            "email": user.email or frappe.session.user,
            "phone": user.phone or user.mobile_no or "",
            "status": "Free Account",
            "user": frappe.session.user,
            "join_date": None,
        }

    # Existing Open Shelf Member
    member_doc = frappe.get_doc(
        "Member",
        member_name
    )

    if member_doc.status != "Active":
        frappe.throw(
            "Your Open Shelf member account is not active."
        )

    data = member_doc.as_dict()
    data["is_free_account"] = False
    data["is_member"] = True
    data["user"] = frappe.session.user

    return data

@frappe.whitelist()
def create_membership(
    membership_plan,
    start_date=None,
):
    """
    Create a new Pending membership for the logged-in member.

    Workflow:

    1. Resolve Member from the authenticated Frappe User.
    2. Create Membership as Pending.
    3. Submit Membership.
    4. Membership creates its Sales Invoice.
    5. Submit the Sales Invoice.
    6. Razorpay payment is collected separately.
    7. Successful verified payment activates the membership.
    """

    if not membership_plan:
        frappe.throw(
            "Membership Plan is required."
        )

    member_doc = _get_current_member()

    plan = frappe.get_doc(
        "Membership Plan",
        membership_plan,
    )

    if not plan.active:
        frappe.throw(
            f"Membership Plan '{plan.plan_name}' is not active."
        )

    membership = frappe.get_doc({
        "doctype": "Membership",
        "member": member_doc.name,
        "membership_plan": membership_plan,
        "start_date": start_date or today(),
        "status": "Pending",
    })

    membership.insert(
        ignore_permissions=True
    )

    membership.flags.ignore_permissions = True
    membership.submit()

    membership.reload()

    if not membership.sales_invoice:
        frappe.throw(
            "Membership Sales Invoice was not created."
        )

    invoice = frappe.get_doc(
        "Sales Invoice",
        membership.sales_invoice,
    )

    # The membership controller creates the invoice as Draft.
    # Submit it before payment/Razorpay processing.
    if invoice.docstatus == 0:
        invoice.flags.ignore_permissions = True
        invoice.submit()

    invoice.reload()

    if invoice.docstatus != 1:
        frappe.throw(
            "Membership Sales Invoice could not be submitted."
        )

    frappe.db.commit()

    return {
        "success": True,
        "membership": membership.name,
        "member": membership.member,
        "membership_plan": membership.membership_plan,
        "plan_name": plan.plan_name,
        "start_date": str(membership.start_date),
        "end_date": str(membership.end_date),
        "status": membership.status,
        "sales_invoice": membership.sales_invoice,
        "invoice_status": invoice.docstatus,
        "payment_status": invoice.payment_status,
        "amount": invoice.grand_total,
    }


@frappe.whitelist()
def get_membership(membership):
    if not membership:
        frappe.throw("Membership is required.")

    member_doc = _get_current_member()

    membership_doc = frappe.get_doc(
        "Membership",
        membership,
    )

    if membership_doc.member != member_doc.name:
        frappe.throw(
            "You are not authorized to access this membership."
        )

    return membership_doc.as_dict()


@frappe.whitelist()
def get_member_memberships():
    member_doc = _get_current_member()

    return frappe.get_all(
        "Membership",
        filters={
            "member": member_doc.name,
        },
        fields=[
            "name",
            "membership_plan",
            "sales_invoice",
            "start_date",
            "end_date",
            "status",
        ],
        order_by="start_date desc",
    )


@frappe.whitelist()
def get_active_membership():
    member_doc = _get_current_member()

    memberships = frappe.get_all(
        "Membership",
        filters={
            "member": member_doc.name,
            "status": "Active",
            "start_date": ["<=", today()],
            "end_date": [">=", today()],
        },
        fields=[
            "name",
            "membership_plan",
            "sales_invoice",
            "start_date",
            "end_date",
            "status",
        ],
        order_by="end_date desc",
        limit=1,
    )

    return memberships[0] if memberships else None


# ============================================================
# RENTAL PLANS
# ============================================================

@frappe.whitelist()
def get_rental_plans():
    """
    Return active rental plans for the customer website.
    """

    return frappe.get_all(
        "Rental Plan",
        filters={
            "active": 1,
        },
        fields=[
            "name",
            "plan_name",
            "duration_days",
            "price",
            "description",
            "active",
        ],
        order_by="price asc",
    )


# ============================================================
# RENTALS
# ============================================================

@frappe.whitelist()
def get_member_rentals():
    """
    Return all rentals belonging to the currently logged-in
    Open Shelf member.

    The Member ID is NEVER accepted from the browser.
    The Member is determined from the authenticated Frappe User.
    """

    member_doc = _get_current_member()

    return frappe.get_all(
        "Rental",
        filters={
            "member": member_doc.name,
        },
        fields=[
            "name",
            "book",
            "rental_plan",
            "quantity",
            "rental_date",
            "due_date",
            "return_date",
            "status",
        ],
        order_by="rental_date desc",
    )


def _get_current_active_member():
    """
    Return the currently logged-in Open Shelf Member only when
    that Member has a currently active Membership.
    """

    member_doc = _get_current_member()

    current_date = getdate(today())

    active_membership = frappe.db.exists(
        "Membership",
        {
            "member": member_doc.name,
            "status": "Active",
            "start_date": ["<=", current_date],
            "end_date": [">=", current_date],
        },
    )

    if not active_membership:
        frappe.throw(
            "An active Open Shelf membership is required to rent books."
        )

    return member_doc


@frappe.whitelist()
def check_rental_eligibility():
    """
    Return the rental eligibility state for the current visitor.

    This endpoint intentionally does not throw for normal
    non-member states because the frontend needs to distinguish
    Guest, Member-without-membership, and Active-Member.
    """

    if frappe.session.user == "Guest":
        return {
            "logged_in": False,
            "eligible": False,
            "reason": "login_required",
        }

    member_name = frappe.db.get_value(
        "Member",
        {"user": frappe.session.user},
        "name",
    )

    if not member_name:
        return {
            "logged_in": True,
            "eligible": False,
            "reason": "membership_required",
        }

    member_doc = frappe.get_doc(
        "Member",
        member_name,
    )

    if member_doc.status != "Active":
        return {
            "logged_in": True,
            "eligible": False,
            "reason": "membership_required",
        }

    current_date = getdate(today())

    active_membership = frappe.db.exists(
        "Membership",
        {
            "member": member_doc.name,
            "status": "Active",
            "start_date": ["<=", current_date],
            "end_date": [">=", current_date],
        },
    )

    if not active_membership:
        return {
            "logged_in": True,
            "eligible": False,
            "reason": "membership_required",
        }

    return {
        "logged_in": True,
        "eligible": True,
        "reason": "eligible",
    }


@frappe.whitelist()
def create_rental(
    book,
    rental_plan,
    quantity=1,
):
    """
    Create and submit a rental for the currently logged-in member.

    The Member is determined from the authenticated Frappe User.
    Inventory is changed only by Rental.on_submit().
    """

    if not book:
        frappe.throw(
            "Book is required."
        )

    if not rental_plan:
        frappe.throw(
            "Rental Plan is required."
        )

    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        frappe.throw(
            "Quantity must be a valid number."
        )

    if quantity <= 0:
        frappe.throw(
            "Quantity must be greater than 0."
        )

    # --------------------------------------------------------
    # Identify logged-in member
    # --------------------------------------------------------

    member_doc = _get_current_active_member()

    # --------------------------------------------------------
    # Validate book
    # --------------------------------------------------------

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
            f"Only {book_doc.available_copies} copies "
            f"of '{book_doc.book_title}' are available."
        )

    # --------------------------------------------------------
    # Validate rental plan
    # --------------------------------------------------------

    plan = frappe.get_doc(
        "Rental Plan",
        rental_plan
    )

    if not plan.duration_days:
        frappe.throw(
            "Rental Plan must have a valid duration."
        )

    if plan.duration_days <= 0:
        frappe.throw(
            "Rental Plan duration must be greater than 0 days."
        )

    # --------------------------------------------------------
    # Rental dates
    # --------------------------------------------------------

    rental_date = getdate(
        today()
    )

    due_date = add_days(
        rental_date,
        plan.duration_days
    )

    # --------------------------------------------------------
    # Create Rental
    # --------------------------------------------------------

    rental = frappe.get_doc({
        "doctype": "Rental",
        "book": book,
        "member": member_doc.name,
        "rental_plan": rental_plan,
        "quantity": quantity,
        "rental_date": rental_date,
        "due_date": due_date,
        "status": "Rented",
    })

    rental.insert(
        ignore_permissions=True
    )

    # Rental.on_submit() is the ONLY place that creates
    # the Rental Out inventory transaction.
    rental.flags.ignore_permissions = True
    rental.submit()

    frappe.db.commit()

    rental.reload()

    return {
        "success": True,
        "rental": rental.name,
        "member": member_doc.name,
        "book": book,
        "quantity": quantity,
        "rental_date": str(rental.rental_date),
        "due_date": str(rental.due_date),
        "status": rental.status,
        "docstatus": rental.docstatus,
    }


@frappe.whitelist()
def return_rental(
    rental,
):
    """
    Return a rental belonging to the currently logged-in member.

    The rental must be submitted and currently active.
    Stock restoration is handled by Rental.on_update_after_submit().
    """

    if not rental:
        frappe.throw(
            "Rental is required."
        )

    # --------------------------------------------------------
    # Identify logged-in member
    # --------------------------------------------------------

    member_doc = _get_current_member()

    # --------------------------------------------------------
    # Load rental
    # --------------------------------------------------------

    rental_doc = frappe.get_doc(
        "Rental",
        rental
    )

    # --------------------------------------------------------
    # Ownership validation
    # --------------------------------------------------------

    if rental_doc.member != member_doc.name:
        frappe.throw(
            "You are not authorized to return this rental."
        )

    # --------------------------------------------------------
    # Rental must be submitted
    # --------------------------------------------------------

    if rental_doc.docstatus != 1:
        frappe.throw(
            "This rental is not an active submitted rental."
        )

    # --------------------------------------------------------
    # Already returned
    # --------------------------------------------------------

    if rental_doc.status == "Returned":
        frappe.throw(
            "This rental has already been returned."
        )

    # --------------------------------------------------------
    # Invalid rental state
    # --------------------------------------------------------

    if rental_doc.status == "Lost":
        frappe.throw(
            "A lost rental cannot be returned normally."
        )

    if rental_doc.status != "Rented":
        frappe.throw(
            "Only an active rented item can be returned."
        )

    # --------------------------------------------------------
    # Process return
    # --------------------------------------------------------

    rental_doc.return_date = getdate(
        today()
    )

    rental_doc.status = "Returned"

    rental_doc.flags.ignore_permissions = True
    rental_doc.save(
        ignore_permissions=True
    )

    frappe.db.commit()

    rental_doc.reload()

    return {
        "success": True,
        "rental": rental_doc.name,
        "book": rental_doc.book,
        "quantity": rental_doc.quantity,
        "return_date": str(
            rental_doc.return_date
        ),
        "status": rental_doc.status,
        "docstatus": rental_doc.docstatus,
    }


@frappe.whitelist()
def create_sales_invoice(customer_name, items, discount=0, tax=0):
    member_doc = _get_current_member()

    if not customer_name:
        customer_name = member_doc.full_name

    if not items:
        frappe.throw("Please add at least one book.")

    if isinstance(items, str):
        items = frappe.parse_json(items)

    if not isinstance(items, list):
        frappe.throw("Invalid items data.")

    discount = float(discount or 0)
    tax = float(tax or 0)

    invoice = frappe.get_doc({
        "doctype": "Sales Invoice",
        "member": member_doc.name,
        "customer_name": customer_name,
        "invoice_date": today(),
        "discount": discount,
        "tax": tax,
    })

    subtotal = 0

    for item in items:
        if not item.get("book"):
            frappe.throw("Please select a book.")

        quantity = int(
            item.get(
                "quantity",
                item.get("qty", 0)
            )
        )

        if quantity <= 0:
            frappe.throw("Quantity must be greater than zero.")

        book = frappe.get_doc("Book", item["book"])

        if quantity > book.available_copies:
            frappe.throw(
                f"Only {book.available_copies} copies of "
                f"{book.book_title} are available."
            )

        rate = float(book.selling_price or 0)
        subtotal += quantity * rate

        invoice.append("items", {
            "item_type": "Book",
            "book": book.name,
            "description": book.book_title,
            "qty": quantity,
            "rate": rate,
        })

    invoice.insert(ignore_permissions=True)

    invoice.flags.ignore_permissions = True
    invoice.submit()

    return {
        "success": True,
        "invoice": invoice.name,
        "member": member_doc.name,
        "subtotal": subtotal,
        "discount": discount,
        "tax": tax,
        "grand_total": invoice.grand_total,
        "payment_status": invoice.payment_status,
    }


@frappe.whitelist()
def get_invoice(invoice):
    """
    Return an invoice only if it belongs to the currently logged-in member.
    """

    if not invoice:
        frappe.throw("Sales Invoice is required.")

    member_doc = _get_current_member()

    invoice_doc = frappe.get_doc(
        "Sales Invoice",
        invoice,
    )

    if invoice_doc.member != member_doc.name:
        frappe.throw(
            "You are not authorized to access this invoice."
        )

    return invoice_doc.as_dict()


@frappe.whitelist()
def create_payment(
    sales_invoice,
    amount,
    payment_method,
    reference=None,
):
    """
    Create a paid Payment for an invoice belonging to the
    currently logged-in member.

    For book-sale invoices, inventory is reduced only after
    the payment is successfully recorded.
    Membership invoices are activated after payment.
    """

    if not sales_invoice:
        frappe.throw("Sales Invoice is required.")

    if not payment_method:
        frappe.throw("Payment Method is required.")

    member_doc = _get_current_member()

    invoice = frappe.get_doc(
        "Sales Invoice",
        sales_invoice,
    )

    if invoice.member != member_doc.name:
        frappe.throw(
            "You are not authorized to pay this invoice."
        )

    amount = float(amount or 0)

    if amount <= 0:
        frappe.throw(
            "Payment amount must be greater than zero."
        )

    if invoice.docstatus == 0:
        invoice.flags.ignore_permissions = True
        invoice.submit()
        invoice.reload()

    if invoice.docstatus != 1:
        frappe.throw(
            "Sales Invoice must be submitted before recording payment."
        )

    # --------------------------------------------------------
    # Check remaining amount
    # --------------------------------------------------------

    paid_amount = frappe.db.sql(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM `tabPayment`
        WHERE sales_invoice = %s
          AND docstatus = 1
          AND payment_status = 'Paid'
        """,
        sales_invoice,
    )[0][0]

    remaining = (
        float(invoice.grand_total)
        - float(paid_amount or 0)
    )

    if remaining <= 0:
        frappe.throw(
            "This invoice has already been fully paid."
        )

    if amount > remaining + 0.0001:
        frappe.throw(
            f"Payment amount cannot exceed the remaining "
            f"invoice amount of {remaining:.2f}."
        )

    # --------------------------------------------------------
    # Create Payment
    # --------------------------------------------------------

    payment = frappe.get_doc({
        "doctype": "Payment",
        "sales_invoice": sales_invoice,
        "member": member_doc.name,
        "payment_date": today(),
        "amount": amount,
        "payment_method": payment_method,
        "payment_status": "Paid",
        "reference": reference,
    })

    payment.insert(
        ignore_permissions=True
    )

    payment.flags.ignore_permissions = True
    payment.submit()

    # --------------------------------------------------------
    # Update inventory for book sales
    # --------------------------------------------------------

    for item in invoice.items:

        book_name = item.get("book")

        if not book_name:
            continue

        quantity = int(
            item.get("qty") or 0
        )

        if quantity <= 0:
            continue

        existing_inventory = frappe.db.exists(
            "Inventory Transaction",
            {
                "transaction_type": "Sale",
                "reference_doctype": "Sales Invoice",
                "reference_name": invoice.name,
                "book": book_name,
            },
        )

        if existing_inventory:
            continue

        inventory = frappe.get_doc({
            "doctype": "Inventory Transaction",
            "book": book_name,
            "transaction_type": "Sale",
            "quantity": quantity,
            "transaction_date": today(),
            "reference_doctype": "Sales Invoice",
            "reference_name": invoice.name,
        })

        inventory.insert(
            ignore_permissions=True
        )

        inventory.flags.ignore_permissions = True
        inventory.submit()

    # --------------------------------------------------------
    # Activate membership after payment
    # --------------------------------------------------------

    invoice.reload()

    membership_name = frappe.db.get_value(
        "Membership",
        {
            "sales_invoice": sales_invoice,
            "member": member_doc.name,
        },
        "name",
    )

    membership_status = None

    if membership_name:

        membership = frappe.get_doc(
            "Membership",
            membership_name,
        )

        membership.activate_after_payment()
        membership.reload()

        membership_status = membership.status

    space_access = _activate_space_access(
        invoice,
        payment.name,
    )

    frappe.db.commit()

    return {
        "success": True,
        "payment": payment.name,
        "invoice": invoice.name,
        "amount": payment.amount,
        "payment_status": invoice.payment_status,
        "grand_total": invoice.grand_total,
        "membership": membership_name,
        "membership_status": membership_status,
    }

@frappe.whitelist()
def get_member_payments():
    """
    Return payment history for the currently logged-in member.

    Payment access is restricted through the Sales Invoice -> Member
    relationship, so the browser never supplies a member ID.
    """

    member_doc = _get_current_member()

    payments = frappe.db.sql(
        """
        SELECT
            p.name,
            p.sales_invoice,
            p.payment_date,
            p.amount,
            p.payment_method,
            p.payment_status,
            p.reference,
            p.razorpay_payment_id,
            si.grand_total,
            si.payment_status AS invoice_payment_status
        FROM `tabPayment` p
        INNER JOIN `tabSales Invoice` si
            ON si.name = p.sales_invoice
        WHERE si.member = %s
          AND p.docstatus = 1
        ORDER BY p.payment_date DESC, p.creation DESC
        """,
        member_doc.name,
        as_dict=True,
    )

    for payment in payments:
        payment["amount"] = float(payment.get("amount") or 0)
        payment["grand_total"] = float(
            payment.get("grand_total") or 0
        )

        if payment.get("payment_date"):
            payment["payment_date"] = str(
                payment["payment_date"]
            )

    return payments


@frappe.whitelist()
def get_admin_dashboard():
    """
    Return dashboard statistics for authorized Open Shelf administrators.

    Only users with the System Manager role can access this endpoint.
    """

    if frappe.session.user == "Guest":
        frappe.throw(
            "Please login to access the admin dashboard."
        )

    if "System Manager" not in frappe.get_roles():
        frappe.throw(
            "You are not authorized to access the admin dashboard."
        )

    return {
        "books": frappe.db.count(
            "Book"
        ),

        "members": frappe.db.count(
            "Member"
        ),

        "memberships": frappe.db.count(
            "Membership"
        ),

        "active_memberships": frappe.db.count(
            "Membership",
            {
                "status": "Active",
            },
        ),

        "pending_memberships": frappe.db.count(
            "Membership",
            {
                "status": "Pending",
            },
        ),

        "rentals": frappe.db.count(
            "Rental"
        ),

        "active_rentals": frappe.db.count(
            "Rental",
            {
                "status": ["in", ["Rented", "Overdue"]],
            },
        ),

        "sales_invoices": frappe.db.count(
            "Sales Invoice"
        ),

        "payments": frappe.db.count(
            "Payment"
        ),

        "paid_payments": frappe.db.count(
            "Payment",
            {
                "payment_status": "Paid",
                "docstatus": 1,
            },
        ),
    }


@frappe.whitelist()
def get_admin_space_calendar(month=None):
    """
    Return working-space reservations for an admin calendar month.

    Space Access is the source of truth.
    Only System Manager users may access this endpoint.
    """

    if frappe.session.user == "Guest":
        frappe.throw(
            "Please login to access the admin working-space calendar."
        )

    if "System Manager" not in frappe.get_roles():
        frappe.throw(
            "You are not authorized to access the admin working-space calendar."
        )

    if month:
        try:
            month_date = getdate(f"{month}-01")
        except Exception:
            frappe.throw("Invalid calendar month.")
    else:
        month_date = getdate(today())

    month_start = month_date.replace(day=1)

    if month_start.month == 12:
        next_month = month_start.replace(
            year=month_start.year + 1,
            month=1,
            day=1,
        )
    else:
        next_month = month_start.replace(
            month=month_start.month + 1,
            day=1,
        )

    month_end = add_days(next_month, -1)

    accesses = frappe.get_all(
        "Space Access",
        filters={
            "status": "Active",
            "start_date": ["<=", month_end],
            "end_date": [">=", month_start],
        },
        fields=[
            "name",
            "member",
            "space_plan",
            "sales_invoice",
            "payment",
            "start_date",
            "end_date",
            "status",
            "creation",
        ],
        order_by="start_date asc, creation asc",
    )

    reservations = []

    for access in accesses:
        plan = frappe.db.get_value(
            "Space Plan",
            access["space_plan"],
            [
                "plan_name",
                "billing_period",
                "daily_capacity",
                "max_hours_per_day",
                "wifi_included",
            ],
            as_dict=True,
        ) or {}

        member_name = access.get("member") or ""

        full_name = ""
        if member_name:
            full_name = (
                frappe.db.get_value(
                    "Member",
                    member_name,
                    "full_name",
                )
                or member_name
            )

        reservations.append(
            {
                "name": access["name"],
                "member": member_name,
                "member_name": full_name,
                "space_plan": access["space_plan"],
                "plan_name": plan.get("plan_name")
                    or access["space_plan"],
                "billing_period": plan.get("billing_period"),
                "daily_capacity": int(
                    plan.get("daily_capacity") or 0
                ),
                "max_hours_per_day": plan.get(
                    "max_hours_per_day"
                ),
                "wifi_included": bool(
                    plan.get("wifi_included")
                ),
                "sales_invoice": access.get(
                    "sales_invoice"
                ),
                "payment": access.get("payment"),
                "start_date": str(
                    access["start_date"]
                ) if access.get("start_date") else None,
                "end_date": str(
                    access["end_date"]
                ) if access.get("end_date") else None,
                "status": access.get("status"),
            }
        )

    capacities = frappe.get_all(
        "Space Plan",
        filters={
            "active": 1,
        },
        fields=[
            "daily_capacity",
        ],
    )

    configured_capacities = []

    for row in capacities:
        try:
            value = int(row.get("daily_capacity") or 0)
        except (TypeError, ValueError):
            value = 0

        if value > 0:
            configured_capacities.append(value)

    capacity = (
        max(configured_capacities)
        if configured_capacities
        else 4
    )

    return {
        "success": True,
        "month": month_start.strftime("%Y-%m"),
        "month_start": str(month_start),
        "month_end": str(month_end),
        "capacity": capacity,
        "reservations": reservations,
    }


# ============================================================
# RAZORPAY
# ============================================================

def _get_razorpay_client():
    """
    Create the Razorpay client using server-side credentials.
    """

    key_id = frappe.conf.get("razorpay_key_id")
    key_secret = frappe.conf.get("razorpay_key_secret")

    if not key_id or not key_secret:
        frappe.throw(
            "Razorpay is not configured on the server."
        )

    return razorpay.Client(
        auth=(key_id, key_secret)
    )


@frappe.whitelist()
def create_razorpay_order(sales_invoice):
    """
    Create a Razorpay order for the logged-in member's invoice.

    The browser supplies only the invoice name.
    The amount is always calculated from the server-side invoice.
    """

    if not sales_invoice:
        frappe.throw("Sales Invoice is required.")

    member_doc = _get_current_member()

    invoice = frappe.get_doc(
        "Sales Invoice",
        sales_invoice,
    )

    if invoice.member != member_doc.name:
        frappe.throw(
            "You are not authorized to pay this invoice."
        )

    if invoice.docstatus != 1:
        frappe.throw(
            "Sales Invoice must be submitted before payment."
        )

    if float(invoice.grand_total or 0) <= 0:
        frappe.throw(
            "Sales Invoice amount must be greater than zero."
        )

    paid_amount = frappe.db.sql(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM `tabPayment`
        WHERE sales_invoice = %s
          AND docstatus = 1
          AND payment_status = 'Paid'
        """,
        sales_invoice,
    )[0][0]

    remaining = (
        float(invoice.grand_total)
        - float(paid_amount or 0)
    )

    if remaining <= 0:
        frappe.throw(
            "This invoice has already been fully paid."
        )

    client = _get_razorpay_client()

    order = client.order.create({
        "amount": int(round(remaining * 100)),
        "currency": "INR",
        "receipt": invoice.name,
        "notes": {
            "sales_invoice": invoice.name,
            "member": member_doc.name,
        },
    })

    return {
        "success": True,
        "key_id": frappe.conf.get("razorpay_key_id"),
        "order_id": order["id"],
        "amount": int(round(remaining * 100)),
        "currency": "INR",
        "sales_invoice": invoice.name,
        "customer_name": member_doc.full_name,
    }


@frappe.whitelist()
def verify_razorpay_payment(
    sales_invoice,
    razorpay_payment_id,
    razorpay_order_id,
    razorpay_signature,
):
    """
    Verify Razorpay payment and complete the paid sale.

    Inventory is updated only after Razorpay confirms
    the payment as captured.
    """

    if not sales_invoice:
        frappe.throw("Sales Invoice is required.")

    if not razorpay_payment_id:
        frappe.throw("Razorpay Payment ID is required.")

    if not razorpay_order_id:
        frappe.throw("Razorpay Order ID is required.")

    if not razorpay_signature:
        frappe.throw("Razorpay signature is required.")

    member_doc = _get_current_member()

    invoice = frappe.get_doc(
        "Sales Invoice",
        sales_invoice,
    )

    if invoice.member != member_doc.name:
        frappe.throw(
            "You are not authorized to verify payment for this invoice."
        )

    if invoice.docstatus != 1:
        frappe.throw(
            "Sales Invoice must be submitted before payment verification."
        )

    client = _get_razorpay_client()

    # --------------------------------------------------------
    # Verify Razorpay signature
    # --------------------------------------------------------

    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature,
        })
    except Exception:
        frappe.throw(
            "Razorpay payment verification failed."
        )

    # --------------------------------------------------------
    # Verify Razorpay order
    # --------------------------------------------------------

    order = client.order.fetch(
        razorpay_order_id
    )

    if order.get("receipt") != invoice.name:
        frappe.throw(
            "Razorpay order does not belong to this invoice."
        )

    # --------------------------------------------------------
    # Verify Razorpay payment
    # --------------------------------------------------------

    payment = client.payment.fetch(
        razorpay_payment_id
    )

    if payment.get("order_id") != razorpay_order_id:
        frappe.throw(
            "Razorpay payment does not belong to this order."
        )

    if payment.get("status") != "captured":
        frappe.throw(
            "Razorpay payment has not been captured."
        )

    order_amount = int(order.get("amount", 0))
    payment_amount = int(payment.get("amount", 0))

    if payment_amount != order_amount:
        frappe.throw(
            "Razorpay payment amount does not match the order amount."
        )

    # --------------------------------------------------------
    # Prevent duplicate payment processing
    # --------------------------------------------------------

    existing_payment = frappe.db.exists(
        "Payment",
        {
            "razorpay_payment_id": razorpay_payment_id,
            "docstatus": 1,
        },
    )

    if existing_payment:
        existing = frappe.get_doc(
            "Payment",
            existing_payment,
        )

        invoice.reload()

        return {
            "success": True,
            "payment": existing.name,
            "invoice": invoice.name,
            "amount": existing.amount,
            "payment_status": invoice.payment_status,
            "membership": existing.membership,
            "membership_status": None,
            "already_processed": True,
        }

    # --------------------------------------------------------
    # Check remaining invoice amount
    # --------------------------------------------------------

    paid_amount = frappe.db.sql(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM `tabPayment`
        WHERE sales_invoice = %s
          AND docstatus = 1
          AND payment_status = 'Paid'
        """,
        sales_invoice,
    )[0][0]

    remaining = (
        float(invoice.grand_total)
        - float(paid_amount or 0)
    )

    amount = payment_amount / 100.0

    if amount > remaining + 0.0001:
        frappe.throw(
            "Razorpay payment exceeds the remaining invoice amount."
        )

    # --------------------------------------------------------
    # Find membership linked to invoice
    # --------------------------------------------------------

    membership_name = frappe.db.get_value(
        "Membership",
        {
            "sales_invoice": sales_invoice,
            "member": member_doc.name,
        },
        "name",
    )

    # --------------------------------------------------------
    # Create Payment
    # --------------------------------------------------------

    payment_doc = frappe.get_doc({
        "doctype": "Payment",
        "sales_invoice": invoice.name,
        "membership": membership_name,
        "member": member_doc.name,
        "payment_date": today(),
        "amount": amount,
        "payment_method": "Razorpay",
        "payment_status": "Paid",
        "reference": razorpay_payment_id,
        "razorpay_order_id": razorpay_order_id,
        "razorpay_payment_id": razorpay_payment_id,
        "razorpay_signature": razorpay_signature,
    })

    payment_doc.insert(
        ignore_permissions=True
    )

    payment_doc.flags.ignore_permissions = True
    payment_doc.submit()

    # --------------------------------------------------------
    # Update inventory after successful payment
    # --------------------------------------------------------

    for item in invoice.items:

        book_name = item.get("book")

        if not book_name:
            continue

        quantity = int(
            item.get("qty") or 0
        )

        if quantity <= 0:
            continue

        existing_inventory = frappe.db.exists(
            "Inventory Transaction",
            {
                "transaction_type": "Sale",
                "reference_doctype": "Sales Invoice",
                "reference_name": invoice.name,
                "book": book_name,
            },
        )

        if existing_inventory:
            continue

        inventory = frappe.get_doc({
            "doctype": "Inventory Transaction",
            "book": book_name,
            "transaction_type": "Sale",
            "quantity": quantity,
            "transaction_date": today(),
            "reference_doctype": "Sales Invoice",
            "reference_name": invoice.name,
        })

        inventory.insert(
            ignore_permissions=True
        )

        inventory.flags.ignore_permissions = True
        inventory.submit()

    # --------------------------------------------------------
    # Activate membership after successful payment
    # --------------------------------------------------------

    invoice.reload()

    membership_status = None

    if membership_name:

        membership = frappe.get_doc(
            "Membership",
            membership_name,
        )

        membership.activate_after_payment()
        membership.reload()

        membership_status = membership.status

    space_access = _activate_space_access(
        invoice,
        payment_doc.name,
    )

    frappe.db.commit()

    return {
        "success": True,
        "payment": payment_doc.name,
        "invoice": invoice.name,
        "amount": payment_doc.amount,
        "payment_status": invoice.payment_status,
        "grand_total": invoice.grand_total,
        "membership": membership_name,
        "membership_status": membership_status,
        "already_processed": False,
    }


# ============================================================
# ADMIN - BOOKS & INVENTORY
# ============================================================

def _require_admin():
    """
    Allow only users with the System Manager role to access
    Open Shelf administrative APIs.
    """

    if frappe.session.user == "Guest":
        frappe.throw("Please login to continue.")

    # Built-in Frappe Administrator always has admin access.
    if frappe.session.user == "Administrator":
        return

    if "System Manager" not in frappe.get_roles(frappe.session.user):
        frappe.throw(
            "You are not authorized to access the admin area."
        )


@frappe.whitelist()
def get_admin_books(search=None):
    """
    Return books for the Open Shelf admin Books & Inventory page.
    """

    _require_admin()

    filters = {}

    books = frappe.get_all(
        "Book",
        filters=filters,
        fields=[
            "name",
            "book_title",
            "isbn",
            "author",
            "publisher",
            "category",
            "description",
            "publication_year",
            "language",
            "edition",
            "total_copies",
            "available_copies",
            "selling_price",
            "rental_allowed",
            "image",
        ],
        order_by="book_title asc",
    )

    if search:
        search = str(search).strip().lower()

        if search:
            books = [
                book
                for book in books
                if search in (book.book_title or "").lower()
                or search in (book.isbn or "").lower()
                or search in (book.author or "").lower()
                or search in (book.publisher or "").lower()
            ]

    for book in books:
        book["rented_copies"] = max(
            int(book.get("total_copies") or 0)
            - int(book.get("available_copies") or 0),
            0,
        )

    return books


@frappe.whitelist()
def get_admin_book(book):
    """
    Return one book for the admin editor.
    """

    _require_admin()

    if not book:
        frappe.throw("Book is required.")

    return frappe.get_doc(
        "Book",
        book,
    ).as_dict()


@frappe.whitelist()
def create_admin_book(
    book_title,
    isbn=None,
    author=None,
    publisher=None,
    category=None,
    description=None,
    publication_year=None,
    language=None,
    edition=None,
    total_copies=0,
    available_copies=None,
    selling_price=0,
    rental_allowed=0,
    image=None,
):
    """
    Create a new Book from the Open Shelf admin interface.
    """

    _require_admin()

    if not book_title or not str(book_title).strip():
        frappe.throw("Book title is required.")

    try:
        total_copies = int(total_copies or 0)
    except (TypeError, ValueError):
        frappe.throw("Total copies must be a valid number.")

    if total_copies < 0:
        frappe.throw("Total copies cannot be negative.")

    if available_copies in (None, ""):
        available_copies = total_copies
    else:
        try:
            available_copies = int(available_copies)
        except (TypeError, ValueError):
            frappe.throw(
                "Available copies must be a valid number."
            )

    if available_copies < 0:
        frappe.throw(
            "Available copies cannot be negative."
        )

    if available_copies > total_copies:
        frappe.throw(
            "Available copies cannot exceed total copies."
        )

    try:
        selling_price = float(selling_price or 0)
    except (TypeError, ValueError):
        frappe.throw("Selling price must be a valid number.")

    if selling_price < 0:
        frappe.throw("Selling price cannot be negative.")

    book_doc = frappe.get_doc({
        "doctype": "Book",
        "book_title": str(book_title).strip(),
        "isbn": isbn,
        "author": author,
        "publisher": publisher,
        "category": category,
        "description": description,
        "publication_year": publication_year,
        "language": language,
        "edition": edition,
        "total_copies": total_copies,
        "available_copies": available_copies,
        "selling_price": selling_price,
        "rental_allowed": 1 if rental_allowed else 0,
        "image": image,
    })

    book_doc.insert(
        ignore_permissions=True
    )

    frappe.db.commit()

    return {
        "success": True,
        "book": book_doc.as_dict(),
    }


@frappe.whitelist()
def update_admin_book(
    book,
    book_title,
    isbn=None,
    author=None,
    publisher=None,
    category=None,
    description=None,
    publication_year=None,
    language=None,
    edition=None,
    total_copies=0,
    available_copies=0,
    selling_price=0,
    rental_allowed=0,
    image=None,
):
    """
    Update book information from the Open Shelf admin interface.

    Inventory quantities are controlled exclusively through submitted
    Inventory Transactions after a Book has been created.

    Initial stock may be supplied when creating a new Book, but existing
    stock cannot be changed through this update endpoint.
    """

    _require_admin()

    if not book:
        frappe.throw("Book is required.")

    if not book_title or not str(book_title).strip():
        frappe.throw("Book title is required.")

    book_doc = frappe.get_doc(
        "Book",
        book,
    )

    current_total = int(
        book_doc.total_copies or 0
    )

    current_available = int(
        book_doc.available_copies or 0
    )

    try:
        requested_total = int(
            total_copies or 0
        )
        requested_available = int(
            available_copies or 0
        )
    except (TypeError, ValueError):
        frappe.throw(
            "Inventory quantities must be valid numbers."
        )

    if requested_total != current_total:
        frappe.throw(
            "Stock cannot be changed from the Book editor. "
            "Use Admin → Inventory → Add Stock for inventory changes."
        )

    if requested_available != current_available:
        frappe.throw(
            "Available stock cannot be changed from the Book editor. "
            "Stock is controlled by Inventory Transactions."
        )

    try:
        selling_price = float(
            selling_price or 0
        )
    except (TypeError, ValueError):
        frappe.throw(
            "Selling price must be a valid number."
        )

    if selling_price < 0:
        frappe.throw(
            "Selling price cannot be negative."
        )

    book_doc.book_title = str(
        book_title
    ).strip()

    book_doc.isbn = isbn
    book_doc.author = author
    book_doc.publisher = publisher
    book_doc.category = category
    book_doc.description = description
    book_doc.publication_year = publication_year
    book_doc.language = language
    book_doc.edition = edition

    # Stock is intentionally NOT modified here.
    book_doc.total_copies = current_total
    book_doc.available_copies = current_available

    book_doc.selling_price = selling_price
    book_doc.rental_allowed = (
        1 if rental_allowed else 0
    )
    book_doc.image = image

    book_doc.save(
        ignore_permissions=True
    )

    frappe.db.commit()

    return {
        "success": True,
        "book": book_doc.as_dict(),
    }


@frappe.whitelist()
def delete_admin_book(book):
    """
    Delete a book only when it has no active rentals and no
    inventory transactions.
    """

    _require_admin()

    if not book:
        frappe.throw("Book is required.")

    book_doc = frappe.get_doc(
        "Book",
        book,
    )

    active_rentals = frappe.db.count(
        "Rental",
        filters={
            "book": book,
            "status": ["in", ["Rented", "Overdue"]],
            "docstatus": 1,
        },
    )

    if active_rentals:
        frappe.throw(
            "This book cannot be deleted because it has active rentals."
        )

    inventory_transactions = frappe.db.count(
        "Inventory Transaction",
        filters={
            "book": book,
        },
    )

    if inventory_transactions:
        frappe.throw(
            "This book cannot be deleted because it has inventory transaction history."
        )

    frappe.delete_doc(
        "Book",
        book,
        ignore_permissions=True,
    )

    frappe.db.commit()

    return {
        "success": True,
        "book": book,
    }

# ADMIN - MEMBERS

@frappe.whitelist()
def get_admin_members(search=None, status=None):
    _require_admin()

    filters = {}

    if status:
        filters["status"] = status

    members = frappe.get_all(
        "Member",
        filters=filters,
        fields=[
            "name",
            "user",
            "full_name",
            "email",
            "phone",
            "address",
            "date_of_birth",
            "join_date",
            "status",
        ],
        order_by="modified desc",
    )

    if search:
        search = str(search).strip().lower()

        if search:
            members = [
                member
                for member in members
                if search in (member.full_name or "").lower()
                or search in (member.email or "").lower()
                or search in (member.phone or "").lower()
                or search in (member.user or "").lower()
                or search in (member.name or "").lower()
            ]

    for member in members:
        member["active_memberships"] = frappe.db.count(
            "Membership",
            {
                "member": member.name,
                "status": "Active",
            },
        )

        member["active_rentals"] = frappe.db.count(
            "Rental",
            {
                "member": member.name,
                "status": ["in", ["Rented", "Overdue"]],
                "docstatus": 1,
            },
        )

    return members


@frappe.whitelist()
def get_admin_member(member):
    _require_admin()

    if not member:
        frappe.throw("Member is required.")

    member_doc = frappe.get_doc("Member", member)

    result = member_doc.as_dict()

    result["active_memberships"] = frappe.db.count(
        "Membership",
        {
            "member": member_doc.name,
            "status": "Active",
        },
    )

    result["active_rentals"] = frappe.db.count(
        "Rental",
        {
            "member": member_doc.name,
            "status": ["in", ["Rented", "Overdue"]],
            "docstatus": 1,
        },
    )

    return result


@frappe.whitelist()
def create_admin_member(
    user,
    full_name,
    email=None,
    phone=None,
    address=None,
    date_of_birth=None,
    join_date=None,
    status="Active",
):
    _require_admin()

    if not user:
        frappe.throw("User is required.")

    if not full_name or not str(full_name).strip():
        frappe.throw("Full Name is required.")

    if not join_date:
        frappe.throw("Join Date is required.")

    if status not in ["Active", "Inactive", "Suspended"]:
        frappe.throw("Invalid member status.")

    existing = frappe.db.exists("Member", {"user": user})

    if existing:
        frappe.throw(
            f"This User is already linked to Member {existing}."
        )

    member_doc = frappe.get_doc(
        {
            "doctype": "Member",
            "user": user,
            "full_name": str(full_name).strip(),
            "email": email,
            "phone": phone,
            "address": address,
            "date_of_birth": date_of_birth,
            "join_date": join_date,
            "status": status,
        }
    )

    member_doc.insert(ignore_permissions=True)

    frappe.db.commit()

    return {
        "success": True,
        "member": member_doc.name,
    }


@frappe.whitelist()
def update_admin_member(
    member,
    user,
    full_name,
    email=None,
    phone=None,
    address=None,
    date_of_birth=None,
    join_date=None,
    status="Active",
):
    _require_admin()

    if not member:
        frappe.throw("Member is required.")

    if not user:
        frappe.throw("User is required.")

    if not full_name or not str(full_name).strip():
        frappe.throw("Full Name is required.")

    if not join_date:
        frappe.throw("Join Date is required.")

    if status not in ["Active", "Inactive", "Suspended"]:
        frappe.throw("Invalid member status.")

    member_doc = frappe.get_doc("Member", member)

    other_member = frappe.db.exists(
        "Member",
        {
            "user": user,
            "name": ["!=", member],
        },
    )

    if other_member:
        frappe.throw(
            f"This User is already linked to Member {other_member}."
        )

    member_doc.user = user
    member_doc.full_name = str(full_name).strip()
    member_doc.email = email
    member_doc.phone = phone
    member_doc.address = address
    member_doc.date_of_birth = date_of_birth
    member_doc.join_date = join_date
    member_doc.status = status

    member_doc.save(ignore_permissions=True)

    frappe.db.commit()

    return {
        "success": True,
        "member": member_doc.name,
    }


@frappe.whitelist()
def delete_admin_member(member):
    _require_admin()

    if not member:
        frappe.throw("Member is required.")

    member_doc = frappe.get_doc("Member", member)

    active_memberships = frappe.db.count(
        "Membership",
        {
            "member": member,
            "status": "Active",
        },
    )

    if active_memberships:
        frappe.throw(
            "This member cannot be deleted because they have an active membership."
        )

    active_rentals = frappe.db.count(
        "Rental",
        {
            "member": member,
            "status": ["in", ["Rented", "Overdue"]],
            "docstatus": 1,
        },
    )

    if active_rentals:
        frappe.throw(
            "This member cannot be deleted because they have active rentals."
        )

    frappe.delete_doc(
        "Member",
        member,
        ignore_permissions=True,
    )

    frappe.db.commit()

    return {
        "success": True,
        "member": member,
    }


@frappe.whitelist()
def get_admin_member_users():
    _require_admin()

    users = frappe.get_all(
        "User",
        filters={
            "enabled": 1,
            "user_type": "Website User",
        },
        fields=[
            "name",
            "full_name",
            "email",
        ],
        order_by="full_name asc",
    )

    return users


# ADMIN - MEMBERSHIPS

@frappe.whitelist()
def get_admin_memberships(search=None, status=None):
    _require_admin()

    filters = {}

    if status:
        filters["status"] = status

    memberships = frappe.get_all(
        "Membership",
        filters=filters,
        fields=[
            "name",
            "member",
            "membership_plan",
            "sales_invoice",
            "start_date",
            "end_date",
            "status",
        ],
        order_by="modified desc",
    )

    if search:
        search = str(search).strip().lower()

        if search:
            filtered = []

            for membership in memberships:
                member_name = frappe.db.get_value(
                    "Member",
                    membership.member,
                    "full_name",
                ) or ""

                plan_name = frappe.db.get_value(
                    "Membership Plan",
                    membership.membership_plan,
                    "plan_name",
                ) or ""

                if (
                    search in (membership.name or "").lower()
                    or search in member_name.lower()
                    or search in plan_name.lower()
                    or search in (membership.sales_invoice or "").lower()
                ):
                    membership["member_full_name"] = member_name
                    membership["plan_display_name"] = plan_name
                    filtered.append(membership)

            memberships = filtered

    for membership in memberships:
        if "member_full_name" not in membership:
            membership["member_full_name"] = (
                frappe.db.get_value(
                    "Member",
                    membership.member,
                    "full_name",
                ) or membership.member
            )

        if "plan_display_name" not in membership:
            membership["plan_display_name"] = (
                frappe.db.get_value(
                    "Membership Plan",
                    membership.membership_plan,
                    "plan_name",
                ) or membership.membership_plan
            )

    return memberships


@frappe.whitelist()
def get_admin_membership(membership):
    _require_admin()

    if not membership:
        frappe.throw("Membership is required.")

    membership_doc = frappe.get_doc(
        "Membership",
        membership,
    )

    result = membership_doc.as_dict()

    result["member_full_name"] = (
        frappe.db.get_value(
            "Member",
            membership_doc.member,
            "full_name",
        ) or membership_doc.member
    )

    result["plan_display_name"] = (
        frappe.db.get_value(
            "Membership Plan",
            membership_doc.membership_plan,
            "plan_name",
        ) or membership_doc.membership_plan
    )

    return result


@frappe.whitelist()
def get_admin_membership_members():
    _require_admin()

    return frappe.get_all(
        "Member",
        filters={"status": "Active"},
        fields=[
            "name",
            "full_name",
            "email",
        ],
        order_by="full_name asc",
    )


@frappe.whitelist()
def get_admin_membership_plans():
    _require_admin()

    return frappe.get_all(
        "Membership Plan",
        filters={"active": 1},
        fields=[
            "name",
            "plan_name",
            "duration_months",
            "price",
            "description",
            "active",
        ],
        order_by="price asc",
    )


@frappe.whitelist()
def create_admin_membership(
    member,
    membership_plan,
    start_date,
    end_date=None,
    status="Pending",
):
    _require_admin()

    if not member:
        frappe.throw("Member is required.")

    if not membership_plan:
        frappe.throw("Membership Plan is required.")

    if not start_date:
        frappe.throw("Start Date is required.")

    if status not in [
        "Pending",
        "Active",
        "Expired",
        "Cancelled",
    ]:
        frappe.throw("Invalid membership status.")

    if not frappe.db.exists("Member", member):
        frappe.throw("Member does not exist.")

    plan = frappe.get_doc(
        "Membership Plan",
        membership_plan,
    )

    if not plan.active:
        frappe.throw("The selected Membership Plan is inactive.")

    start = getdate(start_date)

    if end_date:
        end = getdate(end_date)
    else:
        end = add_days(
            start,
            int(plan.duration_months or 1) * 30 - 1,
        )

    if end < start:
        frappe.throw(
            "End Date cannot be before Start Date."
        )

    membership_doc = frappe.get_doc(
        {
            "doctype": "Membership",
            "member": member,
            "membership_plan": membership_plan,
            "start_date": start,
            "end_date": end,
            "status": status,
        }
    )

    membership_doc.insert(
        ignore_permissions=True
    )

    frappe.db.commit()

    return {
        "success": True,
        "membership": membership_doc.name,
    }


@frappe.whitelist()
def update_admin_membership(
    membership,
    member,
    membership_plan,
    start_date,
    end_date,
    status,
):
    _require_admin()

    if not membership:
        frappe.throw("Membership is required.")

    if not member:
        frappe.throw("Member is required.")

    if not membership_plan:
        frappe.throw("Membership Plan is required.")

    if not start_date:
        frappe.throw("Start Date is required.")

    if not end_date:
        frappe.throw("End Date is required.")

    if status not in [
        "Pending",
        "Active",
        "Expired",
        "Cancelled",
    ]:
        frappe.throw("Invalid membership status.")

    membership_doc = frappe.get_doc(
        "Membership",
        membership,
    )

    start = getdate(start_date)
    end = getdate(end_date)

    if end < start:
        frappe.throw(
            "End Date cannot be before Start Date."
        )

    membership_doc.member = member
    membership_doc.membership_plan = membership_plan
    membership_doc.start_date = start
    membership_doc.end_date = end
    membership_doc.status = status

    membership_doc.save(
        ignore_permissions=True
    )

    frappe.db.commit()

    return {
        "success": True,
        "membership": membership_doc.name,
    }


@frappe.whitelist()
def delete_admin_membership(membership):
    _require_admin()

    if not membership:
        frappe.throw("Membership is required.")

    membership_doc = frappe.get_doc(
        "Membership",
        membership,
    )

    if membership_doc.sales_invoice:
        frappe.throw(
            "This membership cannot be deleted because it is linked to a Sales Invoice."
        )

    frappe.delete_doc(
        "Membership",
        membership,
        ignore_permissions=True,
    )

    frappe.db.commit()

    return {
        "success": True,
        "membership": membership,
    }


# ADMIN - RENTALS

@frappe.whitelist()
def get_admin_rentals(search=None, status=None):
    _require_admin()

    rentals = frappe.get_all(
        "Rental",
        fields=[
            "name",
            "book",
            "member",
            "rental_plan",
            "quantity",
            "rental_date",
            "due_date",
            "return_date",
            "status",
            "docstatus",
        ],
        order_by="rental_date desc, creation desc",
    )

    if search:
        search = str(search).strip().lower()
        if search:
            filtered = []

            for rental in rentals:
                book_title = frappe.db.get_value(
                    "Book",
                    rental.book,
                    "book_title"
                ) or ""

                member_name = frappe.db.get_value(
                    "Member",
                    rental.member,
                    "full_name"
                ) or ""

                values = [
                    rental.name or "",
                    rental.book or "",
                    book_title,
                    rental.member or "",
                    member_name,
                    rental.rental_plan or "",
                    rental.status or "",
                ]

                if any(search in str(value).lower() for value in values):
                    filtered.append(rental)

            rentals = filtered

    if status:
        rentals = [
            rental
            for rental in rentals
            if rental.status == status
        ]

    for rental in rentals:
        rental["book_title"] = (
            frappe.db.get_value(
                "Book",
                rental.book,
                "book_title"
            )
            or rental.book
            or ""
        )

        rental["member_name"] = (
            frappe.db.get_value(
                "Member",
                rental.member,
                "full_name"
            )
            or rental.member
            or "Walk-in / Non-member"
        )

        rental["rental_plan_name"] = (
            frappe.db.get_value(
                "Rental Plan",
                rental.rental_plan,
                "plan_name"
            )
            or rental.rental_plan
            or ""
        )

    return rentals


@frappe.whitelist()
def get_admin_rental(rental):
    _require_admin()

    if not rental:
        frappe.throw("Rental is required.")

    rental_doc = frappe.get_doc("Rental", rental)
    data = rental_doc.as_dict()

    data["book_title"] = (
        frappe.db.get_value(
            "Book",
            rental_doc.book,
            "book_title"
        )
        or rental_doc.book
        or ""
    )

    data["member_name"] = (
        frappe.db.get_value(
            "Member",
            rental_doc.member,
            "full_name"
        )
        or rental_doc.member
        or "Walk-in / Non-member"
    )

    data["rental_plan_name"] = (
        frappe.db.get_value(
            "Rental Plan",
            rental_doc.rental_plan,
            "plan_name"
        )
        or rental_doc.rental_plan
        or ""
    )

    return data


@frappe.whitelist()
def get_admin_rental_members():
    _require_admin()

    return frappe.get_all(
        "Member",
        filters={"status": "Active"},
        fields=[
            "name",
            "full_name",
            "email",
        ],
        order_by="full_name asc",
    )


@frappe.whitelist()
def get_admin_rental_books():
    _require_admin()

    return frappe.get_all(
        "Book",
        filters={"rental_allowed": 1},
        fields=[
            "name",
            "book_title",
            "available_copies",
            "total_copies",
        ],
        order_by="book_title asc",
    )


@frappe.whitelist()
def get_admin_rental_plans():
    _require_admin()

    return frappe.get_all(
        "Rental Plan",
        filters={"active": 1},
        fields=[
            "name",
            "plan_name",
            "duration_days",
            "price",
        ],
        order_by="price asc",
    )


@frappe.whitelist()
def create_admin_rental(
    book,
    rental_plan,
    quantity=1,
    member=None,
    rental_date=None,
    due_date=None,
):
    _require_admin()

    if not book:
        frappe.throw("Book is required.")

    if not rental_plan:
        frappe.throw("Rental Plan is required.")

    quantity = int(quantity or 0)

    if quantity <= 0:
        frappe.throw("Quantity must be greater than zero.")

    book_doc = frappe.get_doc("Book", book)

    if not book_doc.rental_allowed:
        frappe.throw("This book is not available for rental.")

    available_copies = int(book_doc.available_copies or 0)

    if available_copies < quantity:
        frappe.throw(
            f"Only {available_copies} copies of this book are currently available."
        )

    plan_doc = frappe.get_doc("Rental Plan", rental_plan)

    if not plan_doc.active:
        frappe.throw("The selected rental plan is not active.")

    if member:
        member_doc = frappe.get_doc("Member", member)

        if member_doc.status != "Active":
            frappe.throw("The selected member is not active.")

        active_membership = frappe.get_all(
            "Membership",
            filters={
                "member": member,
                "status": "Active",
                "start_date": ["<=", today()],
                "end_date": [">=", today()],
            },
            limit=1,
        )

        if not active_membership:
            frappe.throw(
                "The selected member does not have an active membership."
            )

    rental_date = rental_date or today()

    if due_date:
        due_date_value = getdate(due_date)
    else:
        due_date_value = add_days(
            getdate(rental_date),
            int(plan_doc.duration_days or 0),
        )

    if due_date_value < getdate(rental_date):
        frappe.throw("Due Date cannot be before Rental Date.")

    rental = frappe.get_doc(
        {
            "doctype": "Rental",
            "book": book,
            "member": member or None,
            "rental_plan": rental_plan,
            "quantity": quantity,
            "rental_date": rental_date,
            "due_date": due_date_value,
            "status": "Rented",
        }
    )

    rental.insert(ignore_permissions=True)
    rental.submit()

    frappe.db.commit()

    return {
        "success": True,
        "rental": rental.name,
        "book": rental.book,
        "member": rental.member,
        "rental_plan": rental.rental_plan,
        "quantity": rental.quantity,
        "rental_date": rental.rental_date,
        "due_date": rental.due_date,
        "return_date": rental.return_date,
        "status": rental.status,
    }


@frappe.whitelist()
def return_admin_rental(rental):
    _require_admin()

    if not rental:
        frappe.throw("Rental is required.")

    rental_doc = frappe.get_doc("Rental", rental)

    if rental_doc.docstatus != 1:
        frappe.throw("Only submitted rentals can be returned.")

    if rental_doc.status == "Returned":
        frappe.throw("This rental has already been returned.")

    if rental_doc.status == "Lost":
        frappe.throw("A lost rental cannot be returned normally.")

    if rental_doc.status not in ("Rented", "Overdue"):
        frappe.throw(
            f"Rental cannot be returned from status {rental_doc.status}."
        )

    rental_doc.return_date = today()
    rental_doc.status = "Returned"

    rental_doc.save(ignore_permissions=True)

    frappe.db.commit()

    rental_doc.reload()

    return {
        "success": True,
        "rental": rental_doc.name,
        "book": rental_doc.book,
        "member": rental_doc.member,
        "quantity": rental_doc.quantity,
        "rental_date": rental_doc.rental_date,
        "due_date": rental_doc.due_date,
        "return_date": rental_doc.return_date,
        "status": rental_doc.status,
    }


@frappe.whitelist()
def mark_admin_rental_overdue(rental):
    _require_admin()

    if not rental:
        frappe.throw("Rental is required.")

    rental_doc = frappe.get_doc("Rental", rental)

    if rental_doc.docstatus != 1:
        frappe.throw("Only submitted rentals can be marked overdue.")

    if rental_doc.status != "Rented":
        frappe.throw(
            "Only currently rented rentals can be marked overdue."
        )

    rental_doc.status = "Overdue"
    rental_doc.save(ignore_permissions=True)

    frappe.db.commit()

    rental_doc.reload()

    return {
        "success": True,
        "rental": rental_doc.name,
        "status": rental_doc.status,
    }


@frappe.whitelist()
def delete_admin_rental(rental):
    _require_admin()

    if not rental:
        frappe.throw("Rental is required.")

    rental_doc = frappe.get_doc("Rental", rental)

    if rental_doc.status in ("Rented", "Overdue"):
        frappe.throw(
            "Active rentals cannot be deleted. Return the rental first."
        )

    inventory_exists = frappe.db.exists(
        "Inventory Transaction",
        {
            "reference_doctype": "Rental",
            "reference_name": rental_doc.name,
        },
    )

    if inventory_exists:
        frappe.throw(
            "This rental has inventory transactions and cannot be deleted."
        )

    frappe.delete_doc(
        "Rental",
        rental_doc.name,
        ignore_permissions=True,
    )

    frappe.db.commit()

    return {
        "success": True,
        "rental": rental_doc.name,
    }


@frappe.whitelist()
def get_admin_rental_stats():
    _require_admin()

    total = frappe.db.count("Rental")

    rented = frappe.db.count(
        "Rental",
        filters={"status": "Rented"},
    )

    returned = frappe.db.count(
        "Rental",
        filters={"status": "Returned"},
    )

    overdue = frappe.db.count(
        "Rental",
        filters={"status": "Overdue"},
    )

    lost = frappe.db.count(
        "Rental",
        filters={"status": "Lost"},
    )

    return {
        "total": total,
        "rented": rented,
        "returned": returned,
        "overdue": overdue,
        "lost": lost,
    }


# ============================================================
# ADMIN - SALES INVOICES
# ============================================================

@frappe.whitelist()
def get_admin_sales_invoices(search=None, payment_status=None):
    _require_admin()

    filters = {}

    if payment_status:
        filters["payment_status"] = payment_status

    invoices = frappe.get_all(
        "Sales Invoice",
        filters=filters,
        fields=[
            "name",
            "member",
            "customer_name",
            "invoice_date",
            "subtotal",
            "discount",
            "tax",
            "grand_total",
            "payment_status",
            "docstatus",
        ],
        order_by="invoice_date desc, creation desc",
    )

    if search:
        search = str(search).strip().lower()

        if search:
            filtered = []

            for invoice in invoices:
                member_name = ""

                if invoice.member:
                    member_name = (
                        frappe.db.get_value(
                            "Member",
                            invoice.member,
                            "full_name",
                        )
                        or ""
                    )

                values = [
                    invoice.name or "",
                    invoice.member or "",
                    member_name,
                    invoice.customer_name or "",
                    invoice.payment_status or "",
                ]

                if any(
                    search in str(value).lower()
                    for value in values
                ):
                    invoice["member_name"] = (
                        member_name
                        or invoice.customer_name
                        or "Walk-in / Customer"
                    )
                    filtered.append(invoice)

            invoices = filtered

    for invoice in invoices:
        if "member_name" not in invoice:
            member_name = ""

            if invoice.member:
                member_name = (
                    frappe.db.get_value(
                        "Member",
                        invoice.member,
                        "full_name",
                    )
                    or ""
                )

            invoice["member_name"] = (
                member_name
                or invoice.customer_name
                or "Walk-in / Customer"
            )

        invoice["subtotal"] = float(
            invoice.get("subtotal") or 0
        )
        invoice["discount"] = float(
            invoice.get("discount") or 0
        )
        invoice["tax"] = float(
            invoice.get("tax") or 0
        )
        invoice["grand_total"] = float(
            invoice.get("grand_total") or 0
        )

    return invoices


@frappe.whitelist()
def get_admin_sales_invoice(invoice):
    _require_admin()

    if not invoice:
        frappe.throw("Sales Invoice is required.")

    invoice_doc = frappe.get_doc(
        "Sales Invoice",
        invoice,
    )

    data = invoice_doc.as_dict()

    if invoice_doc.member:
        data["member_name"] = (
            frappe.db.get_value(
                "Member",
                invoice_doc.member,
                "full_name",
            )
            or invoice_doc.member
        )
    else:
        data["member_name"] = (
            invoice_doc.customer_name
            or "Walk-in / Customer"
        )

    data["items"] = [
        item.as_dict()
        for item in invoice_doc.items
    ]

    data["subtotal"] = float(
        data.get("subtotal") or 0
    )
    data["discount"] = float(
        data.get("discount") or 0
    )
    data["tax"] = float(
        data.get("tax") or 0
    )
    data["grand_total"] = float(
        data.get("grand_total") or 0
    )

    for item in data["items"]:
        item["qty"] = int(
            item.get("qty") or 0
        )
        item["rate"] = float(
            item.get("rate") or 0
        )
        item["amount"] = float(
            item.get("amount") or 0
        )

    return data


@frappe.whitelist()
def get_admin_sales_invoice_stats():
    _require_admin()

    total = frappe.db.count(
        "Sales Invoice"
    )

    unpaid = frappe.db.count(
        "Sales Invoice",
        filters={
            "payment_status": "Unpaid",
        },
    )

    partly_paid = frappe.db.count(
        "Sales Invoice",
        filters={
            "payment_status": "Partly Paid",
        },
    )

    paid = frappe.db.count(
        "Sales Invoice",
        filters={
            "payment_status": "Paid",
        },
    )

    return {
        "total": total,
        "unpaid": unpaid,
        "partly_paid": partly_paid,
        "paid": paid,
    }


# ============================================================
# ADMIN - PAYMENTS
# ============================================================

@frappe.whitelist()
def get_admin_payments(search=None, payment_status=None):
    _require_admin()

    filters = {
        "docstatus": 1,
    }

    if payment_status:
        filters["payment_status"] = payment_status

    payments = frappe.get_all(
        "Payment",
        filters=filters,
        fields=[
            "name",
            "sales_invoice",
            "member",
            "payment_date",
            "amount",
            "payment_method",
            "payment_status",
            "reference",
            "razorpay_payment_id",
            "docstatus",
        ],
        order_by="payment_date desc, creation desc",
    )

    search = str(search or "").strip().lower()

    for payment in payments:
        member_name = ""
        customer_name = ""

        if payment.member:
            member_name = (
                frappe.db.get_value(
                    "Member",
                    payment.member,
                    "full_name",
                )
                or ""
            )

        if payment.sales_invoice:
            customer_name = (
                frappe.db.get_value(
                    "Sales Invoice",
                    payment.sales_invoice,
                    "customer_name",
                )
                or ""
            )

        payment["member_name"] = (
            member_name
            or customer_name
            or "Walk-in / Customer"
        )

        payment["customer_name"] = (
            customer_name
            or member_name
            or "Walk-in / Customer"
        )

        payment["amount"] = float(
            payment.get("amount") or 0
        )

        if payment.get("payment_date"):
            payment["payment_date"] = str(
                payment["payment_date"]
            )

    if search:
        filtered = []

        for payment in payments:
            values = [
                payment.get("name") or "",
                payment.get("sales_invoice") or "",
                payment.get("member") or "",
                payment.get("member_name") or "",
                payment.get("customer_name") or "",
                payment.get("payment_method") or "",
                payment.get("payment_status") or "",
                payment.get("reference") or "",
                payment.get("razorpay_payment_id") or "",
            ]

            if any(
                search in str(value).lower()
                for value in values
            ):
                filtered.append(payment)

        payments = filtered

    return payments


@frappe.whitelist()
def get_admin_payment(payment):
    _require_admin()

    if not payment:
        frappe.throw("Payment is required.")

    payment_doc = frappe.get_doc(
        "Payment",
        payment,
    )

    data = payment_doc.as_dict()

    data["amount"] = float(
        data.get("amount") or 0
    )

    if data.get("payment_date"):
        data["payment_date"] = str(
            data["payment_date"]
        )

    data["member_name"] = "Walk-in / Customer"
    data["customer_name"] = "Walk-in / Customer"

    if payment_doc.member:
        data["member_name"] = (
            frappe.db.get_value(
                "Member",
                payment_doc.member,
                "full_name",
            )
            or payment_doc.member
        )

    if payment_doc.sales_invoice:
        invoice_customer = (
            frappe.db.get_value(
                "Sales Invoice",
                payment_doc.sales_invoice,
                "customer_name",
            )
            or ""
        )

        if invoice_customer:
            data["customer_name"] = invoice_customer
        elif payment_doc.member:
            data["customer_name"] = data["member_name"]

    if payment_doc.sales_invoice:
        invoice = frappe.get_doc(
            "Sales Invoice",
            payment_doc.sales_invoice,
        )

        data["invoice"] = {
            "name": invoice.name,
            "member": invoice.member,
            "customer_name": invoice.customer_name,
            "invoice_date": (
                str(invoice.invoice_date)
                if invoice.invoice_date
                else None
            ),
            "subtotal": float(
                invoice.subtotal or 0
            ),
            "discount": float(
                invoice.discount or 0
            ),
            "tax": float(
                invoice.tax or 0
            ),
            "grand_total": float(
                invoice.grand_total or 0
            ),
            "payment_status": invoice.payment_status,
            "docstatus": invoice.docstatus,
        }
    else:
        data["invoice"] = None

    return data


@frappe.whitelist()
def get_admin_payment_stats():
    _require_admin()

    total = frappe.db.count(
        "Payment",
        filters={
            "docstatus": 1,
        },
    )

    paid = frappe.db.count(
        "Payment",
        filters={
            "docstatus": 1,
            "payment_status": "Paid",
        },
    )

    pending = frappe.db.count(
        "Payment",
        filters={
            "docstatus": 1,
            "payment_status": "Pending",
        },
    )

    failed = frappe.db.count(
        "Payment",
        filters={
            "docstatus": 1,
            "payment_status": "Failed",
        },
    )

    return {
        "total": total,
        "paid": paid,
        "pending": pending,
        "failed": failed,
    }


@frappe.whitelist()
def get_admin_inventory(search=None):
    """
    Return the current inventory position for the admin inventory page.

    Stock quantities come directly from the Book master, which is updated
    by submitted Inventory Transactions.
    """

    _require_admin()

    books = frappe.get_all(
        "Book",
        fields=[
            "name",
            "book_title",
            "isbn",
            "total_copies",
            "available_copies",
            "selling_price",
            "rental_allowed",
        ],
        order_by="book_title asc",
    )

    search = str(search or "").strip().lower()

    inventory = []

    for book in books:
        if search:
            values = [
                book.name or "",
                book.book_title or "",
                book.isbn or "",
            ]

            if not any(
                search in str(value).lower()
                for value in values
            ):
                continue

        total = int(book.total_copies or 0)
        available = int(book.available_copies or 0)

        inventory.append({
            "name": book.name,
            "book_title": book.book_title,
            "isbn": book.isbn,
            "total_copies": total,
            "available_copies": available,
            "rented_copies": max(total - available, 0),
            "selling_price": float(book.selling_price or 0),
            "rental_allowed": int(book.rental_allowed or 0),
        })

    return inventory


@frappe.whitelist()
def get_admin_inventory_stats():
    """
    Return inventory summary statistics for administrators.
    """

    _require_admin()

    books = frappe.get_all(
        "Book",
        fields=[
            "total_copies",
            "available_copies",
        ],
    )

    total_books = len(books)
    total_copies = 0
    available_copies = 0

    for book in books:
        total_copies += int(book.total_copies or 0)
        available_copies += int(book.available_copies or 0)

    rented_copies = max(
        total_copies - available_copies,
        0,
    )

    return {
        "total_books": total_books,
        "total_copies": total_copies,
        "available_copies": available_copies,
        "rented_copies": rented_copies,
    }


@frappe.whitelist()
def get_admin_inventory_transactions(
    search=None,
    transaction_type=None,
):
    """
    Return inventory transaction history for administrators.

    Submitted and cancelled transactions are retained as historical
    records. Stock effects are controlled by the Inventory Transaction
    DocType itself.
    """

    _require_admin()

    filters = {}

    if transaction_type:
        filters["transaction_type"] = transaction_type

    transactions = frappe.get_all(
        "Inventory Transaction",
        filters=filters,
        fields=[
            "name",
            "book",
            "transaction_type",
            "quantity",
            "transaction_date",
            "reference_doctype",
            "reference_name",
            "notes",
            "docstatus",
            "creation",
        ],
        order_by="transaction_date desc, creation desc",
    )

    search = str(search or "").strip().lower()

    result = []

    for transaction in transactions:
        book_title = (
            frappe.db.get_value(
                "Book",
                transaction.book,
                "book_title",
            )
            or transaction.book
            or ""
        )

        values = [
            transaction.name or "",
            transaction.book or "",
            book_title,
            transaction.transaction_type or "",
            transaction.reference_doctype or "",
            transaction.reference_name or "",
            transaction.notes or "",
        ]

        if search and not any(
            search in str(value).lower()
            for value in values
        ):
            continue

        transaction["book_title"] = book_title

        if transaction.transaction_date:
            transaction["transaction_date"] = str(
                transaction.transaction_date
            )

        result.append(transaction)

    return result


@frappe.whitelist()
def get_admin_inventory_transaction(transaction):
    """
    Return one inventory transaction for the admin details view.
    """

    _require_admin()

    if not transaction:
        frappe.throw("Inventory transaction is required.")

    transaction_doc = frappe.get_doc(
        "Inventory Transaction",
        transaction,
    )

    data = transaction_doc.as_dict()

    data["book_title"] = (
        frappe.db.get_value(
            "Book",
            transaction_doc.book,
            "book_title",
        )
        or transaction_doc.book
        or ""
    )

    data["quantity"] = int(
        data.get("quantity") or 0
    )

    if data.get("transaction_date"):
        data["transaction_date"] = str(
            data["transaction_date"]
        )

    return data


@frappe.whitelist()
def create_admin_inventory_purchase(
    book,
    quantity,
    transaction_date=None,
    notes=None,
):
    """
    Record new stock purchased for a book.

    The submitted Inventory Transaction is the only operation that changes
    stock. Its existing on_submit/update_stock logic increases both
    total_copies and available_copies.
    """

    _require_admin()

    if not book:
        frappe.throw("Book is required.")

    if not frappe.db.exists("Book", book):
        frappe.throw("The selected book does not exist.")

    try:
        quantity = int(quantity or 0)
    except (TypeError, ValueError):
        frappe.throw("Quantity must be a valid number.")

    if quantity <= 0:
        frappe.throw("Quantity must be greater than 0.")

    if not transaction_date:
        transaction_date = frappe.utils.today()

    transaction = frappe.get_doc({
        "doctype": "Inventory Transaction",
        "book": book,
        "transaction_type": "Purchase",
        "quantity": quantity,
        "transaction_date": transaction_date,
        "notes": notes,
    })

    transaction.insert(
        ignore_permissions=True
    )

    transaction.submit()

    frappe.db.commit()

    return {
        "success": True,
        "transaction": transaction.name,
        "book": book,
        "quantity": quantity,
    }

# ============================================================================
# BULK IMPORT / EXPORT
# Production-safe admin data tools
# ============================================================================

import csv
import io
import json


BULK_MASTER_DOCTYPES = {
    "Author",
    "Book",
    "Category",
    "Member",
    "Membership Plan",
    "Publisher",
    "Rental Plan",
}


def _require_bulk_admin():
    """Allow bulk data operations only for administrators."""
    if frappe.session.user == "Guest":
        frappe.throw("Administrator login required.")

    roles = frappe.get_roles(frappe.session.user)

    if "System Manager" not in roles:
        frappe.throw(
            "You do not have permission to perform bulk data operations."
        )


def _validate_bulk_doctype(doctype):
    """Allow only approved master-data DocTypes."""
    if not doctype:
        frappe.throw("DocType is required.")

    if doctype not in BULK_MASTER_DOCTYPES:
        frappe.throw(
            f"Bulk import/export is not allowed for DocType '{doctype}'."
        )

    if not frappe.db.exists("DocType", doctype):
        frappe.throw(f"DocType '{doctype}' does not exist.")

    return doctype


def _get_bulk_fields(doctype):
    """
    Return safe fields that can be exported/imported.

    System fields, read-only fields, table fields and internal fields
    are excluded automatically.
    """
    meta = frappe.get_meta(doctype)

    excluded_fieldtypes = {
        "Section Break",
        "Column Break",
        "Tab Break",
        "Table",
        "Table MultiSelect",
        "HTML",
        "Button",
        "Fold",
        "Heading",
    }

    fields = ["name"]

    for df in meta.fields:
        if df.fieldname == "name":
            continue

        if df.fieldtype in excluded_fieldtypes:
            continue

        if df.read_only:
            continue

        if df.hidden:
            continue

        if df.is_virtual:
            continue

        if df.fieldname.startswith("_"):
            continue

        fields.append(df.fieldname)

    return fields


@frappe.whitelist()
def get_bulk_import_template(doctype):
    """
    Return a CSV template for an approved master DocType.
    """
    _require_bulk_admin()
    doctype = _validate_bulk_doctype(doctype)

    fields = _get_bulk_fields(doctype)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(fields)

    frappe.response["filename"] = (
        f"{frappe.scrub(doctype).replace('_', '-')}-import-template.csv"
    )
    frappe.response["filecontent"] = output.getvalue()
    frappe.response["type"] = "download"


@frappe.whitelist()
def export_bulk_data(doctype):
    """
    Export all records from an approved master DocType as CSV.
    """
    _require_bulk_admin()
    doctype = _validate_bulk_doctype(doctype)

    fields = _get_bulk_fields(doctype)

    records = frappe.get_all(
        doctype,
        fields=fields,
        order_by="creation asc",
        limit_page_length=0,
    )

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=fields,
        extrasaction="ignore",
    )

    writer.writeheader()

    for record in records:
        row = {}

        for field in fields:
            value = record.get(field)

            if value is None:
                value = ""

            if isinstance(value, (dict, list, tuple)):
                value = json.dumps(
                    value,
                    ensure_ascii=False,
                    default=str,
                )

            row[field] = value

        writer.writerow(row)

    frappe.response["filename"] = (
        f"{frappe.scrub(doctype).replace('_', '-')}-export.csv"
    )
    frappe.response["filecontent"] = output.getvalue()
    frappe.response["type"] = "download"


@frappe.whitelist()
def import_bulk_data(doctype, csv_data, dry_run=0):
    """
    Production-safe master-data CSV import.

    Behaviour:
    - Existing records are updated.
    - New records are inserted.
    - Existing records are never deleted.
    - Only valid fields for the selected DocType are accepted.
    - dry_run=1 validates without saving.
    - Real imports are atomic: if any row fails, the entire import
      is rolled back and nothing is committed.

    Book-specific behaviour:
    - ISBN is the primary business identifier.
    - Existing Books are matched by ISBN before name.
    - Duplicate ISBN rows in one CSV are merged.
    - Explicit total_copies uses the largest supplied value.
    - If total_copies is absent, duplicate rows represent copies.
    """
    _require_bulk_admin()
    doctype = _validate_bulk_doctype(doctype)

    if not csv_data:
        frappe.throw("CSV data is required.")

    try:
        if isinstance(csv_data, bytes):
            csv_data = csv_data.decode("utf-8-sig")

        csv_data = str(csv_data)

        reader = csv.DictReader(io.StringIO(csv_data))

        if not reader.fieldnames:
            frappe.throw("The CSV file does not contain a header row.")

        allowed_fields = set(_get_bulk_fields(doctype))

        supplied_fields = {
            field.strip()
            for field in reader.fieldnames
            if field and field.strip()
        }

        invalid_fields = sorted(
            supplied_fields - allowed_fields
        )

        if invalid_fields:
            frappe.throw(
                "Invalid fields for "
                f"{doctype}: {', '.join(invalid_fields)}"
            )

        if "name" not in supplied_fields:
            frappe.throw(
                "The CSV must contain a 'name' column. "
                "Leave it blank for new records."
            )

        dry_run = str(dry_run).lower() in {
            "1",
            "true",
            "yes",
        }

        raw_rows = list(reader)

        # ------------------------------------------------------------
        # BOOK-SPECIFIC DUPLICATE ISBN PROTECTION
        # ------------------------------------------------------------

        if doctype == "Book" and "isbn" in supplied_fields:

            grouped_rows = {}
            group_order = []

            for row_number, raw_row in enumerate(raw_rows, start=2):

                isbn = (raw_row.get("isbn") or "").strip()

                if not isbn:
                    key = f"__NO_ISBN_{row_number}"
                else:
                    key = isbn

                if key not in grouped_rows:
                    grouped_rows[key] = {
                        "rows": [],
                        "first_row": row_number,
                    }
                    group_order.append(key)

                grouped_rows[key]["rows"].append(
                    (row_number, raw_row)
                )

            merged_rows = []

            for key in group_order:

                entries = grouped_rows[key]

                if key.startswith("__NO_ISBN_"):
                    for row_number, raw_row in entries["rows"]:
                        merged_rows.append(
                            (row_number, raw_row)
                        )
                    continue

                rows = entries["rows"]
                first_row_number, first_raw_row = rows[0]

                merged = dict(first_raw_row)

                # First non-empty name.
                for _, source_row in rows:
                    name = (source_row.get("name") or "").strip()

                    if name:
                        merged["name"] = name
                        break

                # First non-empty normal field.
                for field in supplied_fields:
                    if field in {
                        "name",
                        "isbn",
                        "total_copies",
                    }:
                        continue

                    current = merged.get(field) or ""

                    if not str(current).strip():
                        for _, source_row in rows:
                            value = (
                                source_row.get(field) or ""
                            )

                            if str(value).strip():
                                merged[field] = value
                                break

                merged["isbn"] = key

                # ----------------------------------------------------
                # COPY COUNT
                # ----------------------------------------------------

                if "total_copies" in supplied_fields:

                    explicit_totals = []

                    for _, source_row in rows:

                        raw_total = (
                            source_row.get("total_copies") or ""
                        ).strip()

                        if raw_total:

                            try:
                                explicit_totals.append(
                                    int(float(raw_total))
                                )
                            except (ValueError, TypeError):

                                raise ValueError(
                                    "Invalid total_copies value "
                                    f"for ISBN {key}: "
                                    f"{raw_total}"
                                )

                    if explicit_totals:
                        merged["total_copies"] = str(
                            max(explicit_totals)
                        )
                    else:
                        merged["total_copies"] = str(
                            len(rows)
                        )

                merged_rows.append(
                    (first_row_number, merged)
                )

            raw_rows = merged_rows

        # ------------------------------------------------------------
        # FIELD TYPE CONVERSION
        # ------------------------------------------------------------

        meta = frappe.get_meta(doctype)

        field_types = {}

        for df in meta.fields:
            if df.fieldname:
                field_types[df.fieldname] = df.fieldtype

        numeric_types = {
            "Int",
            "Float",
            "Currency",
            "Percent",
        }

        check_types = {
            "Check",
        }

        def convert_value(field, value):

            if value is None:
                return None

            value = str(value).strip()

            if value == "":
                return None

            fieldtype = field_types.get(field)

            if fieldtype in numeric_types:

                try:

                    number = float(value)

                    if fieldtype == "Int":
                        return int(number)

                    return number

                except (ValueError, TypeError):

                    raise ValueError(
                        f"Invalid numeric value for "
                        f"{field}: {value}"
                    )

            if fieldtype in check_types:

                lowered = value.lower()

                if lowered in {
                    "1",
                    "yes",
                    "true",
                    "on",
                }:
                    return 1

                if lowered in {
                    "0",
                    "no",
                    "false",
                    "off",
                }:
                    return 0

                raise ValueError(
                    f"Invalid checkbox value for "
                    f"{field}: {value}"
                )

            return value

        # ------------------------------------------------------------
        # PROCESS IMPORT
        # ------------------------------------------------------------

        results = []
        inserted = 0
        updated = 0
        errors = 0

        for row_number, raw_row in raw_rows:

            try:

                row = {}

                for field in supplied_fields:

                    value = raw_row.get(field)

                    if value is None:
                        continue

                    value = str(value).strip()

                    if value == "":
                        continue

                    row[field] = convert_value(
                        field,
                        value,
                    )

                record_name = row.get("name")

                # ----------------------------------------------------
                # BOOK MATCHING
                # ----------------------------------------------------

                if doctype == "Book":

                    isbn = row.get("isbn")

                    if isbn:

                        existing_name = frappe.db.get_value(
                            "Book",
                            {"isbn": isbn},
                            "name",
                        )

                        if existing_name:

                            doc = frappe.get_doc(
                                "Book",
                                existing_name,
                            )

                            action = "updated"

                        elif (
                            record_name
                            and frappe.db.exists(
                                "Book",
                                record_name,
                            )
                        ):

                            doc = frappe.get_doc(
                                "Book",
                                record_name,
                            )

                            if (
                                doc.isbn
                                and doc.isbn != isbn
                            ):
                                frappe.throw(
                                    f"Book '{record_name}' already "
                                    f"has ISBN '{doc.isbn}'."
                                )

                            action = "updated"

                        else:

                            doc = frappe.new_doc("Book")
                            action = "inserted"

                    elif (
                        record_name
                        and frappe.db.exists(
                            "Book",
                            record_name,
                        )
                    ):

                        doc = frappe.get_doc(
                            "Book",
                            record_name,
                        )

                        action = "updated"

                    else:

                        doc = frappe.new_doc("Book")
                        action = "inserted"

                # ----------------------------------------------------
                # OTHER MASTER DOCTYPES
                # ----------------------------------------------------

                else:

                    if record_name:

                        if frappe.db.exists(
                            doctype,
                            record_name,
                        ):

                            doc = frappe.get_doc(
                                doctype,
                                record_name,
                            )

                            action = "updated"

                        else:

                            doc = frappe.new_doc(doctype)
                            doc.name = record_name
                            action = "inserted"

                    else:

                        doc = frappe.new_doc(doctype)
                        action = "inserted"

                row.pop("name", None)

                # ----------------------------------------------------
                # SET FIELDS
                # ----------------------------------------------------

                for field, value in row.items():

                    if field == "name":
                        continue

                    if not hasattr(doc, field):
                        continue

                    if value is None:
                        continue

                    doc.set(
                        field,
                        value,
                    )

                # ----------------------------------------------------
                # BOOK INVENTORY SAFETY
                # ----------------------------------------------------

                if doctype == "Book":

                    total = doc.total_copies
                    available = doc.available_copies

                    if total is None:
                        total = 0

                    if available is None:
                        available = total

                    total = int(total)
                    available = int(available)

                    if total < 0:
                        total = 0

                    if available < 0:
                        available = 0

                    if available > total:
                        available = total

                    doc.total_copies = total
                    doc.available_copies = available

                # ----------------------------------------------------
                # SAVE
                # ----------------------------------------------------

                if not dry_run:

                    if action == "updated":

                        doc.save(
                            ignore_permissions=True,
                        )

                    else:

                        doc.insert(
                            ignore_permissions=True,
                        )

                if action == "updated":
                    updated += 1
                else:
                    inserted += 1

                results.append(
                    {
                        "row": row_number,
                        "name": doc.name,
                        "status": (
                            "valid"
                            if dry_run
                            else action
                        ),
                    }
                )

            except Exception as exc:

                errors += 1

                results.append(
                    {
                        "row": row_number,
                        "name": raw_row.get(
                            "name",
                            "",
                        ),
                        "status": "error",
                        "error": str(exc),
                    }
                )

        # ------------------------------------------------------------
        # ATOMIC TRANSACTION
        # ------------------------------------------------------------

        if not dry_run:

            if errors:

                # Do NOT commit a partially imported dataset.
                frappe.db.rollback()

                return {
                    "success": False,
                    "doctype": doctype,
                    "dry_run": False,
                    "total_rows": len(raw_rows),
                    "inserted": 0,
                    "updated": 0,
                    "errors": errors,
                    "rolled_back": True,
                    "results": results,
                }

            frappe.db.commit()

        return {
            "success": errors == 0,
            "doctype": doctype,
            "dry_run": dry_run,
            "total_rows": len(raw_rows),
            "inserted": inserted,
            "updated": updated,
            "errors": errors,
            "rolled_back": False,
            "results": results,
        }

    except Exception:
        frappe.db.rollback()
        raise

@frappe.whitelist()
def get_space_plans():
    """
    Return active space-access plans for the public website.
    """
    return frappe.get_all(
        "Space Plan",
        filters={"active": 1},
        fields=[
            "name",
            "plan_name",
            "billing_period",
            "price",
            "max_hours_per_day",
            "additional_hour_fee",
            "wifi_included",
            "cafe_voucher_amount",
            "description",
            "active",
        ],
        order_by="price asc",
    )


@frappe.whitelist()
def seed_space_plans():
    plans = [
        {
            "name": "Daily Pass",
            "plan_name": "Daily Pass",
            "billing_period": "Per Pass",
            "price": 150,
            "max_hours_per_day": 2,
            "additional_hour_fee": 75,
            "wifi_included": 0,
            "cafe_voucher_amount": 0,
            "description": "Daily space access for up to 2 hours per day. Wi-Fi is not included.",
            "active": 1,
        },
        {
            "name": "Monthly Pass",
            "plan_name": "Monthly Pass",
            "billing_period": "Monthly",
            "price": 1500,
            "max_hours_per_day": 3,
            "additional_hour_fee": 75,
            "wifi_included": 0,
            "cafe_voucher_amount": 0,
            "description": "Monthly space access for up to 3 hours per day. Wi-Fi is not included.",
            "active": 1,
        },
        {
            "name": "Solo Working",
            "plan_name": "Solo Working",
            "billing_period": "Monthly",
            "price": 2250,
            "max_hours_per_day": 0,
            "additional_hour_fee": 0,
            "wifi_included": 1,
            "cafe_voucher_amount": 200,
            "description": "Unlimited working hours with Wi-Fi included and a 200 in-house cafe voucher.",
            "active": 1,
        },
    ]

    for data in plans:
        if frappe.db.exists("Space Plan", data["name"]):
            doc = frappe.get_doc("Space Plan", data["name"])
            for field, value in data.items():
                if field != "name":
                    doc.set(field, value)
            doc.save(ignore_permissions=True)
        else:
            frappe.get_doc({
                "doctype": "Space Plan",
                **data,
            }).insert(ignore_permissions=True)

    frappe.db.commit()

    return frappe.get_all(
        "Space Plan",
        fields=[
            "name",
            "plan_name",
            "billing_period",
            "price",
            "max_hours_per_day",
            "additional_hour_fee",
            "wifi_included",
            "cafe_voucher_amount",
            "active",
        ],
        order_by="price asc",
    )


# ============================================================

# ============================================================
# SPACE WORKING CAPACITY
# ============================================================

def _space_capacity_for_plan(space_plan):
    capacity = frappe.db.get_value(
        "Space Plan",
        space_plan,
        "daily_capacity",
    )

    try:
        capacity = int(capacity or 0)
    except (TypeError, ValueError):
        capacity = 0

    return capacity if capacity > 0 else 4


def _space_usage_for_date(booking_date):
    return frappe.db.count(
        "Space Access",
        filters={
            "status": "Active",
            "start_date": ["<=", booking_date],
            "end_date": [">=", booking_date],
        },
    )


@frappe.whitelist()
def get_space_availability(space_plan, booking_date):
    if not space_plan:
        frappe.throw("Space Plan is required.")

    if not booking_date:
        frappe.throw("Working-space date is required.")

    plan = frappe.get_doc("Space Plan", space_plan)

    if not plan.active:
        frappe.throw("This Space Plan is not currently available.")

    capacity = _space_capacity_for_plan(space_plan)
    used = _space_usage_for_date(booking_date)

    return {
        "success": True,
        "space_plan": space_plan,
        "booking_date": booking_date,
        "capacity": capacity,
        "used": used,
        "available": max(capacity - used, 0),
        "is_available": used < capacity,
    }


def _validate_space_capacity(space_plan, booking_date):
    plan = frappe.get_doc("Space Plan", space_plan)

    booking_date = getdate(booking_date)

    if plan.billing_period == "Per Pass":
        dates_to_check = [booking_date]

    elif plan.billing_period == "Monthly":
        end_date = add_months(booking_date, 1)
        dates_to_check = []

        current_date = booking_date

        while current_date < end_date:
            dates_to_check.append(current_date)
            current_date = add_days(current_date, 1)

    else:
        frappe.throw(
            f"Unsupported Space Plan billing period: "
            f"{plan.billing_period}"
        )

    capacity = _space_capacity_for_plan(space_plan)

    for check_date in dates_to_check:
        used = _space_usage_for_date(check_date)

        if used >= capacity:
            frappe.throw(
                f"The working space is full for {check_date}. "
                "Please choose another date."
            )

    return {
        "capacity": capacity,
        "dates_checked": len(dates_to_check),
        "is_available": True,
    }

# SPACE PLAN PURCHASE / ACCESS
# ============================================================

def _get_space_plan_from_invoice(invoice):
    """
    Return the Space Plan referenced by an invoice, if any.

    Space Plan invoices use Sales Invoice Item.item_type = Other
    and store the Space Plan name in the description.
    """

    for item in invoice.items:

        if item.get("item_type") != "Other":
            continue

        description = (item.get("description") or "").strip()

        if not description:
            continue

        space_plan = frappe.db.get_value(
            "Space Plan",
            {
                "plan_name": description,
                "active": 1,
            },
            "name",
        )

        if space_plan:
            return space_plan

    return None


def _activate_space_access(invoice, payment_name):
    """
    Create Space Access after a Space Plan invoice is successfully paid.

    This function does nothing for Book or Membership invoices.
    """

    space_plan_name = _get_space_plan_from_invoice(invoice)

    if not space_plan_name:
        return None

    member_name = invoice.member

    if not member_name:
        frappe.throw(
            "Space Plan invoice must be linked to a member."
        )

    existing = frappe.db.exists(
        "Space Access",
        {
            "sales_invoice": invoice.name,
            "member": member_name,
        },
    )

    if existing:
        return frappe.get_doc(
            "Space Access",
            existing,
        )

    space_plan = frappe.get_doc(
        "Space Plan",
        space_plan_name,
    )

    start_date = getdate(today())

    remarks = (invoice.remarks or "").strip()
    booking_prefix = "Space Plan Booking Date:"

    if remarks.startswith(booking_prefix):
        selected_date = remarks[len(booking_prefix):].strip()
        if selected_date:
            start_date = getdate(selected_date)

    if space_plan.billing_period == "Per Pass":
        end_date = start_date

    elif space_plan.billing_period == "Monthly":
        end_date = add_months(start_date, 1)

    else:
        frappe.throw(
            f"Unsupported Space Plan billing period: "
            f"{space_plan.billing_period}"
        )

    access = frappe.get_doc({
        "doctype": "Space Access",
        "member": member_name,
        "space_plan": space_plan.name,
        "sales_invoice": invoice.name,
        "payment": payment_name,
        "start_date": start_date,
        "end_date": end_date,
        "status": "Active",
    })

    access.insert(
        ignore_permissions=True
    )

    return access


@frappe.whitelist()
def create_space_plan_invoice(space_plan, customer_name=None, booking_date=None):
    # Frappe may expose request parameters through form_dict depending
    # on how the frontend sends the POST request. Keep the explicit
    # argument first, then fall back to the request value.
    booking_date = booking_date or frappe.form_dict.get("booking_date")
    """
    Create a Sales Invoice for an active Space Plan.

    No Membership is created.
    No Book inventory is affected.
    """

    if not space_plan:
        frappe.throw("Space Plan is required.")

    member_doc = _get_current_member()

    plan = frappe.get_doc(
        "Space Plan",
        space_plan,
    )

    if not plan.active:
        frappe.throw(
            "This Space Plan is not currently available."
        )

    # Accept the selected date when supplied. If the request reaches
    # the backend without the field, use today rather than blocking
    # the existing working-space purchase flow.
    booking_date = booking_date or frappe.form_dict.get("booking_date")
    booking_date = booking_date or today()
    booking_date = getdate(booking_date)

    if booking_date < getdate(today()):
        frappe.throw(
            "Working-space date cannot be in the past."
        )

    _validate_space_capacity(
        space_plan=space_plan,
        booking_date=booking_date,
    )

    if not customer_name:
        customer_name = member_doc.full_name

    price = float(plan.price or 0)

    if price <= 0:
        frappe.throw(
            "Space Plan price must be greater than zero."
        )

    invoice = frappe.get_doc({
        "doctype": "Sales Invoice",
        "member": member_doc.name,
        "customer_name": customer_name,
        "invoice_date": today(),
        "discount": 0,
        "tax": 0,
    })

    invoice.append("items", {
        "item_type": "Other",
        "description": plan.plan_name,
        "qty": 1,
        "rate": price,
    })

    invoice.remarks = (
        f"Space Plan Booking Date: {booking_date}"
    )

    invoice.insert(
        ignore_permissions=True
    )

    invoice.flags.ignore_permissions = True
    invoice.submit()

    return {
        "success": True,
        "invoice": invoice.name,
        "member": member_doc.name,
        "space_plan": plan.name,
        "plan_name": plan.plan_name,
        "price": price,
        "grand_total": invoice.grand_total,
        "payment_status": invoice.payment_status,
    }


@frappe.whitelist()
def get_member_space_access():
    """
    Return Space Plan purchases belonging to the logged-in member.
    """

    member_doc = _get_current_member()

    accesses = frappe.get_all(
        "Space Access",
        filters={
            "member": member_doc.name,
        },
        fields=[
            "name",
            "member",
            "space_plan",
            "sales_invoice",
            "payment",
            "start_date",
            "end_date",
            "status",
            "creation",
        ],
        order_by="creation desc",
    )

    for access in accesses:

        plan = frappe.db.get_value(
            "Space Plan",
            access["space_plan"],
            [
                "plan_name",
                "billing_period",
                "price",
                "max_hours_per_day",
                "additional_hour_fee",
                "wifi_included",
                "cafe_voucher_amount",
                "description",
            ],
            as_dict=True,
        )

        access["plan"] = plan

    return accesses

# ---------------------------------------------------------------------------
# Open Shelf — Direct Booksdata XLSX browser import
# ---------------------------------------------------------------------------

@frappe.whitelist()
def import_books_excel(dry_run=1):
    """Import the real Open Shelf Booksdata Excel workbook.

    Access is restricted to Administrator or System Manager.
    Validation always runs before a real import.
    """

    if frappe.session.user == "Guest":
        frappe.throw("Please login to continue.")

    uploaded = frappe.request.files.get("file")

    if not uploaded:
        frappe.throw("Please select an Excel (.xlsx) file.")

    filename = (uploaded.filename or "").strip()

    if not filename:
        frappe.throw("The uploaded Excel file has no filename.")

    if not filename.lower().endswith(".xlsx"):
        frappe.throw("Only Excel .xlsx files are supported.")

    import os
    import tempfile

    try:
        from open_shelf.open_shelf.import_scripts.import_booksdata import run

        file_bytes = uploaded.read()

        if not file_bytes:
            frappe.throw("The uploaded Excel file is empty.")

        temp_path = None

        try:
            with tempfile.NamedTemporaryFile(
                suffix=".xlsx",
                prefix="openshelf_books_",
                delete=False,
            ) as temp_file:
                temp_file.write(file_bytes)
                temp_path = temp_file.name

            requested_dry_run = str(dry_run).lower() in {
                "1",
                "true",
                "yes",
            }

            def compact_result(result, imported=False):
                import_result = result.get("import_result") or {}
                raw_results = import_result.get("results") or []

                errors = [
                    {
                        "row": item.get("row"),
                        "name": item.get("name"),
                        "error": item.get("error"),
                    }
                    for item in raw_results
                    if item.get("status") == "error"
                ]

                stats = result.get("stats") or {}

                return {
                    "success": not bool(errors),
                    "dry_run": requested_dry_run,
                    "imported": imported,
                    "filename": filename,
                    "message": (
                        "Excel validation completed."
                        if requested_dry_run
                        else (
                            "Excel import completed successfully."
                            if imported
                            else "Excel import was not performed."
                        )
                    ),
                    "source": {
                        "excel_rows": stats.get("excel_rows", 0),
                        "unique_isbn_groups": stats.get(
                            "unique_isbn_groups", 0
                        ),
                        "duplicate_rows_consolidated": stats.get(
                            "duplicate_rows_consolidated", 0
                        ),
                        "no_usable_isbn": stats.get(
                            "no_usable_isbn", 0
                        ),
                        "fallback_matched": stats.get(
                            "fallback_matched", 0
                        ),
                        "fallback_created": stats.get(
                            "fallback_created", 0
                        ),
                    },
                    "masters": {
                        "would_create" if requested_dry_run else "created":
                            stats.get(
                                "masters_would_create"
                                if requested_dry_run
                                else "masters_created",
                                0,
                            )
                    },
                    "books": {
                        "inserted": import_result.get("inserted", 0),
                        "updated": import_result.get("updated", 0),
                        "errors": len(errors),
                    },
                    "errors": errors,
                }

            if requested_dry_run:
                result = run(temp_path, dry_run=1)
                return compact_result(result, imported=False)

            validation = run(temp_path, dry_run=1)
            validation_import = validation.get("import_result") or {}
            validation_results = validation_import.get("results") or []

            validation_errors = [
                {
                    "row": item.get("row"),
                    "name": item.get("name"),
                    "error": item.get("error"),
                }
                for item in validation_results
                if item.get("status") == "error"
            ]

            if validation_errors:
                return {
                    "success": False,
                    "dry_run": False,
                    "imported": False,
                    "filename": filename,
                    "message": (
                        "Import stopped because validation found errors. "
                        "No records were imported."
                    ),
                    "errors": validation_errors,
                }

            result = run(temp_path, dry_run=0)
            return compact_result(result, imported=True)

        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    except frappe.exceptions.ValidationError:
        raise
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "Open Shelf XLSX Import Error",
        )
        raise


# ============================================================
# AUTHENTICATION / ROLE ROUTING
# ============================================================

@frappe.whitelist()
def get_current_user_roles():
    """
    Return the authenticated user's roles for frontend routing.

    System Manager users are treated as Open Shelf administrators.
    All other authenticated users follow the customer flow.
    """

    if frappe.session.user == "Guest":
        frappe.throw("Please login to continue.")

    roles = frappe.get_roles()

    return {
        "username": frappe.session.user,
        "roles": roles,
        "is_admin": "System Manager" in roles,
    }


@frappe.whitelist()
def get_admin_book_sales():
    """Return paid book purchases for the admin dashboard."""
    if frappe.session.user == "Guest":
        frappe.throw("Please login to continue.")

    if "System Manager" not in frappe.get_roles():
        frappe.throw("Not permitted.")

    rows = frappe.db.sql(
        """
        SELECT
            si.name AS invoice,
            si.invoice_date,
            si.customer_name,
            si.member,
            sii.book,
            sii.description AS book_title,
            sii.qty AS quantity,
            sii.rate,
            sii.amount,
            si.grand_total,
            si.payment_status
        FROM `tabSales Invoice` si
        INNER JOIN `tabSales Invoice Item` sii
            ON sii.parent = si.name
        WHERE
            si.docstatus = 1
            AND sii.item_type = 'Book'
            AND EXISTS (
                SELECT 1
                FROM `tabPayment` p
                WHERE
                    p.sales_invoice = si.name
                    AND p.docstatus = 1
                    AND p.payment_status = 'Paid'
            )
        ORDER BY si.invoice_date DESC, si.creation DESC
        """,
        as_dict=True,
    )

    for row in rows:
        row["quantity"] = int(row.get("quantity") or 0)
        row["rate"] = float(row.get("rate") or 0)
        row["amount"] = float(row.get("amount") or 0)
        row["grand_total"] = float(row.get("grand_total") or 0)

    return {
        "success": True,
        "count": len(rows),
        "sales": rows,
    }
