// H01/H02: compare selection (2 to 4 finished evaluations, §4.9), row menus, delete and export modals.
(() => {
    const compareForm = document.querySelector("[data-compare-form]");
    if (compareForm) {
        const boxes = [...compareForm.querySelectorAll("[data-select]")];
        const bar = compareForm.querySelector("[data-selection-bar]");
        const submit = compareForm.querySelector("[data-compare-submit]");
        const sync = () => {
            const selected = boxes.filter((box) => box.checked);
            compareForm.querySelectorAll("[data-selected-count]").forEach((node) => { node.textContent = selected.length; });
            bar.hidden = selected.length === 0;
            submit.disabled = selected.length < 2 || selected.length > 4;
            boxes.forEach((box) => box.closest("[data-row]").classList.toggle("is-selected", box.checked));
        };
        compareForm.addEventListener("change", sync);
        compareForm.querySelector("[data-clear-selection]")?.addEventListener("click", () => {
            boxes.forEach((box) => { box.checked = false; });
            sync();
        });
        sync();
    }

    // Close any open row menu when clicking elsewhere.
    document.addEventListener("click", (event) => {
        document.querySelectorAll("details.menu[open]").forEach((menu) => {
            if (!menu.contains(event.target)) menu.removeAttribute("open");
        });
    });

    document.addEventListener("click", (event) => {
        const trigger = event.target.closest("[data-delete-url]");
        if (trigger) {
            const form = document.querySelector("[data-delete-form]");
            form.action = trigger.dataset.deleteUrl;
            form.querySelector("[data-delete-label]").textContent = `${trigger.dataset.deleteName} · ${trigger.dataset.deleteDate}`;
        }
        const exporter = event.target.closest("[data-export-url]");
        if (exporter) {
            const form = document.querySelector("[data-export-form]");
            form.action = exporter.dataset.exportUrl;
            if (exporter.dataset.exportLabel) form.querySelector("[data-export-label]").textContent = exporter.dataset.exportLabel;
        }
    });

    const exportForm = document.querySelector("[data-export-form]");
    exportForm?.addEventListener("change", () => {
        const isPdf = exportForm.querySelector("[name=formato]:checked").value === "pdf";
        exportForm.querySelector("[data-pdf-only]").hidden = !isPdf;
        exportForm.querySelector("[data-export-submit]").textContent = isPdf ? "Descargar PDF" : "Descargar CSV";
    });
    exportForm?.addEventListener("submit", () => {
        // A download does not navigate away, so close the dialog ourselves.
        setTimeout(() => exportForm.closest(".modal").setAttribute("hidden", ""), 0);
    });
})();
