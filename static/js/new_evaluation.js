// D02: show the panel of the chosen software source and warn about non-free licenses (§1).
(() => {
    const form = document.querySelector("[data-new-evaluation]");
    if (!form) return;
    const panels = form.querySelectorAll("[data-mode-panel]");
    const license = form.querySelector("[name=license_type]");
    const notice = form.querySelector("[data-license-notice]");

    const sync = () => {
        const mode = form.querySelector("[name=mode]:checked")?.value;
        panels.forEach((panel) => { panel.hidden = panel.dataset.modePanel !== mode; });
        if (license && notice) notice.hidden = !license.value || license.value === "libre";
        // Mirrors the server rule so the button is only enabled when the form can be submitted.
        const ready = mode === "existente"
            ? Boolean(form.querySelector("[name=software]")?.value)
            : Boolean(form.querySelector("[name=name]")?.value.trim() && license?.value);
        form.querySelector("[data-submit]").disabled = !ready;
    };
    form.addEventListener("change", sync);
    form.addEventListener("input", sync);
    sync();
})();
