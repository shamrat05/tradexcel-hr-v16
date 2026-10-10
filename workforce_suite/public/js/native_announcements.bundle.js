// Compatibility for the installed v16 native Navbar Settings announcement.
// desk.html loads app assets before Application constructs the native navbar.
// Native Toolbar currently resets dismissal AFTER rendering, hiding changed
// notices until a second reload. Use its existing keys, before that rendering.
(() => {
    const notice = frappe.boot?.navbar_settings?.announcement_widget;
    if (notice && notice !== localStorage.getItem("announcement_widget")) {
        localStorage.removeItem("dismissed_announcement_widget");
    }
    $(document).on("app_ready.workforceAnnouncement", () => {
        const close = document.querySelector(".announcement-widget .close-message");
        // Upstream renders a clickable DIV. Leave a future native button alone.
        if (!close || close.tagName === "BUTTON" || close.tabIndex >= 0) return;
        close.setAttribute("role", "button");
        close.setAttribute("tabindex", "0");
        close.setAttribute("aria-label", __("Dismiss site announcement"));
        close.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                close.click(); // Native handler owns dismissal and persistence.
            }
        });
    });
})();
