(function () {

    "use strict";

    /*
     * Open Shelf free customer account prompt.
     *
     * This creates only a Frappe Website User.
     * It does NOT create:
     * - Membership
     * - Rental
     * - Space Access
     * - Payment
     */

    const ACCOUNT_CREATED_KEY =
        "open_shelf_account_prompt_seen";

    const PROMPT_DELAY =
        10000;

    const EXCLUDED_PATHS = [
        "/login",
        "/profile",
        "/admin",
        "/customer-registration"
    ];

    function isExcludedPage() {

        const path =
            window.location.pathname
                .replace(/\/+$/, "");

        return EXCLUDED_PATHS.some(
            function (item) {
                return path === item ||
                    path.startsWith(item + "/");
            }
        );

    }

    async function isLoggedIn() {

        try {

            const response =
                await fetch(
                    "/api/method/frappe.auth.get_logged_user",
                    {
                        method: "GET",
                        credentials: "same-origin",
                        headers: {
                            "Accept": "application/json"
                        }
                    }
                );

            if (!response.ok) {
                return false;
            }

            const data =
                await response.json();

            const user =
                data &&
                data.message;

            return Boolean(
                user &&
                user !== "Guest"
            );

        } catch (error) {

            return false;

        }

    }

    function alreadyShown() {

        try {
            return sessionStorage.getItem(
                ACCOUNT_CREATED_KEY
            ) === "1";
        } catch (error) {
            return false;
        }

    }

    function markShown() {

        try {
            sessionStorage.setItem(
                ACCOUNT_CREATED_KEY,
                "1"
            );
        } catch (error) {
            // Ignore storage errors.
        }

    }

    function escapeHtml(value) {

        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");

    }

    function injectStyles() {

        if (
            document.getElementById(
                "open-shelf-account-popup-style"
            )
        ) {
            return;
        }

        const style =
            document.createElement("style");

        style.id =
            "open-shelf-account-popup-style";

        style.textContent = `
            #open-shelf-account-overlay {
                position: fixed;
                inset: 0;
                background: rgba(0,0,0,.65);
                display: none;
                align-items: center;
                justify-content: center;
                z-index: 999999;
                padding: 20px;
            }

            #open-shelf-account-modal {
                width: min(460px, 100%);
                background: #fff;
                border-radius: 14px;
                padding: 30px;
                box-shadow: 0 20px 60px rgba(0,0,0,.25);
                position: relative;
                font-family: inherit;
            }

            #open-shelf-account-modal h2 {
                margin: 0 0 10px;
                font-size: 26px;
            }

            #open-shelf-account-modal p {
                margin: 0 0 20px;
                line-height: 1.6;
            }

            #open-shelf-account-modal label {
                display: block;
                margin: 12px 0 6px;
                font-weight: 600;
            }

            #open-shelf-account-modal input {
                width: 100%;
                box-sizing: border-box;
                padding: 12px;
                border: 1px solid #ccc;
                border-radius: 6px;
                font-size: 15px;
            }

            .open-shelf-account-primary {
                width: 100%;
                margin-top: 18px;
                padding: 13px;
                border: 0;
                border-radius: 6px;
                cursor: pointer;
                font-weight: 600;
                font-size: 15px;
            }

            .open-shelf-account-secondary {
                width: 100%;
                margin-top: 10px;
                padding: 11px;
                background: transparent;
                border: 1px solid #ccc;
                border-radius: 6px;
                cursor: pointer;
                font-size: 15px;
            }

            .open-shelf-account-close {
                position: absolute;
                top: 12px;
                right: 15px;
                border: 0;
                background: transparent;
                font-size: 24px;
                cursor: pointer;
            }

            .open-shelf-account-message {
                margin-top: 12px;
                font-size: 14px;
                line-height: 1.5;
            }
        `;

        document.head.appendChild(style);

    }

    function createModal() {

        if (
            document.getElementById(
                "open-shelf-account-overlay"
            )
        ) {
            return;
        }

        const overlay =
            document.createElement("div");

        overlay.id =
            "open-shelf-account-overlay";

        overlay.innerHTML = `

            <div id="open-shelf-account-modal">

                <h2>
                    Welcome to Open Shelf
                </h2>

                <p>
                    Create your free Open Shelf account
                    to continue your journey with us.
                </p>

                <div id="open-shelf-account-form">

                    <label for="open-shelf-account-name">
                        Full Name
                    </label>

                    <input
                        id="open-shelf-account-name"
                        type="text"
                        autocomplete="name"
                        placeholder="Your full name"
                    >

                    <label for="open-shelf-account-email">
                        Email
                    </label>

                    <input
                        id="open-shelf-account-email"
                        type="email"
                        autocomplete="email"
                        placeholder="you@example.com"
                    >

                    <button
                        type="button"
                        class="open-shelf-account-primary"
                        id="open-shelf-create-account"
                    >
                        Create Free Account
                    </button>

                    <button
                        type="button"
                        class="open-shelf-account-secondary"
                        id="open-shelf-login-account"
                    >
                        I already have an account
                    </button>

                    <div
                        id="open-shelf-account-message"
                        class="open-shelf-account-message"
                    ></div>

                </div>

            </div>

        `;

        document.body.appendChild(overlay);

        document
            .getElementById(
                "open-shelf-login-account"
            )
            .addEventListener(
                "click",
                function () {

                    const redirect =
                        encodeURIComponent(
                            window.location.pathname +
                            window.location.search
                        );

                    window.location.href =
                        "/login?redirect=" +
                        redirect;

                }
            );

        document
            .getElementById(
                "open-shelf-create-account"
            )
            .addEventListener(
                "click",
                createAccount
            );

    }

    async function createAccount() {

        const nameInput =
            document.getElementById(
                "open-shelf-account-name"
            );

        const emailInput =
            document.getElementById(
                "open-shelf-account-email"
            );

        const button =
            document.getElementById(
                "open-shelf-create-account"
            );

        const message =
            document.getElementById(
                "open-shelf-account-message"
            );

        const fullName =
            nameInput.value.trim();

        const email =
            emailInput.value.trim().toLowerCase();

        if (!fullName) {

            message.textContent =
                "Please enter your full name.";

            return;

        }

        if (
            !email ||
            !email.includes("@")
        ) {

            message.textContent =
                "Please enter a valid email address.";

            return;

        }

        button.disabled = true;
        button.textContent =
            "Creating account...";

        message.textContent = "";

        try {

            const response =
                await fetch(
                    "/api/method/open_shelf.api.customer_account.create_free_account",
                    {
                        method: "POST",
                        headers: {
                            "Content-Type":
                                "application/json"
                        },
                        credentials: "same-origin",
                        body: JSON.stringify({
                            full_name: fullName,
                            email: email
                        })
                    }
                );

            const result =
                await response.json();

            if (
                !response.ok ||
                result.exc
            ) {
                throw new Error(
                    result.exception ||
                    result.message ||
                    "Unable to create account."
                );
            }

            message.innerHTML =
                "Your free account has been created. " +
                "Please check your email for the account setup instructions.";

            button.style.display =
                "none";

            markShown();

            setTimeout(
                function () {

                    window.location.href =
                        "/assets/open_shelf/frontend/pages/profile.html";

                },
                2500
            );

        } catch (error) {

            console.error(
                "Open Shelf account creation error:",
                error
            );

            message.textContent =
                error.message ||
                "Unable to create account.";

            button.disabled = false;
            button.textContent =
                "Create Free Account";

        }

    }

    function showModal() {

        injectStyles();
        createModal();

        const overlay =
            document.getElementById(
                "open-shelf-account-overlay"
            );

        overlay.style.display =
            "flex";

    }

    async function init() {

        if (isExcludedPage()) {
            return;
        }

        if (await isLoggedIn()) {
            return;
        }

        setTimeout(
            showModal,
            PROMPT_DELAY
        );

    }

    if (
        document.readyState ===
        "loading"
    ) {

        document.addEventListener(
            "DOMContentLoaded",
            init
        );

    } else {

        init();

    }

})();


/* ============================================================
   OPEN SHELF ACCOUNT NAVIGATION

   Guest:
       Login -> /login

   Logged-in Website User:
       My Account -> /profile

   This only controls the account link.
   It does not modify other navigation links.
   ============================================================ */

(function () {

    "use strict";

    function updateAccountNavigation() {

        fetch(
            "/api/method/frappe.auth.get_logged_user",
            {
                credentials: "same-origin",
                cache: "no-store"
            }
        )
        .then(function (response) {
            if (!response.ok) {
                throw new Error(
                    "Unable to determine login status."
                );
            }

            return response.json();
        })
        .then(function (data) {

            const username =
                data && data.message
                    ? String(data.message)
                    : "Guest";

            const loggedIn =
                username !== "" &&
                username !== "Guest";

            document
                .querySelectorAll("a")
                .forEach(function (link) {

                    const href =
                        (link.getAttribute("href") || "")
                        .trim();

                    const text =
                        (link.textContent || "")
                        .trim()
                        .toLowerCase();

                    /*
                     * Only identify actual account links.
                     *
                     * We deliberately do NOT modify arbitrary
                     * links on the website.
                     */
                    const isLoginLink =
                        href === "/login" ||
                        href === "/login/" ||
                        href.indexOf("/login?") === 0 ||
                        text === "login";

                    const isMyAccountLink =
                        text === "my account" ||
                        href === "/me" ||
                        href === "/me/" ||
                        href === "/profile" ||
                        href === "/profile/";

                    if (loggedIn && (isLoginLink || isMyAccountLink)) {

                        link.textContent = "My Account";
                        link.setAttribute(
                            "href",
                            "/assets/open_shelf/frontend/pages/profile.html"
                        );

                    } else if (!loggedIn && isMyAccountLink) {

                        link.textContent = "Login";
                        link.setAttribute(
                            "href",
                            "/login"
                        );

                    }

                });

        })
        .catch(function (error) {

            console.warn(
                "Open Shelf account navigation check failed:",
                error
            );

        });

    }

    function startAccountNavigationCheck() {

        updateAccountNavigation();

        /*
         * Some Open Shelf pages render their navigation after
         * the initial page load. Check a few times so the common
         * navigation is corrected without changing page content.
         */
        setTimeout(updateAccountNavigation, 300);
        setTimeout(updateAccountNavigation, 1000);
        setTimeout(updateAccountNavigation, 2000);
        setTimeout(updateAccountNavigation, 4000);

    }

    if (document.readyState === "loading") {

        document.addEventListener(
            "DOMContentLoaded",
            startAccountNavigationCheck
        );

    } else {

        startAccountNavigationCheck();

    }

})();

