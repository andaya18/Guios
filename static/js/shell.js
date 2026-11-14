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

    // One place applies the theme so the top bar toggle and the profile choice stay in sync.
    const applyTheme = (theme) => {
        document.documentElement.dataset.theme = theme;
        store.set("guios-theme", theme);
        document.querySelectorAll("[data-theme-option]").forEach((option) => {
            const active = option.dataset.themeOption === theme;
            option.classList.toggle("is-active", active);
            option.setAttribute("aria-checked", String(active));
        });
    };
    applyTheme(document.documentElement.dataset.theme === "dark" ? "dark" : "light");
    document.querySelector("[data-theme-toggle]")?.addEventListener("click", () => {
        applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
    });
    document.querySelectorAll("[data-theme-option]").forEach((option) => {
        option.addEventListener("click", () => applyTheme(option.dataset.themeOption));
    });

    const search = document.querySelector("[data-search]");
    document.addEventListener("keydown", (event) => {
        if (search && (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
            event.preventDefault();
            search.focus();
        }
    });
})();
