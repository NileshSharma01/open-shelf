import frappe

from open_shelf.api.commerce import create_book_invoice


def _session_customer_name(member_doc=None):
    if member_doc:
        return member_doc.full_name

    user = frappe.get_doc("User", frappe.session.user)

    return (
        user.full_name
        or user.first_name
        or frappe.session.user
    )


@frappe.whitelist()
def checkout_cart(items, customer_name=None):
    """
    Create a submitted book-sale invoice from the website cart.

    Payment is completed separately through Razorpay.
    """

    if frappe.session.user == "Guest":
        frappe.throw("Please login to continue.")

    from open_shelf.api.api import _get_current_member

    member_doc = _get_current_member()

    if not customer_name:
        customer_name = _session_customer_name(member_doc)

    invoice = create_book_invoice(
        items=items,
        customer_name=customer_name,
        member=member_doc.name if member_doc else None,
        channel="Online",
    )

    return {
        "success": True,
        "invoice": invoice.name,
        "member": invoice.member,
        "customer_name": invoice.customer_name,
        "subtotal": invoice.subtotal,
        "grand_total": invoice.grand_total,
        "payment_status": invoice.payment_status,
    }
