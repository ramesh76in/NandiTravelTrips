"use strict";

/**
 * Nandi Travel Trips - Airport Search Modal Controller
 * Modernized, XSS-Safe, and LocalStorage-Persisted
 */
(function () {
    let selectedField = "from";
    const STORAGE_KEY = "nandi_recent_airports";

    // Initialize Recent Searches from localStorage
    function getRecentAirports() {
        try {
            const data = localStorage.getItem(STORAGE_KEY);
            return data ? JSON.parse(data) : [];
        } catch (e) {
            console.error("Failed to read recent airports from localStorage:", e);
            return [];
        }
    }

    function saveRecentAirport(airport) {
        try {
            let recent = getRecentAirports();
            recent = recent.filter(a => a.code !== airport.code);
            recent.unshift({
                city: airport.city,
                code: airport.code,
                airport: airport.airport,
                country: airport.country
            });
            if (recent.length > 5) {
                recent = recent.slice(0, 5);
            }
            localStorage.setItem(STORAGE_KEY, JSON.stringify(recent));
            renderRecentAirports();
        } catch (e) {
            console.error("Failed to save recent airport to localStorage:", e);
        }
    }

    function createAirportCard(airport) {
        const itemDiv = document.createElement("div");
        itemDiv.className = "airport-item";
        itemDiv.setAttribute("data-code", airport.code);
        itemDiv.setAttribute("data-city", airport.city);

        const strong = document.createElement("strong");
        strong.textContent = `${airport.city} (${airport.code})`;

        const p = document.createElement("p");
        p.textContent = `${airport.airport} • ${airport.country}`;

        itemDiv.appendChild(strong);
        itemDiv.appendChild(p);

        itemDiv.addEventListener("click", () => {
            selectAirport(airport);
        });

        return itemDiv;
    }

    function renderRecentAirports() {
        const recentContainer = document.getElementById("recentAirportList");
        if (!recentContainer) return;

        recentContainer.innerHTML = "";
        const recent = getRecentAirports();

        if (recent.length === 0) {
            // Default seed if empty
            const defaultItem = {
                city: "Jaipur",
                code: "JAI",
                airport: "Jaipur International Airport",
                country: "India"
            };
            recentContainer.appendChild(createAirportCard(defaultItem));
            return;
        }

        const fragment = document.createDocumentFragment();
        recent.forEach(airport => {
            fragment.appendChild(createAirportCard(airport));
        });
        recentContainer.appendChild(fragment);
    }

    function loadAirports() {
        const indianContainer = document.getElementById("airportList");
        const internationalContainer = document.getElementById("internationalAirportList");

        if (indianContainer) {
            indianContainer.innerHTML = "";
            const fragIndian = document.createDocumentFragment();
            const domesticList = window.NandiAirports.filter(a => a.category === "domestic");
            domesticList.forEach(airport => {
                fragIndian.appendChild(createAirportCard(airport));
            });
            indianContainer.appendChild(fragIndian);
        }

        if (internationalContainer) {
            internationalContainer.innerHTML = "";
            const fragIntl = document.createDocumentFragment();
            const intlList = window.NandiAirports.filter(a => a.category === "international");
            intlList.forEach(airport => {
                fragIntl.appendChild(createAirportCard(airport));
            });
            internationalContainer.appendChild(fragIntl);
        }

        renderRecentAirports();
    }

    function openModal(field) {
        selectedField = field;
        const modal = document.getElementById("airportModal");
        const searchInput = document.getElementById("airportSearchInput");
        if (modal) {
            modal.style.display = "block";
            if (searchInput) {
                searchInput.value = "";
                filterAirports("");
                setTimeout(() => searchInput.focus(), 50);
            }
        }
    }

    function closeModal() {
        const modal = document.getElementById("airportModal");
        if (modal) {
            modal.style.display = "none";
        }
    }

    function selectAirport(airport) {
        if (selectedField === "from") {
            const cityEl = document.getElementById("from_city");
            const airportEl = document.getElementById("from_airport");
            const countryEl = document.getElementById("from_country");
            const hiddenCode = document.getElementById("origin_code");

            if (cityEl) cityEl.textContent = airport.city;
            if (airportEl) airportEl.textContent = `${airport.code} • ${airport.airport}`;
            if (countryEl) countryEl.textContent = airport.country;
            if (hiddenCode) hiddenCode.value = airport.code;
        } else {
            const cityEl = document.getElementById("to_city");
            const airportEl = document.getElementById("to_airport");
            const countryEl = document.getElementById("to_country");
            const hiddenCode = document.getElementById("destination_code");

            if (cityEl) cityEl.textContent = airport.city;
            if (airportEl) airportEl.textContent = `${airport.code} • ${airport.airport}`;
            if (countryEl) countryEl.textContent = airport.country;
            if (hiddenCode) hiddenCode.value = airport.code;
        }

        saveRecentAirport(airport);
        closeModal();
    }

    function filterAirports(query) {
        const q = (query || "").trim().toLowerCase();
        const allItems = document.querySelectorAll("#airportList .airport-item, #internationalAirportList .airport-item");
        
        allItems.forEach(item => {
            const text = (item.textContent || "").toLowerCase();
            if (!q || text.includes(q)) {
                item.style.display = "";
            } else {
                item.style.display = "none";
            }
        });
    }

    function initAirportModal() {
        const fromBox = document.getElementById("fromBox");
        const toBox = document.getElementById("toBox");
        const closeBtn = document.getElementById("closeAirportModal");
        const overlay = document.getElementById("airportOverlay");
        const searchInput = document.getElementById("airportSearchInput");

        if (fromBox) {
            fromBox.addEventListener("click", () => openModal("from"));
        }

        if (toBox) {
            toBox.addEventListener("click", () => openModal("to"));
        }

        if (closeBtn) {
            closeBtn.addEventListener("click", closeModal);
        }

        if (overlay) {
            overlay.addEventListener("click", closeModal);
        }

        if (searchInput) {
            searchInput.addEventListener("input", function () {
                filterAirports(this.value);
            });
        }

        // Close on ESC
        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape") {
                closeModal();
            }
        });

        loadAirports();
    }

    // Export to global namespace
    window.NandiAirportModal = {
        open: openModal,
        close: closeModal,
        select: selectAirport,
        init: initAirportModal
    };

    // Backward compatibility for inline functions
    window.selectAirport = (city, code, airport, country) => {
        selectAirport({ city, code, airport, country });
    };

    document.addEventListener("DOMContentLoaded", initAirportModal);
})();