// Shell behaviour shared by every authenticated page: sidebar collapse, dark mode and Ctrl+K search.
(() => {
    const app = document.querySelector("[data-app]");
    const store = {
        get: (key) => { try { return localStorage.getItem(key); } catch { return null; } },
        set: (key, value) => { try { localStorage.setItem(key, value); } catch { /* storage disabled */ } },
    };

    if (app && store.get("guios-sidebar") === "collapsed") app.classList.add("is-collapsed");
    document.querySelector("[data-sidebar-toggle]")?.addEventListener("click", () => {
        const collapsed = app.classList.toggle("is-collapsed");
        store.set("guios-sidebar", collapsed ? "collapsed" : "expanded");
    });

    document.querySelector("[data-theme-toggle]")?.addEventListener("click", () => {
        const root = document.documentElement;
        root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
        store.set("guios-theme", root.dataset.theme);
    });

    const search = document.querySelector("[data-search]");
    document.addEventListener("keydown", (event) => {
        if (search && (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
            event.preventDefault();
            search.focus();
        }
    });
})();
