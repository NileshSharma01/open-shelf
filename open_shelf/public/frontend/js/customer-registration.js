document.addEventListener("DOMContentLoaded", function () {

    const form = document.getElementById("customer-registration-form");

    const applicationType = document.getElementById("application_type");

    const membershipPlan = document.getElementById("membership_plan");
    const spacePlan = document.getElementById("space_plan");

    const membershipPlanGroup =
        document.getElementById("membership-plan-group");

    const spacePlanGroup =
        document.getElementById("space-plan-group");

    const planDescription =
        document.getElementById("plan-description");

    const howHeard =
        document.getElementById("how_heard_about_us");

    const howHeardOtherGroup =
        document.getElementById("how-heard-other-group");

    const howHeardOther =
        document.getElementById("how_heard_other");

    const applicationDate =
        document.getElementById("application_date");

    const submitButton =
        document.getElementById("submit-button");

    const formMessage =
        document.getElementById("form-message");


    let plans = {
        membership_plans: [],
        space_plans: []
    };


    function showMessage(message, type) {

        formMessage.textContent = message;

        formMessage.className =
            "message " + type;

    }


    function clearMessage() {

        formMessage.textContent = "";

        formMessage.className =
            "message";

    }


    function setToday() {

        const today =
            new Date().toISOString().split("T")[0];

        applicationDate.value = today;

    }


    function loadPlans() {

        return fetch(
            "/api/method/open_shelf.api.customer_application.get_active_plans",
            {
                method: "GET",
                credentials: "same-origin"
            }
        )
        .then(function (response) {

            if (!response.ok) {
                throw new Error(
                    "Unable to load subscription plans."
                );
            }

            return response.json();

        })
        .then(function (result) {

            const data = result.message || result;

            plans.membership_plans =
                data.membership_plans || [];

            plans.space_plans =
                data.space_plans || [];

            populatePlans();

        });

    }


    function populatePlans() {

        membershipPlan.innerHTML =
            '<option value="">Select membership plan</option>';

        spacePlan.innerHTML =
            '<option value="">Select Solo Working plan</option>';


        plans.membership_plans.forEach(function (plan) {

            const option =
                document.createElement("option");

            option.value = plan.name;

            option.textContent =
                `${plan.plan_name} - ₹${plan.price}`;

            membershipPlan.appendChild(option);

        });


        plans.space_plans.forEach(function (plan) {

            const option =
                document.createElement("option");

            option.value = plan.name;

            option.textContent =
                `${plan.plan_name} - ₹${plan.price}`;

            spacePlan.appendChild(option);

        });

    }


    
function applyPlanFromUrl() {
    const params = new URLSearchParams(window.location.search);
    const plan = params.get("plan");

    if (!plan) {
        return;
    }

    const membershipSelect = document.getElementById("membership_plan");
    const spaceSelect = document.getElementById("space_plan");

    const selectPlan = function (select) {
        if (!select) {
            return false;
        }

        const option = Array.from(select.options).find(
            function (item) {
                return item.value === plan;
            }
        );

        if (!option) {
            return false;
        }

        select.value = plan;
        select.dispatchEvent(new Event("change", { bubbles: true }));

        return true;
    };

    if (selectPlan(membershipSelect)) {
        return;
    }

    selectPlan(spaceSelect);
}

function updatePlanFields() {

        const type =
            applicationType.value;

        clearMessage();

        planDescription.style.display = "none";
        planDescription.innerHTML = "";


        if (type === "Membership") {

            membershipPlanGroup.style.display = "";
            spacePlanGroup.style.display = "none";

            spacePlan.value = "";

        }

        else if (type === "Solo Working") {

            membershipPlanGroup.style.display = "none";
            spacePlanGroup.style.display = "";

            membershipPlan.value = "";

        }

        else {

            membershipPlanGroup.style.display = "";
            spacePlanGroup.style.display = "none";

            membershipPlan.value = "";
            spacePlan.value = "";

        }

    }


    function findSelectedPlan() {

        if (applicationType.value === "Membership") {

            return plans.membership_plans.find(
                function (plan) {
                    return plan.name === membershipPlan.value;
                }
            );

        }

        if (applicationType.value === "Solo Working") {

            return plans.space_plans.find(
                function (plan) {
                    return plan.name === spacePlan.value;
                }
            );

        }

        return null;

    }


    function displayPlanDetails() {

        const plan =
            findSelectedPlan();

        if (!plan) {

            planDescription.style.display = "none";
            planDescription.innerHTML = "";

            return;

        }


        let html = "";

        html += `<strong>${plan.plan_name}</strong><br>`;
        html += `Price: ₹${plan.price}<br>`;

        if (plan.billing_period) {
            html += `Billing: ${plan.billing_period}<br>`;
        }

        if (
            plan.max_hours_per_day !== null &&
            plan.max_hours_per_day !== undefined
        ) {
            if (Number(plan.max_hours_per_day) === 0) {
                html += "Hours: Unlimited<br>";
            }
            else {
                html +=
                    `Maximum hours/day: ${plan.max_hours_per_day}<br>`;
            }
        }

        if (plan.additional_hour_fee) {

            html +=
                `Additional hour: ₹${plan.additional_hour_fee}<br>`;

        }

        html +=
            `Wi-Fi: ${plan.wifi_included ? "Included" : "Not included"}<br>`;

        if (plan.cafe_voucher_amount) {

            html +=
                `Café voucher: ₹${plan.cafe_voucher_amount}<br>`;

        }

        if (plan.description) {

            html += `<br>${plan.description}`;

        }


        planDescription.innerHTML = html;
        planDescription.style.display = "block";

    }


    function updateHowHeard() {

        if (howHeard.value === "Other") {

            howHeardOtherGroup.style.display = "";

        }
        else {

            howHeardOtherGroup.style.display = "none";
            howHeardOther.value = "";

        }

    }


    function getActivities() {

        const selected =
            document.querySelectorAll(
                ".activity-option input[type='checkbox']:checked"
            );

        return Array.from(selected).map(
            function (checkbox) {
                return checkbox.value;
            }
        );

    }


    function getFormData() {

        const data = {

            application_type:
                applicationType.value,

            membership_plan:
                applicationType.value === "Membership"
                    ? membershipPlan.value
                    : null,

            space_plan:
                applicationType.value === "Solo Working"
                    ? spacePlan.value
                    : null,

            title:
                document.getElementById("title").value,

            first_name:
                document.getElementById("first_name").value.trim(),

            last_name:
                document.getElementById("last_name").value.trim(),

            address:
                document.getElementById("address").value.trim(),

            phone:
                document.getElementById("phone").value.trim(),

            email:
                document.getElementById("email").value.trim(),

            date_of_birth:
                document.getElementById("date_of_birth").value || null,

            gender:
                document.getElementById("gender").value,

            occupation:
                document.getElementById("occupation").value.trim(),

            organization_school:
                document.getElementById(
                    "organization_school"
                ).value.trim(),

            how_heard_about_us:
                howHeard.value,

            how_heard_other:
                howHeardOther.value.trim(),

            activities:
                getActivities(),

            whatsapp_consent:
                document.getElementById(
                    "whatsapp_consent"
                ).checked,

            email_consent:
                document.getElementById(
                    "email_consent"
                ).checked,

            application_date:
                applicationDate.value,

            signature: null

        };


        return data;

    }


    function validateFormData(data) {

        if (!data.application_type) {
            return "Please select a service.";
        }

        if (
            data.application_type === "Membership" &&
            !data.membership_plan
        ) {
            return "Please select a Membership Plan.";
        }

        if (
            data.application_type === "Solo Working" &&
            !data.space_plan
        ) {
            return "Please select a Solo Working Plan.";
        }

        if (!data.first_name) {
            return "First Name is required.";
        }

        if (!data.last_name) {
            return "Last Name is required.";
        }

        if (!data.address) {
            return "Address is required.";
        }

        if (!data.phone) {
            return "Phone is required.";
        }

        if (!data.email) {
            return "Email is required.";
        }

        if (
            data.how_heard_about_us === "Other" &&
            !data.how_heard_other
        ) {
            return "Please specify how you heard about us.";
        }

        if (!data.whatsapp_consent) {
            return "WhatsApp community consent is required.";
        }

        if (!data.email_consent) {
            return "Group email consent is required.";
        }

        if (!data.application_date) {
            return "Application date is required.";
        }

        return null;

    }


    function submitApplication(data) {

        submitButton.disabled = true;

        submitButton.textContent =
            "Submitting...";

        clearMessage();


        return fetch(
            "/api/method/open_shelf.api.customer_application.submit_application",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                credentials: "same-origin",

                body: JSON.stringify({
                    data: data
                })
            }
        )
        .then(function (response) {

            return response.json().then(
                function (result) {

                    if (!response.ok) {

                        const message =
                            result.exception ||
                            result.message ||
                            "Application submission failed.";

                        throw new Error(message);

                    }

                    return result;

                }
            );

        })
        .then(function (result) {

            const message =
                result.message || result;

            showMessage(
                `Application submitted successfully. Application ID: ${message.application}`,
                "success"
            );

            window.location.href = "/";

        })
        .catch(function (error) {

            console.error(
                "Customer application error:",
                error
            );

            showMessage(
                error.message ||
                "Unable to submit application.",
                "error"
            );

        })
        .finally(function () {

            submitButton.disabled = false;

            submitButton.textContent =
                "Submit Application";

        });

    }


    applicationType.addEventListener(
        "change",
        updatePlanFields
    );


    membershipPlan.addEventListener(
        "change",
        displayPlanDetails
    );


    spacePlan.addEventListener(
        "change",
        displayPlanDetails
    );


    howHeard.addEventListener(
        "change",
        updateHowHeard
    );


    form.addEventListener(
        "submit",
        function (event) {

            event.preventDefault();

            clearMessage();

            const data =
                getFormData();

            const validationError =
                validateFormData(data);

            if (validationError) {

                showMessage(
                    validationError,
                    "error"
                );

                return;

            }

            submitApplication(data);

        }
    );


    setToday();

    updatePlanFields();

    updateHowHeard();

    loadPlans().catch(
        function (error) {

            console.error(
                "Plan loading error:",
                error
            );

            showMessage(
                "Unable to load subscription plans. Please refresh the page.",
                "error"
            );

        }
    );

});
