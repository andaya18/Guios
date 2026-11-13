// C01: add an evaluation as soon as it is picked and toggle "only FODA differences".
(() => {
    document.querySelector("[data-autosubmit-select]")?.addEventListener("change", (event) => {
        if (event.target.value) event.target.form.submit();
    });
    document.querySelector("[data-only-differences]")?.addEventListener("change", (event) => {
        document.querySelector("[data-compare-scope]")?.classList.toggle("is-differences-only", event.target.checked);
    });
})();
