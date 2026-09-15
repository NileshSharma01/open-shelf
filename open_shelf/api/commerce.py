import frappe
from frappe.utils import today


def parse_item_list(items):
    if not items:
        frappe.throw("Please add at least one book.")

    if isinstance(items, str):
        items = frappe.parse_json(items)

    if not isinstance(items, list):
        frappe.throw("Invalid items data.")

    return items


def append_book_items(invoice, items):
    subtotal = 0

    for item in items:
        book_name = item.get("book") or item.get("name")

        if not book_name:
            frappe.throw("Please select a book.")

        quantity = int(item.get("quantity", item.get("qty", 0)) or 0)

        if quantity <= 0:
            frappe.throw("Quantity must be greater than zero.")

        book = frappe.get_doc("Book", book_name)
        available = int(book.available_copies or 0)

        if quantity > available:
            frappe.throw(
                f"Only {available} copies of {book.book_title} are available."
            )

        rate = float(book.selling_price or 0)

        if rate <= 0:
            frappe.throw(
                f"'{book.book_title}' does not have a selling price."
            )

        subtotal += quantity * rate

        invoice.append(
            "items",
            {
                "item_type": "Book",
                "book": book.name,
                "description": book.book_title,
                "qty": quantity,
                "rate": rate,
            },
        )

    return subtotal


def create_book_invoice(
    items,
    customer_name=None,
    member=None,
    discount=0,
    tax=0,
    channel="Online",
):
    items = parse_item_list(items)
    discount = float(discount or 0)
    tax = float(tax or 0)

    invoice = frappe.get_doc(
        {
            "doctype": "Sales Invoice",
            "member": member or None,
            "customer_name": customer_name,
            "invoice_date": today(),
            "discount": discount,
            "tax": tax,
            "channel": channel,
        }
    )

    append_book_items(invoice, items)
    invoice.insert(ignore_permissions=True)
    invoice.flags.ignore_permissions = True
    invoice.submit()
    invoice.reload()

    return invoice


def record_paid_payment(
    invoice,
    amount,
    payment_method,
    member=None,
    reference=None,
):
    payment = frappe.get_doc(
        {
            "doctype": "Payment",
            "sales_invoice": invoice.name,
            "member": member or invoice.member,
            "payment_date": today(),
            "amount": amount,
            "payment_method": payment_method,
            "payment_status": "Paid",
            "reference": reference,
        }
    )

    payment.insert(ignore_permissions=True)
    payment.flags.ignore_permissions = True
    payment.submit()
    invoice.reload()

    return payment
