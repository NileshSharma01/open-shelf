app_name = "open_shelf"
app_title = "Open Shelf"
app_publisher = "Open Shelf Reading Foundation"
app_description = "Open Shelf Reading Foundation website and library management system"
app_email = ""
app_license = "MIT"

# Home Page
home_page = "home"

# Website
website_context = {
    "favicon": "/assets/open_shelf/images/favicon.png"
}

# Includes
# app_include_css = "/assets/open_shelf/css/open_shelf.css"
# app_include_js = "/assets/open_shelf/js/open_shelf.js"

# Jinja
# jinja = {
#     "methods": "open_shelf.utils.jinja_methods",
#     "filters": "open_shelf.utils.jinja_filters"
# }

# Website Route Rules
website_redirects = [
    {"source": "/me", "target": "/assets/open_shelf/frontend/pages/profile.html", "redirect_http_status": 302},
]

website_route_rules = [
    {"from_route": "/me", "to_route": "/profile"},
    {"from_route": "/catalogue", "to_route": "catalogue"},
    {"from_route": "/space-plans", "to_route": "space-plans"},
    {"from_route": "/membership", "to_route": "membership"},
    {"from_route": "/rental", "to_route": "rental"},
    {"from_route": "/events", "to_route": "events"},
    {"from_route": "/about", "to_route": "about"},
    {"from_route": "/contact", "to_route": "contact"},
    {"from_route": "/customer-registration", "to_route": "customer-registration/customer-registration"},
]

# Document Events
# doc_events = {
#     "*": {
#         "on_update": "method",
#         "on_submit": "method",
#         "on_cancel": "method",
#     }
# }

web_include_js = ["/assets/open_shelf/frontend/js/visitor-account.js"]
