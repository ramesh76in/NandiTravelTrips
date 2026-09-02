"use strict";

/**
 * Nandi Travel Trips - Trip Type Controller
 * Handles ONEWAY, ROUNDTRIP, and MULTICITY toggles
 */
(function () {
    function changeTripType() {
        const checkedRadio = document.querySelector('input[name="tripSelection"]:checked');
        if (!checkedRadio) return;

        const tripType = checkedRadio.value;
        const hiddenTripType = document.getElementById("trip_type");
        const returnBox = document.getElementById("returnBox");

        if (hiddenTripType) {
            hiddenTripType.value = tripType;
        }

        if (returnBox) {
            if (tripType === "ROUNDTRIP") {
                returnBox.style.display = "block";
            } else {
                returnBox.style.display = "none";
            }
        }
    }

    function initTripType() {
        const tripOptions = document.querySelectorAll('input[name="tripSelection"]');
        tripOptions.forEach(option => {
            option.addEventListener("change", changeTripType);
        });

        // Initialize state on load
        changeTripType();
    }

    window.NandiTripType = {
        init: initTripType,
        change: changeTripType
    };

    document.addEventListener("DOMContentLoaded", initTripType);
})();