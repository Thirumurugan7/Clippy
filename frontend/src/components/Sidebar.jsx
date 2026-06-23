// Collapsible Veed/Descript-style sidebar: a vertical icon strip selects the
// active panel; collapsing hides the panel area.
export function Sidebar({ tabs, active, onSelect, collapsed, onToggle, children }) {
  return (
    <aside className={"sidebar" + (collapsed ? " collapsed" : "")}>
      <div className="side-strip">
        {tabs.map((t) => (
          <button
            key={t.id}
            className={"side-icon" + (active === t.id && !collapsed ? " on" : "")}
            title={t.label}
            onClick={() => {
              if (collapsed) onToggle();
              onSelect(t.id);
            }}
          >
            <span className="side-glyph">{t.icon}</span>
            <span className="side-label">{t.label}</span>
          </button>
        ))}
        <button className="side-collapse" onClick={onToggle} title={collapsed ? "Expand" : "Collapse"}>
          {collapsed ? "‹" : "›"}
        </button>
      </div>
      {!collapsed && <div className="side-panel">{children}</div>}
    </aside>
  );
}
