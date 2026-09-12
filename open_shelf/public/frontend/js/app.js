(function () {

    "use strict";


    window.OpenShelf = {

        apiGet: async function (url) {

            const response = await fetch(url, {
                method: "GET",
                credentials: "include",
                headers: {
                    "Accept": "application/json"
                }
            });

            let data = {};

            try {
                data = await response.json();
            } catch (error) {
                throw new Error("Invalid server response.");
            }

            if (!response.ok || data.exception || data.exc) {
                throw new Error(
                    data.exception ||
                    data.message ||
                    "Request failed."
                );
            }

            return data.message;
        },


        apiPost: async function (url, body) {

            let csrfToken = "";

            /*
             * The Open Shelf frontend is served as a static asset page.
             * Therefore we obtain the CSRF token from our authenticated
             * Frappe session through a read-only GET request.
             */
            const csrfResponse = await fetch(
                "/api/method/open_shelf.api.api.get_open_shelf_csrf_token",
                {
                    method: "GET",
                    credentials: "include",
                    headers: {
                        "Accept": "application/json"
                    }
                }
            );

            let csrfData = {};

            try {
                csrfData = await csrfResponse.json();
            } catch (error) {
                throw new Error(
                    "Unable to obtain the security token."
                );
            }

            if (
                !csrfResponse.ok ||
                csrfData.exception ||
                csrfData.exc ||
                !csrfData.message
            ) {
                throw new Error(
                    csrfData.exception ||
                    csrfData.message ||
                    "Unable to obtain the security token."
                );
            }

            csrfToken = csrfData.message;

            const headers = {
                "Content-Type":
                    "application/x-www-form-urlencoded; charset=UTF-8",
                "Accept": "application/json",
                "X-Frappe-CSRF-Token": csrfToken
            };

            const response = await fetch(url, {
                method: "POST",
                credentials: "include",
                headers: headers,
                body: new URLSearchParams(body || {})
            });

            let data = {};

            try {
                data = await response.json();
            } catch (error) {
                throw new Error(
                    "Invalid server response."
                );
            }

            if (!response.ok || data.exception || data.exc) {
                throw new Error(
                    data.exception ||
                    data.message ||
                    "Request failed."
                );
            }

            return data.message;
        },

        getCurrentUser: async function () {

            return await this.apiGet(
                "/api/method/frappe.auth.get_logged_user"
            );

        },


        isGuest: async function () {

            const user =
                await this.getCurrentUser();

            return !user || user === "Guest";

        },


        escapeHtml: function (value) {

            if (
                value === null ||
                value === undefined
            ) {
                return "";
            }

            return String(value)
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        },


        formatPrice: function (value) {

            return new Intl.NumberFormat(
                "en-IN",
                {
                    style: "currency",
                    currency: "INR",
                    maximumFractionDigits: 0
                }
            ).format(
                Number(value || 0)
            );

        }

    };


    document.addEventListener(
        "DOMContentLoaded",
        function () {

            const yearElement =
                document.getElementById("current-year");

            if (yearElement) {
                yearElement.textContent =
                    new Date().getFullYear();
            }

        }
    );

})();
