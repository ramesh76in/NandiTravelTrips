"use strict";

/**
 * Nandi Travel Trips - Traveller & Cabin Class Controller
 * Enforces airline capacity constraints and updates UI summaries
 */
(function () {
    let adults = 1;
    let children = 0;
    let infants = 0;
    const MAX_TOTAL_PASSENGERS = 9;

    function updateCounts() {
        const adultEl = document.getElementById("adultCount");
        const childEl = document.getElementById("childCount");
        const infantEl = document.getElementById("infantCount");

        if (adultEl) adultEl.textContent = adults;
        if (childEl) childEl.textContent = children;
        if (infantEl) infantEl.textContent = infants;

        const hiddenAdult = document.getElementById("adult_count");
        const hiddenChild = document.getElementById("child_count");
        const hiddenInfant = document.getElementById("infant_count");

        if (hiddenAdult) hiddenAdult.value = adults;
        if (hiddenChild) hiddenChild.value = children;
        if (hiddenInfant) hiddenInfant.value = infants;

        updateSummary();
    }

    function updateSummary() {
        const summary = document.getElementById("travellerSummary");
        const classText = document.getElementById("travelClassText");
        const travelClassSelect = document.getElementById("travelClass");
        const hiddenClass = document.getElementById("travel_class");

        let travelClass = travelClassSelect ? travelClassSelect.value : "ECONOMY";

        if (summary) {
            const parts = [];
            parts.push(`${adults} Adult${adults > 1 ? "s" : ""}`);
            if (children > 0) parts.push(`${children} Child${children > 1 ? "ren" : ""}`);
            if (infants > 0) parts.push(`${infants} Infant${infants > 1 ? "s" : ""}`);
            summary.textContent = parts.join(", ");
        }

        if (classText) {
            const labels = {
                "ECONOMY": "Economy",
                "PREMIUM_ECONOMY": "Premium Economy",
                "BUSINESS": "Business",
                "FIRST": "First Class"
            };
            classText.textContent = labels[travelClass] || "Economy";
        }

        if (hiddenClass) {
            hiddenClass.value = travelClass;
        }
    }

    function increaseAdults() {
        if (adults + children + infants < MAX_TOTAL_PASSENGERS) {
            adults++;
            updateCounts();
        }
    }

    function decreaseAdults() {
        if (adults > 1) {
            adults--;
            // Number of infants cannot exceed number of adults
            if (infants > adults) {
                infants = adults;
            }
            updateCounts();
        }
    }

    function increaseChildren() {
        if (adults + children + infants < MAX_TOTAL_PASSENGERS) {
            children++;
            updateCounts();
        }
    }

    function decreaseChildren() {
        if (children > 0) {
            children--;
            updateCounts();
        }
    }

    function increaseInfants() {
        if (adults + children + infants < MAX_TOTAL_PASSENGERS && infants < adults) {
            infants++;
            updateCounts();
        }
    }

    function decreaseInfants() {
        if (infants > 0) {
            infants--;
            updateCounts();
        }
    }

    function initTravellerPopup() {
        const travellerBox = document.getElementById("travellerBox");
        const popup = document.getElementById("travellerPopup");
        const closeBtn = document.getElementById("closeTraveller");
        const doneBtn = document.getElementById("travellerDone");
        const travelClassSelect = document.getElementById("travelClass");

        if (travellerBox && popup) {
            travellerBox.addEventListener("click", () => {
                popup.style.display = "block";
            });
        }

        if (closeBtn && popup) {
            closeBtn.addEventListener("click", () => {
                popup.style.display = "none";
            });
        }

        if (doneBtn && popup) {
            doneBtn.addEventListener("click", () => {
                popup.style.display = "none";
                updateSummary();
            });
        }

        if (travelClassSelect) {
            travelClassSelect.addEventListener("change", updateSummary);
        }

        // Close on ESC
        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape" && popup) {
                popup.style.display = "none";
            }
        });

        // Initialize state
        updateCounts();
    }

    // Export functions globally
    window.NandiTravellers = {
        increaseAdults,
        decreaseAdults,
        increaseChildren,
        decreaseChildren,
        increaseInfants,
        decreaseInfants,
        updateSummary,
        init: initTravellerPopup
    };

    window.increaseAdults = increaseAdults;
    window.decreaseAdults = decreaseAdults;
    window.increaseChildren = increaseChildren;
    window.decreaseChildren = decreaseChildren;
    window.increaseInfants = increaseInfants;
    window.decreaseInfants = decreaseInfants;

    document.addEventListener("DOMContentLoaded", initTravellerPopup);
})();