import frappe


@frappe.whitelist(allow_guest=True)
def get_books(search=None, category=None):
    filters = {}

    if search:
        filters["book_title"] = ["like", f"%{search}%"]

    if category:
        filters["category"] = category

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
            "image",
            "total_copies",
            "available_copies",
            "selling_price",
            "rental_allowed",
        ],
        order_by="modified desc",
        limit_page_length=100,
    )

    for book in books:
        available_copies = int(book.get("available_copies") or 0)

        book["available"] = available_copies > 0

        book["can_rent"] = (
            bool(book.get("rental_allowed"))
            and available_copies > 0
        )

    return books


@frappe.whitelist(allow_guest=True)
def get_book(name):
    if not name:
        frappe.throw("Book name is required.")

    book = frappe.get_doc("Book", name)

    available_copies = int(book.available_copies or 0)

    return {
        "name": book.name,
        "book_title": book.book_title,
        "isbn": book.isbn,
        "author": book.author,
        "publisher": book.publisher,
        "category": book.category,
        "description": book.description,
        "publication_year": book.publication_year,
        "language": book.language,
        "edition": book.edition,
        "image": book.image,
        "total_copies": book.total_copies,
        "available_copies": available_copies,
        "selling_price": book.selling_price,
        "rental_allowed": book.rental_allowed,
        "available": available_copies > 0,
        "can_rent": (
            bool(book.rental_allowed)
            and available_copies > 0
        ),
    }


@frappe.whitelist(allow_guest=True)
def get_categories():
    return frappe.get_all(
        "Category",
        fields=["name"],
        order_by="name asc",
        limit_page_length=100,
    )
