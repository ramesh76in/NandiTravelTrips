"use strict";

/**
 * Nandi Travel Trips - Interactive Date Picker Calendar
 * Handles Departure & Return dates with range highlighting and auto-sync
 */
(function () {
    const today = new Date();
    let currentMonth = today.getMonth();
    let currentYear = today.getFullYear();
    let activeInput = "departure"; // "departure" or "return"

    // Default dates: departure = today + 2 days, return = today + 9 days
    let selectedDeparture = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 2);
    let selectedReturn = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 9);

    const monthNames = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ];

    const weekDays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

    function formatDateToISO(date) {
        const y = date.getFullYear();
        const m = String(date.getMonth() + 1).padStart(2, "0");
        const d = String(date.getDate()).padStart(2, "0");
        return `${y}-${m}-${d}`;
    }

    function isSameDate(d1, d2) {
        if (!d1 || !d2) return false;
        return d1.getFullYear() === d2.getFullYear() &&
               d1.getMonth() === d2.getMonth() &&
               d1.getDate() === d2.getDate();
    }

    function updateUIElements() {
        if (selectedDeparture) {
            const depDay = document.getElementById("departure_day");
            const depMonth = document.getElementById("departure_month");
            const depWeekday = document.getElementById("departure_weekday");
            const depInput = document.getElementById("departure_date");

            const depWeekdayName = selectedDeparture.toLocaleDateString("en-US", { weekday: "long" });
            const depMonthYear = `${monthNames[selectedDeparture.getMonth()]} ${selectedDeparture.getFullYear()}`;

            if (depDay) depDay.textContent = selectedDeparture.getDate();
            if (depMonth) depMonth.textContent = depMonthYear;
            if (depWeekday) depWeekday.textContent = depWeekdayName;
            if (depInput) depInput.value = formatDateToISO(selectedDeparture);
        }

        if (selectedReturn) {
            const retDay = document.getElementById("return_day");
            const retMonth = document.getElementById("return_month");
            const retWeekday = document.getElementById("return_weekday");
            const retInput = document.getElementById("return_date");

            const retWeekdayName = selectedReturn.toLocaleDateString("en-US", { weekday: "long" });
            const retMonthYear = `${monthNames[selectedReturn.getMonth()]} ${selectedReturn.getFullYear()}`;

            if (retDay) retDay.textContent = selectedReturn.getDate();
            if (retMonth) retMonth.textContent = retMonthYear;
            if (retWeekday) retWeekday.textContent = retWeekdayName;
            if (retInput) retInput.value = formatDateToISO(selectedReturn);
        }
    }

    function renderCalendar() {
        const monthTitle = document.getElementById("currentMonth");
        const grid = document.getElementById("calendarGrid");

        if (!monthTitle || !grid) return;

        grid.innerHTML = "";
        monthTitle.textContent = `${monthNames[currentMonth]} ${currentYear}`;

        const firstDayIndex = new Date(currentYear, currentMonth, 1).getDay();
        const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();
        const prevMonthDays = new Date(currentYear, currentMonth, 0).getDate();

        const todayStart = new Date(today.getFullYear(), today.getMonth(), today.getDate());

        // Previous month filler days
        for (let i = firstDayIndex; i > 0; i--) {
            const dayNum = prevMonthDays - i + 1;
            const div = document.createElement("div");
            div.className = "calendar-day other-month";
            div.textContent = dayNum;
            grid.appendChild(div);
        }

        // Current month active days
        for (let day = 1; day <= daysInMonth; day++) {
            const div = document.createElement("div");
            div.className = "calendar-day";
            div.textContent = day;

            const thisDate = new Date(currentYear, currentMonth, day);

            if (thisDate < todayStart) {
                div.classList.add("disabled");
            } else {
                // Check if this date is today
                if (isSameDate(thisDate, today)) {
                    div.classList.add("today");
                }

                // Check if departure date
                if (selectedDeparture && isSameDate(thisDate, selectedDeparture)) {
                    div.classList.add("active");
                }

                // Check if return date
                if (selectedReturn && isSameDate(thisDate, selectedReturn)) {
                    div.classList.add("active");
                }

                // Check if in range
                if (selectedDeparture && selectedReturn && thisDate > selectedDeparture && thisDate < selectedReturn) {
                    div.classList.add("range");
                }

                div.addEventListener("click", () => {
                    handleDateSelect(day);
                });
            }

            grid.appendChild(div);
        }

        // Next month filler days to complete standard 42-grid cell layout
        let nextDay = 1;
        while (grid.children.length < 42) {
            const div = document.createElement("div");
            div.className = "calendar-day other-month";
            div.textContent = nextDay++;
            grid.appendChild(div);
        }
    }

    function handleDateSelect(day) {
        const clickedDate = new Date(currentYear, currentMonth, day);

        if (activeInput === "departure") {
            selectedDeparture = clickedDate;
            // If return date is before departure, push return date forward
            if (selectedReturn && selectedReturn < selectedDeparture) {
                selectedReturn = new Date(selectedDeparture.getTime() + 7 * 86400000);
            }
        } else {
            if (clickedDate < selectedDeparture) {
                selectedDeparture = clickedDate;
            } else {
                selectedReturn = clickedDate;
            }
        }

        updateUIElements();
        renderCalendar();
        setTimeout(closeCalendar, 200);
    }

    function previousMonth() {
        const minDate = new Date(today.getFullYear(), today.getMonth(), 1);
        const targetDate = new Date(currentYear, currentMonth - 1, 1);

        if (targetDate < minDate) {
            return; // Don't navigate to past months
        }

        currentMonth--;
        if (currentMonth < 0) {
            currentMonth = 11;
            currentYear--;
        }
        renderCalendar();
    }

    function nextMonth() {
        currentMonth++;
        if (currentMonth > 11) {
            currentMonth = 0;
            currentYear++;
        }
        renderCalendar();
    }

    function openCalendar(type) {
        activeInput = type || "departure";
        const modal = document.getElementById("calendarModal");
        if (modal) {
            modal.classList.add("show");
            // Set current viewed month to match the active date
            const activeDate = (activeInput === "departure" ? selectedDeparture : selectedReturn) || today;
            currentMonth = activeDate.getMonth();
            currentYear = activeDate.getFullYear();
            renderCalendar();
        }
    }

    function closeCalendar() {
        const modal = document.getElementById("calendarModal");
        if (modal) {
            modal.classList.remove("show");
        }
    }

    function initializeCalendar() {
        const departureBox = document.getElementById("departureBox");
        const returnBox = document.getElementById("returnBox");
        const closeBtn = document.getElementById("closeCalendar");
        const overlay = document.getElementById("calendarOverlay");
        const prevBtn = document.getElementById("previousMonth");
        const nextBtn = document.getElementById("nextMonth");

        if (departureBox) {
            departureBox.addEventListener("click", () => openCalendar("departure"));
        }

        if (returnBox) {
            returnBox.addEventListener("click", () => openCalendar("return"));
        }

        if (closeBtn) closeBtn.addEventListener("click", closeCalendar);
        if (overlay) overlay.addEventListener("click", closeCalendar);
        if (prevBtn) prevBtn.addEventListener("click", previousMonth);
        if (nextBtn) nextBtn.addEventListener("click", nextMonth);

        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape") closeCalendar();
        });

        // Initialize UI with dates on startup
        updateUIElements();
        renderCalendar();
    }

    // Expose global methods
    window.NandiCalendar = {
        open: openCalendar,
        close: closeCalendar,
        init: initializeCalendar
    };

    window.closeCalendar = closeCalendar;

    document.addEventListener("DOMContentLoaded", initializeCalendar);
})();