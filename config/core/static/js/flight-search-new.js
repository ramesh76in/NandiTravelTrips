"use strict";

/**
 * Nandi Travel Trips - Flight Search Controller
 * Handles form validation, airport swapping, and results submission
 */
(function () {
    function initDefaults() {
        const originInput = document.getElementById("origin_code");
        const destInput = document.getElementById("destination_code");

        if (originInput && !originInput.value) {
            originInput.value = "JAI";
        }
        if (destInput && !destInput.value) {
            destInput.value = "BOM";
        }

        const tripTypeInput = document.getElementById("trip_type");
        if (tripTypeInput && !tripTypeInput.value) {
            tripTypeInput.value = "ONEWAY";
        }

        const travelClassInput = document.getElementById("travel_class");
        if (travelClassInput && !travelClassInput.value) {
            travelClassInput.value = "ECONOMY";
        }
    }

    function initSwapButton() {
        const swapBtn = document.getElementById("swapButton");
        if (!swapBtn) return;

        swapBtn.addEventListener("click", () => {
            // Animate button
            swapBtn.style.transform = "rotate(180deg)";
            setTimeout(() => {
                swapBtn.style.transform = "";
            }, 350);

            // Swap text contents
            const fromCity = document.getElementById("from_city");
            const toCity = document.getElementById("to_city");
            const fromAirport = document.getElementById("from_airport");
            const toAirport = document.getElementById("to_airport");
            const fromCountry = document.getElementById("from_country");
            const toCountry = document.getElementById("to_country");

            const originInput = document.getElementById("origin_code");
            const destInput = document.getElementById("destination_code");

            if (fromCity && toCity) {
                const tempCity = fromCity.textContent;
                fromCity.textContent = toCity.textContent;
                toCity.textContent = tempCity;
            }

            if (fromAirport && toAirport) {
                const tempAirport = fromAirport.textContent;
                fromAirport.textContent = toAirport.textContent;
                toAirport.textContent = tempAirport;
            }

            if (fromCountry && toCountry) {
                const tempCountry = fromCountry.textContent;
                fromCountry.textContent = toCountry.textContent;
                toCountry.textContent = tempCountry;
            }

            if (originInput && destInput) {
                const tempCode = originInput.value;
                originInput.value = destInput.value;
                destInput.value = tempCode;
            }
        });
    }

    function validateSearchForm() {
        const origin = (document.getElementById("origin_code")?.value || "").trim();
        const destination = (document.getElementById("destination_code")?.value || "").trim();
        const departure = (document.getElementById("departure_date")?.value || "").trim();
        const adults = parseInt(document.getElementById("adult_count")?.value || "1", 10);

        if (!origin) {
            showNotice("Please select a departure city (From).", "error");
            return false;
        }

        if (!destination) {
            showNotice("Please select an arrival destination (To).", "error");
            return false;
        }

        if (origin.toUpperCase() === destination.toUpperCase()) {
            showNotice("Departure and destination airports cannot be the same.", "error");
            return false;
        }

        if (!departure) {
            showNotice("Please select a departure date.", "error");
            return false;
        }

        if (isNaN(adults) || adults < 1) {
            showNotice("At least one adult traveller is required.", "error");
            return false;
        }

        return true;
    }

    function showNotice(message, type) {
        if (window.NandiUI && window.NandiUI.showToast) {
            window.NandiUI.showToast(message, type);
        } else {
            // Fallback lightweight banner if toast not loaded yet
            const notice = document.createElement("div");
            notice.className = `nandi-notice ${type}`;
            notice.textContent = message;
            document.body.appendChild(notice);
            setTimeout(() => notice.remove(), 4000);
        }
    }

    function initSearchForm() {
        const form = document.querySelector(".flight-booking-section form");
        const searchButton = document.getElementById("searchFlightButton");

        if (form) {
            form.setAttribute("action", "/flights/results/");
            form.setAttribute("method", "GET");

            form.addEventListener("submit", function (e) {
                if (!validateSearchForm()) {
                    e.preventDefault();
                    return false;
                }
            });
        }

        if (searchButton && !form) {
            searchButton.addEventListener("click", function (e) {
                if (!validateSearchForm()) {
                    e.preventDefault();
                    return false;
                }
                const origin = document.getElementById("origin_code")?.value || "JAI";
                const dest = document.getElementById("destination_code")?.value || "BOM";
                const dep = document.getElementById("departure_date")?.value || "";
                const adults = document.getElementById("adult_count")?.value || "1";
                window.location.href = `/flights/results/?origin_code=${origin}&destination_code=${dest}&departure_date=${dep}&adults=${adults}`;
            });
        }
    }

    function init() {
        initDefaults();
        initSwapButton();
        initSearchForm();
    }

    window.NandiFlightSearch = {
        init,
        validate: validateSearchForm
    };

    document.addEventListener("DOMContentLoaded", init);
})();