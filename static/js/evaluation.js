// Evaluation stages: modals and autosave feedback (HTMX posts each control on change, §6.4).
(() => {
    document.addEventListener("click", (event) => {
        const opener = event.target.closest("[data-open-modal]");
        if (opener) document.getElementById(opener.dataset.openModal)?.removeAttribute("hidden");
        const closer = event.target.closest("[data-close-modal]");
        if (closer) closer.closest(".modal")?.setAttribute("hidden", "");
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") document.querySelectorAll(".modal:not([hidden])").forEach((m) => m.setAttribute("hidden", ""));
    });

    const status = document.querySelector("[data-save-status]");
    const setStatus = (text, isError) => {
        if (!status) return;
        status.textContent = text;
        status.classList.toggle("is-error", isError);
    };
    document.body.addEventListener("htmx:beforeRequest", () => setStatus("Guardando…", false));
    const toast = document.querySelector("[data-offline-toast]");
    let failed = null;
    document.body.addEventListener("htmx:afterRequest", (event) => {
        // Failed saves keep the user's choice on screen and say so (§6.4, G02).
        if (event.detail.successful) {
            setStatus("Guardado automáticamente hace un momento", false);
            if (toast) toast.hidden = true;
            return;
        }
        if (event.detail.xhr.status === 401) {
            document.getElementById("session-modal")?.removeAttribute("hidden");
            return;
        }
        failed = event.detail.elt;
        setStatus("No se pudo guardar", true);
        if (toast) toast.hidden = false;
    });
    document.querySelector("[data-retry]")?.addEventListener("click", () => {
        if (failed && window.htmx) window.htmx.trigger(failed, "change");
    });
    document.body.addEventListener("htmx:configRequest", (event) => {
        const token = document.querySelector("[name=csrfmiddlewaretoken]");
        if (token) event.detail.headers["X-CSRFToken"] = token.value;
    });
})();

// E3/H02 detail filter: "Todos" | "Debilidades y amenazas".
document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-filter]");
    if (!button) return;
    const scope = button.closest("[data-filter-scope]");
    scope.querySelectorAll("[data-filter]").forEach((item) => item.classList.toggle("is-active", item === button));
    scope.classList.toggle("is-problems-only", button.dataset.filter === "problems");
    const selector = button.dataset.filter === "problems" ? "tbody tr[data-problem]" : "tbody tr";
    const counter = scope.querySelector("[data-visible-count]");
    if (counter) counter.textContent = scope.querySelectorAll(selector).length;
});
