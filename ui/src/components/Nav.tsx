import { useStore, type Tab } from "../store";
import { MessageCircle, Bot, ScrollText } from "lucide-react";

type NavItem = { tab: Tab; label: string; icon: React.ReactNode };

const NAV_ITEMS: NavItem[] = [
  { tab: "chat", label: "Chat", icon: <MessageCircle size={16} /> },
  { tab: "agents", label: "Agents", icon: <Bot size={16} /> },
  { tab: "logs", label: "Logs", icon: <ScrollText size={16} /> },
];

export function Nav() {
  const tab = useStore((s) => s.tab);
  const setTab = useStore((s) => s.setTab);
  const settings = useStore((s) => s.settings);
  const applySettings = useStore((s) => s.applySettings);
  const collapsed = settings.navCollapsed ?? false;
  const groupsCollapsed = settings.navGroupsCollapsed ?? {};

  return (
    <aside className={`nav ${collapsed ? "nav--collapsed" : ""}`}>
      <div className="nav-group">
        <button
          className="nav-label"
          onClick={() =>
            applySettings({ navGroupsCollapsed: { ...groupsCollapsed, Main: !groupsCollapsed["Main"] } })
          }
          aria-expanded={!groupsCollapsed["Main"]}
        >
          <span className="nav-label__text">Main</span>
          <span className="nav-label__chevron">{groupsCollapsed["Main"] ? "+" : "−"}</span>
        </button>
        <div className="nav-group__items">
          {NAV_ITEMS.map(({ tab: t, label, icon }) => (
            <button
              key={t}
              className={`nav-item ${tab === t ? "active" : ""}`}
              onClick={() => setTab(t)}
            >
              <span className="nav-item__icon" aria-hidden="true">{icon}</span>
              <span className="nav-item__text">{label}</span>
            </button>
          ))}
        </div>
      </div>
    </aside>
  );
}
