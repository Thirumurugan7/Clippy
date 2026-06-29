// Left tool rail (Veed/Descript-style): grouped, labeled tools so every feature
// is discoverable at a glance. The active tool opens its panel beside the rail;
// "soon" tools are visible but disabled, so the roadmap reads as one surface.
export function Sidebar({ groups, active, onSelect, collapsed, onToggle, children }) {
  return (
    <aside className={"sidebar" + (collapsed ? " collapsed" : "")}>
      <div className="side-strip">
        {groups.map((g) => (
          <div className="side-group" key={g.label}>
            <span className="side-group-label">{g.label}</span>
            {g.tools.map((t) => (
              <button
                key={t.id}
                className={
                  "side-icon" +
                  (active === t.id && !collapsed ? " on" : "") +
                  (t.soon ? " soon" : "")
                }
                title={t.soon ? `${t.label} — coming soon` : t.label}
                disabled={t.soon}
                onClick={() => {
                  if (t.soon) return;
                  if (collapsed) onToggle();
                  onSelect(t.id);
                }}
              >
                <span className="side-glyph">{t.icon}</span>
                <span className="side-label">{t.label}</span>
                {t.soon && <span className="side-soon">soon</span>}
              </button>
            ))}
          </div>
        ))}
        <button className="side-collapse" onClick={onToggle} title={collapsed ? "Expand panel" : "Collapse panel"}>
          {collapsed ? "›" : "‹"}
        </button>
      </div>
      {!collapsed && <div className="side-panel">{children}</div>}
    </aside>
  );
}
