document.addEventListener("DOMContentLoaded", function () {

    const menuButton = document.querySelector(".menu-toggle");
    const navigation = document.querySelector(".main-nav");

    if (menuButton && navigation) {

        menuButton.addEventListener("click", function () {

            if (navigation.style.display === "flex") {
                navigation.style.display = "";
            } else {
                navigation.style.display = "flex";

                navigation.style.position = "absolute";
                navigation.style.top = "78px";
                navigation.style.left = "0";
                navigation.style.right = "0";
                navigation.style.padding = "20px";
                navigation.style.background = "#f8f6f1";
                navigation.style.borderBottom = "1px solid #e6e1d8";
                navigation.style.flexDirection = "column";
            }

        });

    }

});
