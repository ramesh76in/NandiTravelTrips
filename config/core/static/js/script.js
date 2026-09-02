"use strict";

/**
 * Nandi Travel Trips - Global Application Script & UI Helpers
 */
(function () {
    // Toast Notification System
    function showToast(message, type = "info") {
        let container = document.getElementById("nandiToastContainer");
        if (!container) {
            container = document.createElement("div");
            container.id = "nandiToastContainer";
            container.className = "toast-container";
            document.body.appendChild(container);
        }

        const toast = document.createElement("div");
        toast.className = `toast-item toast-${type}`;

        const icon = document.createElement("span");
        icon.className = "toast-icon";
        if (type === "success") icon.innerHTML = '<i class="fas fa-check-circle"></i>';
        else if (type === "error") icon.innerHTML = '<i class="fas fa-exclamation-circle"></i>';
        else icon.innerHTML = '<i class="fas fa-info-circle"></i>';

        const text = document.createElement("span");
        text.className = "toast-text";
        text.textContent = message;

        const closeBtn = document.createElement("button");
        closeBtn.className = "toast-close";
        closeBtn.innerHTML = "&times;";
        closeBtn.onclick = () => toast.remove();

        toast.appendChild(icon);
        toast.appendChild(text);
        toast.appendChild(closeBtn);

        container.appendChild(toast);

        setTimeout(() => {
            toast.classList.add("fade-out");
            setTimeout(() => toast.remove(), 400);
        }, 4000);
    }

    // Active Navigation Highlighter
    function initNavigation() {
        const currentPath = window.location.pathname;
        const navLinks = document.querySelectorAll(".nav-menu li a");

        navLinks.forEach(link => {
            const href = link.getAttribute("href");
            if (href === currentPath || (href !== "/" && currentPath.startsWith(href))) {
                link.classList.add("active");
            } else {
                link.classList.remove("active");
            }
        });
    }

    // Export UI toolkit
    window.NandiUI = {
        showToast,
        initNavigation
    };

    document.addEventListener("DOMContentLoaded", () => {
        initNavigation();
    });
})();