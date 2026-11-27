(() => {
    const form = document.querySelector("[data-ai-recalculate]");
    if (!form) return;

    const status = document.querySelector("[data-ai-status]");
    const button = form.querySelector("button[type=submit]");
    const buttonLabel = button.textContent;
    let inFlight = false;

    const recalculate = async () => {
        if (inFlight) return;
        inFlight = true;
        button.disabled = true;
        button.textContent = "Consultando IA...";
        status.hidden = false;
        status.textContent = "La IA está evaluando los documentos. Puedes seguir usando esta página mientras termina.";

        try {
            const response = await fetch(form.action, {
                method: "POST",
                body: new FormData(form),
                headers: { Accept: "application/json" },
                credentials: "same-origin",
            });
            if (!response.ok) throw new Error(`El servidor respondió HTTP ${response.status}.`);
            const result = await response.json();
            if (!["ia", "respaldo"].includes(result.origin)) {
                throw new Error("El servidor devolvió un resultado inesperado.");
            }
            window.location.reload();
        } catch (error) {
            status.textContent = `No se pudo completar el cálculo: ${error.message}`;
            button.disabled = false;
            button.textContent = buttonLabel;
            inFlight = false;
        }
    };

    form.addEventListener("submit", (event) => {
        event.preventDefault();
        recalculate();
    });

    if (form.dataset.autoRecalculate === "true") recalculate();
})();
