import { useStore, type ThemeMode } from "../store";
import { resolveTheme } from "../lib/theme";

const THEMES: ThemeMode[] = ["system", "light", "dark"];

export function ThemeToggle() {
  const settings = useStore((s) => s.settings);
  const applySettings = useStore((s) => s.applySettings);
  const theme = (settings.theme as ThemeMode) ?? "system";
  const index = Math.max(0, THEMES.indexOf(theme));

  function setTheme(next: ThemeMode) {
    applySettings({ theme: next });
    document.documentElement.setAttribute("data-theme", resolveTheme(next));
  }

  return (
    <div className="theme-toggle" style={{ "--theme-index": index } as React.CSSProperties}>
      <div className="theme-toggle__track" role="group" aria-label="Theme">
        <span className="theme-toggle__indicator" />
        <button
          className={`theme-toggle__button ${theme === "system" ? "active" : ""}`}
          onClick={() => setTheme("system")}
          aria-pressed={theme === "system"}
          aria-label="System theme"
          title="System"
        >
          <svg className="theme-icon" viewBox="0 0 24 24" aria-hidden="true">
            <rect width="20" height="14" x="2" y="3" rx="2" />
            <line x1="8" x2="16" y1="21" y2="21" />
            <line x1="12" x2="12" y1="17" y2="21" />
          </svg>
        </button>
        <button
          className={`theme-toggle__button ${theme === "light" ? "active" : ""}`}
          onClick={() => setTheme("light")}
          aria-pressed={theme === "light"}
          aria-label="Light theme"
          title="Light"
        >
          <svg className="theme-icon" viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="12" cy="12" r="4" />
            <path d="M12 2v2M12 20v2m-7.07-14.93 1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2m-4.34-5.66 1.41-1.41M6.34 17.66l-1.41 1.41" />
          </svg>
        </button>
        <button
          className={`theme-toggle__button ${theme === "dark" ? "active" : ""}`}
          onClick={() => setTheme("dark")}
          aria-pressed={theme === "dark"}
          aria-label="Dark theme"
          title="Dark"
        >
          <svg className="theme-icon" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M20.985 12.486a9 9 0 1 1-9.473-9.472c.405-.022.617.46.402.803a6 6 0 0 0 8.268 8.268c.344-.215.825-.004.803.401" />
          </svg>
        </button>
      </div>
    </div>
  );
}
