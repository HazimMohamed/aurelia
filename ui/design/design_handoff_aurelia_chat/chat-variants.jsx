/* global React */
const { useState, useMemo } = React;

/* ============================================================
   Shared bits — Aurelia shell chrome reused by both variants
   ============================================================ */

const Brand = () => (
  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
    <div style={{
      width: 32, height: 32, borderRadius: 10,
      background: "radial-gradient(circle at 35% 30%, #e08a5f, #b95c31 70%)",
      boxShadow: "inset 0 0 0 1px rgba(255,255,255,.18), 0 1px 2px rgba(60,40,20,.18)",
      display: "grid", placeItems: "center", color: "#fff8f2",
      fontFamily: "var(--mono)", fontWeight: 700, fontSize: 13, letterSpacing: "-.04em",
    }}>æ</div>
    <div style={{ lineHeight: 1.05 }}>
      <div style={{ fontWeight: 700, fontSize: 13, letterSpacing: ".18em", color: "var(--text-strong)" }}>AURELIA</div>
      <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted)", letterSpacing: ".06em", marginTop: 1 }}>agent gateway</div>
    </div>
  </div>
);

const HealthPill = ({ tone = "ok", children }) => (
  <div style={{
    display: "inline-flex", alignItems: "center", gap: 7,
    padding: "4px 10px 4px 9px",
    borderRadius: 999,
    background: tone === "ok" ? "rgba(47,138,86,.10)" : "var(--bg-elevated)",
    border: `1px solid ${tone === "ok" ? "rgba(47,138,86,.28)" : "var(--border)"}`,
    fontSize: 11, fontWeight: 600, color: tone === "ok" ? "#22683f" : "var(--muted)",
    letterSpacing: "-.005em",
  }}>
    <span style={{
      width: 6, height: 6, borderRadius: 999,
      background: tone === "ok" ? "#3f9f66" : "var(--muted-soft)",
      boxShadow: tone === "ok" ? "0 0 0 3px rgba(63,159,102,.18)" : "none",
    }} />
    {children}
  </div>
);

const Sidebar = ({ active = "Chat", dense = false, collapsed = false }) => {
  const groups = [
    { label: "Chat", items: [["Chat", "💬"]] },
    { label: "Agent", items: [["Agents", "□"]] },
    { label: "Observe", items: [["Logs", "≡"]] },
  ];
  if (collapsed) {
    return (
      <nav style={{
        display: "flex", flexDirection: "column", alignItems: "center",
        padding: "12px 6px", gap: 6,
        borderRight: "1px solid var(--border)",
        background: "linear-gradient(180deg, var(--panel) 0%, var(--panel-strong) 100%)",
      }}>
        {groups.flatMap(g => g.items).map(([name, glyph]) => {
          const isActive = name === active;
          return (
            <button key={name} title={name} style={{
              width: 32, height: 32, borderRadius: 8,
              border: "1px solid " + (isActive ? "var(--accent-soft)" : "transparent"),
              background: isActive ? "var(--accent-subtle)" : "transparent",
              color: isActive ? "var(--accent)" : "var(--muted)",
              display: "grid", placeItems: "center", cursor: "pointer",
              fontFamily: "var(--mono)", fontSize: 13,
            }}>{glyph}</button>
          );
        })}
      </nav>
    );
  }
  const pad = dense ? "7px 10px" : "10px 12px";
  return (
    <nav style={{
      display: "flex", flexDirection: "column",
      padding: dense ? "12px 10px" : "14px 12px",
      gap: dense ? 8 : 12, fontSize: 12.5,
      borderRight: "1px solid var(--border)",
      background: "linear-gradient(180deg, var(--panel) 0%, var(--panel-strong) 100%)",
      minWidth: 0,
    }}>
      {groups.map((g) => (
        <div key={g.label} style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <div style={{
            fontFamily: "var(--mono)", fontSize: 9.5, letterSpacing: ".22em",
            color: "var(--muted-soft)", textTransform: "uppercase",
            padding: "4px 10px 6px",
          }}>{g.label}</div>
          {g.items.map(([name, glyph]) => {
            const isActive = name === active;
            return (
              <button key={name} style={{
                display: "flex", alignItems: "center", gap: 10,
                padding: pad, borderRadius: 8, border: "1px solid transparent",
                background: isActive ? "var(--accent-subtle)" : "transparent",
                color: isActive ? "var(--accent)" : "var(--text)",
                fontWeight: isActive ? 600 : 500,
                cursor: "pointer", textAlign: "left",
                fontFamily: "inherit", fontSize: 12.5, letterSpacing: "-.01em",
              }}>
                <span style={{
                  width: 16, display: "inline-grid", placeItems: "center",
                  fontFamily: "var(--mono)", fontSize: 11, opacity: .9,
                }}>{glyph}</span>
                {name}
              </button>
            );
          })}
        </div>
      ))}
    </nav>
  );
};

const Topbar = ({ dense = false, onToggleNav, navCollapsed = false }) => (
  <header style={{
    display: "flex", alignItems: "center", justifyContent: "space-between",
    padding: dense ? "10px 16px" : "14px 20px",
    background: "rgba(247,242,232,.92)",
    backdropFilter: "saturate(140%) blur(8px)",
    borderBottom: "1px solid var(--border)",
  }}>
    <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
      <button onClick={onToggleNav} aria-label="Toggle nav" title={navCollapsed ? "Expand sidebars" : "Collapse sidebars"} style={{
        width: 28, height: 28, border: "1px solid var(--border)", borderRadius: 7,
        background: "var(--bg-elevated)", display: "grid", placeItems: "center", cursor: "pointer",
      }}>
        <span style={{ fontFamily: "var(--mono)", fontSize: 13, color: "var(--muted)" }}>{navCollapsed ? "›≡" : "≡"}</span>
      </button>
      <Brand />
    </div>
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <HealthPill>Backend&nbsp;<span style={{ fontFamily: "var(--mono)", fontSize: 10.5 }}>OK · 38ms</span></HealthPill>
      <div style={{
        display: "inline-flex", padding: 3, gap: 2,
        border: "1px solid var(--border)", borderRadius: 999, background: "var(--bg-elevated)",
        fontSize: 11,
      }}>
        {["◐","☀","☾"].map((g, i) => (
          <button key={i} style={{
            width: 24, height: 22, border: "none", borderRadius: 999, cursor: "pointer",
            background: i === 1 ? "var(--accent)" : "transparent",
            color: i === 1 ? "#fff" : "var(--muted)", fontSize: 12,
          }}>{g}</button>
        ))}
      </div>
    </div>
  </header>
);

/* ============================================================
   Shared content used in both transcripts (different layouts)
   ============================================================ */

const transcript = [
  {
    role: "user", time: "10:42",
    text: "test-agent fallback keeps tripping rate limits this morning. what's going on?"
  },
  {
    role: "assistant", time: "10:42", thinking: "Checking recent warn-level logs scoped to test-agent for the last hour, then the routing config for fallbacks.",
    tools: [
      { name: "logs.search", status: "ok", dur: "120ms",
        args: { agent: "test-agent", level: "warn", since: "1h" },
        out: "12 matches · rate_limit_exceeded × 9 · provider=openrouter · model=moonshotai/kimi-k2.5" },
      { name: "config.read", status: "ok", dur: "8ms",
        args: { path: "agents.test-agent.routing" },
        out: '{ primary: "openrouter/…", fallbacks: ["openrouter/kimi-k2.5"] }' },
    ],
    text: "Both primary and fallback resolve to **openrouter/kimi-k2.5** — so when the primary 429s, the retry hits the same model and 429s again. Two cheap fixes:\n\n1. Set a real fallback (e.g. `anthropic/claude-sonnet-4.5`)\n2. Raise the retry backoff from `200ms` to `1.5s`\n\nWant me to apply (1) now?"
  },
  {
    role: "user", time: "10:44",
    text: "yes, switch primary to anthropic/claude-sonnet-4.5 and keep kimi as the fallback."
  },
  {
    role: "assistant", time: "10:44",
    tools: [
      { name: "config.update", status: "ok", dur: "42ms",
        args: { "agents.test-agent.routing.primary": "anthropic/claude-sonnet-4.5" },
        out: "patched · 1 file changed · awaiting reload" },
      { name: "agent.reload", status: "running", dur: "—", args: { agent: "test-agent" } },
    ],
    text: "Patched. Reloading test-agent — should be live in ~2s."
  },
];

/* ============================================================
   VARIANT A — Aurelia · Compact
   Density-first refinement. Tighter rhythm, sessions rail,
   compact tool strips, inline meta. Same visual DNA.
   ============================================================ */

const SessionsRail = () => {
  const sessions = [
    ["test-agent · rate-limit triage", "10:42", true],
    ["main · README rewrite", "yesterday"],
    ["test-agent · cron sweep", "yesterday"],
    ["main · OAuth scopes", "Apr 18"],
    ["main · vector store init", "Apr 16"],
    ["test-agent · skill rebuild", "Apr 14"],
  ];
  return (
    <aside style={{
      width: 220, minWidth: 220,
      borderRight: "1px solid var(--border)",
      background: "var(--bg-accent)",
      display: "flex", flexDirection: "column",
      fontSize: 12,
    }}>
      <div style={{ padding: "10px 12px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ fontWeight: 600, letterSpacing: "-.01em" }}>Sessions</div>
        <button style={{
          fontFamily: "var(--mono)", fontSize: 11, padding: "2px 8px",
          border: "1px solid var(--border)", borderRadius: 6,
          background: "var(--bg-elevated)", color: "var(--muted)", cursor: "pointer",
        }}>＋ new</button>
      </div>
      <div style={{ padding: "8px 10px 6px", display: "flex", flexDirection: "column", gap: 2, overflowY: "auto" }}>
        {sessions.map(([t, when, active], i) => (
          <button key={i} style={{
            display: "grid", gridTemplateColumns: "1fr auto", gap: 6,
            padding: "7px 9px", borderRadius: 7, border: "1px solid transparent",
            background: active ? "var(--bg-elevated)" : "transparent",
            borderColor: active ? "var(--border)" : "transparent",
            cursor: "pointer", textAlign: "left",
            fontFamily: "inherit", color: "var(--text)",
          }}>
            <span style={{
              whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
              fontWeight: active ? 600 : 500, fontSize: 12,
            }}>{t}</span>
            <span style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted-soft)" }}>{when}</span>
          </button>
        ))}
      </div>
      <div style={{ marginTop: "auto", padding: "8px 10px", borderTop: "1px solid var(--border)", color: "var(--muted)", fontSize: 11, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span>48 sessions · 2.3k msgs</span>
        <span style={{ fontFamily: "var(--mono)" }}>⌘K</span>
      </div>
    </aside>
  );
};

const Avatar = ({ who }) => {
  const isUser = who === "user";
  return (
    <div style={{
      width: 22, height: 22, borderRadius: 7,
      flexShrink: 0,
      background: isUser ? "var(--bg-elevated)" : "radial-gradient(circle at 30% 30%, #e08a5f, #b95c31 75%)",
      border: isUser ? "1px solid var(--border)" : "none",
      color: isUser ? "var(--muted)" : "#fff8f2",
      display: "grid", placeItems: "center",
      fontFamily: "var(--mono)", fontSize: 10.5, fontWeight: 700, letterSpacing: "-.04em",
    }}>{isUser ? "U" : "æ"}</div>
  );
};

const ToolStrip = ({ tool }) => {
  const [open, setOpen] = useState(false);
  const dot = tool.status === "ok" ? "#3f9f66" : tool.status === "running" ? "var(--accent)" : "var(--danger)";
  return (
    <div style={{
      border: "1px solid var(--border)", borderRadius: 8,
      background: "var(--bg-elevated)", overflow: "hidden",
      fontFamily: "var(--mono)", fontSize: 11.5,
    }}>
      <button onClick={() => setOpen(o => !o)} style={{
        display: "grid", gridTemplateColumns: "auto 1fr auto auto auto", gap: 10,
        width: "100%", alignItems: "center",
        padding: "6px 10px", border: "none", background: "transparent", cursor: "pointer",
        textAlign: "left", fontFamily: "inherit", fontSize: "inherit",
      }}>
        <span style={{
          width: 7, height: 7, borderRadius: 999, background: dot,
          animation: tool.status === "running" ? "pulse 1.2s ease-in-out infinite" : "none",
        }} />
        <span style={{ color: "var(--text-strong)", fontWeight: 600 }}>
          {tool.name}
          <span style={{ color: "var(--muted-soft)", fontWeight: 400 }}>
            ({Object.entries(tool.args).slice(0, 1).map(([k,v]) => `${k}: ${typeof v === "string" ? `"${v}"` : JSON.stringify(v)}`)}{Object.keys(tool.args).length > 1 ? ", …" : ""})
          </span>
        </span>
        <span style={{ color: "var(--muted)", fontSize: 10.5 }}>{tool.dur}</span>
        <span style={{ color: "var(--muted-soft)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: ".1em" }}>{tool.status}</span>
        <span style={{ color: "var(--muted-soft)", fontSize: 10 }}>{open ? "▴" : "▾"}</span>
      </button>
      {open && (
        <div style={{ borderTop: "1px solid var(--border)", padding: "8px 10px", background: "var(--bg-accent)", color: "var(--text)", whiteSpace: "pre-wrap" }}>
          {tool.out}
        </div>
      )}
    </div>
  );
};

const TurnA = ({ turn }) => {
  const isUser = turn.role === "user";
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "22px 1fr",
      gap: 10, padding: "8px 0",
    }}>
      <Avatar who={turn.role} />
      <div style={{ minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 3 }}>
          <span style={{ fontWeight: 600, fontSize: 12.5, color: "var(--text-strong)" }}>
            {isUser ? "You" : "Aurelia"}
          </span>
          {!isUser && <span style={{
            fontFamily: "var(--mono)", fontSize: 9.5, color: "var(--muted-soft)",
            padding: "1px 6px", border: "1px solid var(--border)", borderRadius: 999,
            letterSpacing: ".04em",
          }}>claude-sonnet-4.5</span>}
          <span style={{ fontFamily: "var(--mono)", fontSize: 10.5, color: "var(--muted-soft)", marginLeft: "auto" }}>{turn.time}</span>
        </div>
        {turn.thinking && (
          <div style={{
            fontSize: 11.5, color: "var(--muted)", fontStyle: "italic",
            borderLeft: "2px solid var(--border-strong)", paddingLeft: 9,
            margin: "0 0 6px",
          }}>{turn.thinking}</div>
        )}
        {turn.tools && (
          <div style={{ display: "flex", flexDirection: "column", gap: 5, margin: "0 0 7px" }}>
            {turn.tools.map((t, i) => <ToolStrip key={i} tool={t} />)}
          </div>
        )}
        {turn.text && (
          <div style={{
            fontSize: 13.5, lineHeight: 1.55, color: "var(--text)",
            textWrap: "pretty",
          }} dangerouslySetInnerHTML={{ __html: renderInline(turn.text) }} />
        )}
      </div>
    </div>
  );
};

function renderInline(t) {
  // very small markdown subset: **bold**, `code`, newlines, 1./2. items
  let s = t.replace(/`([^`]+)`/g, '<code style="font-family:var(--mono);font-size:.9em;background:var(--bg-elevated);border:1px solid var(--border);padding:1px 5px;border-radius:5px">$1</code>');
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong style="font-weight:600;color:var(--text-strong)">$1</strong>');
  // simple numbered list
  s = s.replace(/^(\d+)\.\s+(.+)$/gm, '<div style="display:grid;grid-template-columns:18px 1fr;gap:4px;margin:2px 0"><span style="color:var(--accent);font-family:var(--mono);font-size:11.5px">$1.</span><span>$2</span></div>');
  s = s.replace(/\n/g, "<br/>");
  return s;
}

const ComposerA = () => (
  <div style={{
    margin: "10px 16px 14px", padding: 10,
    background: "var(--bg-elevated)", border: "1px solid var(--border)",
    borderRadius: 12, boxShadow: "0 1px 0 rgba(255,255,255,.6) inset, 0 6px 18px rgba(60,40,20,.06)",
  }}>
    <div style={{
      display: "grid", gridTemplateColumns: "1fr auto", gap: 8, alignItems: "end",
    }}>
      <div style={{
        minHeight: 38, padding: "8px 10px",
        fontSize: 13.5, color: "var(--muted)",
        background: "transparent",
      }}>Reply to Aurelia… <span style={{ fontFamily: "var(--mono)", color: "var(--muted-soft)", fontSize: 11 }}>↩ send · ⇧↩ newline · @ mention · / commands</span></div>
      <div style={{ display: "flex", gap: 6 }}>
        <button style={chipBtn}>@<span style={{ color: "var(--muted-soft)" }}>agent</span></button>
        <button style={chipBtn}>/<span style={{ color: "var(--muted-soft)" }}>skill</span></button>
        <button style={chipBtn}>📎</button>
        <button style={sendBtn}>Send <span style={{ fontFamily: "var(--mono)", fontSize: 11, opacity: .7, marginLeft: 4 }}>↵</span></button>
      </div>
    </div>
    <div style={{
      display: "flex", gap: 4, padding: "6px 2px 0", borderTop: "1px dashed var(--border)", marginTop: 8, flexWrap: "wrap",
    }}>
      {["Apply patch","Show diff","Rollback","Run health check","Open logs filter"].map((s, i) => (
        <button key={i} style={{
          fontSize: 11, padding: "3px 8px", border: "1px solid var(--border)", borderRadius: 999,
          background: "transparent", color: "var(--muted)", cursor: "pointer",
          fontFamily: "inherit",
        }}>{s}</button>
      ))}
    </div>
  </div>
);

const chipBtn = {
  padding: "6px 9px", border: "1px solid var(--border)", borderRadius: 8,
  background: "var(--bg-accent)", color: "var(--text)", cursor: "pointer",
  fontSize: 12, fontFamily: "inherit",
};
const sendBtn = {
  padding: "6px 12px", border: "none", borderRadius: 8,
  background: "var(--accent)", color: "#fff8f2", cursor: "pointer",
  fontSize: 12, fontWeight: 600, fontFamily: "inherit",
  boxShadow: "0 1px 0 rgba(255,255,255,.18) inset, 0 4px 10px rgba(201,103,58,.25)",
};

const PageHeader = ({ title, sub, right }) => (
  <div style={{
    display: "flex", alignItems: "flex-end", justifyContent: "space-between",
    padding: "12px 16px 8px", borderBottom: "1px solid var(--border)",
    background: "var(--bg-accent)",
  }}>
    <div>
      <div style={{ fontSize: 18, fontWeight: 600, letterSpacing: "-.02em", color: "var(--text-strong)" }}>{title}</div>
      <div style={{ fontSize: 11.5, color: "var(--muted)", marginTop: 1 }}>{sub}</div>
    </div>
    {right}
  </div>
);

const AgentSelector = () => (
  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
    <div style={{
      display: "flex", alignItems: "center", gap: 7, padding: "5px 9px 5px 6px",
      border: "1px solid var(--border)", borderRadius: 8, background: "var(--bg-elevated)",
      fontSize: 12,
    }}>
      <span style={{
        width: 18, height: 18, borderRadius: 5,
        background: "radial-gradient(circle at 30% 30%, #e08a5f, #b95c31 70%)",
        color: "#fff8f2", display: "grid", placeItems: "center",
        fontFamily: "var(--mono)", fontSize: 10, fontWeight: 700,
      }}>T</span>
      <span style={{ fontWeight: 600 }}>test-agent</span>
      <span style={{ color: "var(--muted-soft)", fontFamily: "var(--mono)", fontSize: 10 }}>›</span>
      <span style={{ color: "var(--muted)" }}>main</span>
      <span style={{ color: "var(--muted-soft)", marginLeft: 4 }}>▾</span>
    </div>
    <button title="New session" style={{
      width: 28, height: 28, border: "1px solid var(--border)", borderRadius: 8,
      background: "var(--bg-elevated)", cursor: "pointer", color: "var(--muted)",
      fontSize: 13,
    }}>＋</button>
    <button title="Memory" style={{
      width: 28, height: 28, border: "1px solid var(--border)", borderRadius: 8,
      background: "var(--bg-elevated)", cursor: "pointer", color: "var(--muted)",
      fontSize: 13,
    }}>◉</button>
  </div>
);

const ChatA = ({ showSessions = true }) => (
  <div style={{
    width: "100%", height: "100%",
    background: "var(--bg)", color: "var(--text)",
    fontFamily: "var(--body)",
    display: "grid", gridTemplateRows: "auto 1fr",
    overflow: "hidden",
  }}>
    <Topbar dense />
    <div style={{ display: "grid", gridTemplateColumns: "180px 1fr", minHeight: 0 }}>
      <Sidebar active="Chat" dense />
      <main style={{ display: "grid", gridTemplateColumns: showSessions ? "220px 1fr" : "1fr", minHeight: 0, background: "var(--panel)" }}>
        {showSessions && <SessionsRail />}
        <section style={{ display: "grid", gridTemplateRows: "auto 1fr auto", minHeight: 0 }}>
          <PageHeader
            title="Chat"
            sub="Direct gateway chat · 8 messages · grouped by turn"
            right={<AgentSelector />}
          />
          <div style={{ overflowY: "auto", padding: "6px 16px" }}>
            <div style={{
              display: "flex", alignItems: "center", gap: 10,
              padding: "8px 10px", margin: "8px 0",
              background: "var(--bg-elevated)", border: "1px dashed var(--border)",
              borderRadius: 8, fontSize: 11.5, color: "var(--muted)",
              fontFamily: "var(--mono)",
            }}>
              <span style={{ color: "var(--muted-soft)" }}>—</span>
              <span>Sun 22 Feb · 10:42 EST · session <span style={{ color: "var(--text)" }}>openclaw-tui</span></span>
              <span style={{ marginLeft: "auto", color: "var(--muted-soft)" }}>workspace /tmp/test-agent-workspace</span>
            </div>
            {transcript.map((t, i) => <TurnA key={i} turn={t} />)}
            <div style={{
              display: "flex", alignItems: "center", gap: 8,
              padding: "4px 0 14px", color: "var(--muted)", fontSize: 11.5,
            }}>
              <Avatar who="assistant" />
              <span>Aurelia is reloading agent</span>
              <span className="aurelia-dots" style={{ display: "inline-flex", gap: 3 }}>
                <span style={dot} /><span style={{...dot, animationDelay: ".15s"}} /><span style={{...dot, animationDelay: ".3s"}} />
              </span>
            </div>
          </div>
          <ComposerA />
        </section>
      </main>
    </div>
    <style>{`
      @keyframes pulse { 0%,100% { opacity: 1 } 50% { opacity: .35 } }
      @keyframes bob { 0%,100% { transform: translateY(0); opacity:.4 } 50% { transform: translateY(-2px); opacity:1 } }
    `}</style>
  </div>
);

const dot = { width: 4, height: 4, borderRadius: 999, background: "var(--accent)", animation: "bob 1s ease-in-out infinite" };

/* ============================================================
   VARIANT B — Aurelia · Ledger (bold direction)
   Editorial transcript with a gutter for time/role.
   Serif accents for assistant prose; mono compiler-style tools.
   ============================================================ */

const ContextStrip = () => (
  <div style={{
    display: "grid",
    gridTemplateColumns: "auto 1px auto 1px auto 1px 1fr auto",
    alignItems: "center", gap: 14,
    padding: "9px 18px",
    background: "var(--bg-accent)",
    borderBottom: "1px solid var(--border)",
    fontSize: 11.5, color: "var(--muted)",
    fontFamily: "var(--mono)", letterSpacing: "-.005em",
  }}>
    <div><span style={{ color: "var(--muted-soft)" }}>agent</span> <span style={{ color: "var(--text-strong)" }}>test-agent</span> <span style={{ color: "var(--muted-soft)" }}>›</span> <span style={{ color: "var(--text)" }}>main</span></div>
    <div style={{ width: 1, height: 14, background: "var(--border)" }} />
    <div><span style={{ color: "var(--muted-soft)" }}>model</span> <span style={{ color: "var(--text)" }}>anthropic/claude-sonnet-4.5</span></div>
    <div style={{ width: 1, height: 14, background: "var(--border)" }} />
    <div><span style={{ color: "var(--muted-soft)" }}>ws</span> <span style={{ color: "var(--text)" }}>/tmp/test-agent-workspace</span></div>
    <div style={{ width: 1, height: 14, background: "var(--border)" }} />
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <span style={{ color: "var(--muted-soft)" }}>p95</span>
      <Sparkline />
      <span style={{ color: "var(--text)" }}>412ms</span>
    </div>
    <div style={{ display: "flex", gap: 6 }}>
      <button style={ledgerChip}>memory</button>
      <button style={ledgerChip}>tools · 14</button>
      <button style={{...ledgerChip, color: "var(--accent)", borderColor: "var(--accent-soft)"}}>focus mode</button>
    </div>
  </div>
);
const ledgerChip = {
  fontFamily: "var(--mono)", fontSize: 11,
  padding: "3px 8px", border: "1px solid var(--border)", borderRadius: 999,
  background: "transparent", color: "var(--muted)", cursor: "pointer",
};

const Sparkline = () => {
  const pts = [4,7,5,9,6,11,8,7,12,9,6,8,5,7,6];
  const w = 80, h = 14, max = Math.max(...pts);
  const d = pts.map((p, i) => `${(i*(w/(pts.length-1))).toFixed(1)},${(h - (p/max)*h).toFixed(1)}`).join(" ");
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden>
      <polyline points={d} fill="none" stroke="var(--accent)" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
};

const LedgerTurn = ({ turn, idx, userIdx }) => {
  const isUser = turn.role === "user";
  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "118px 1fr",
      gap: 0,
      borderTop: idx === 0 ? "none" : "1px solid var(--border)",
      padding: "14px 0",
    }}>
      {/* gutter */}
      <div style={{
        paddingRight: 16, borderRight: "1px solid var(--border)",
        textAlign: "right",
        fontFamily: "var(--mono)", fontSize: 11, color: "var(--muted-soft)",
        display: "flex", flexDirection: "column", gap: 4, alignItems: "flex-end",
      }}>
        <div style={{
          fontSize: 9.5, letterSpacing: ".22em", textTransform: "uppercase",
          color: isUser ? "var(--muted)" : "var(--accent)",
          fontWeight: 600,
        }}>{isUser ? "You" : "Aurelia"}</div>
        <div>{turn.time}</div>
        {isUser && (
          <div style={{ fontSize: 9.5, opacity: .7 }}>§ {String(userIdx).padStart(2, "0")}</div>
        )}
        {!isUser && (
          <div style={{ marginTop: 4, fontSize: 9.5, opacity: .7, lineHeight: 1.3, maxWidth: 100, textAlign: "right" }}>
            sonnet-4.5<br/>2 tools · 170ms
          </div>
        )}
        {!isUser && (
          <div style={{
            marginTop: 4, fontSize: 10, fontWeight: 600,
            color: "var(--accent)", letterSpacing: "-.005em",
          }}>${(0.0008 + idx * 0.0011).toFixed(4)}</div>
        )}
      </div>
      {/* body */}
      <div style={{ padding: "0 24px 0 22px", minWidth: 0 }}>
        {turn.thinking && (
          <div style={{
            fontFamily: "var(--serif)", fontStyle: "italic", fontSize: 14,
            color: "var(--muted)", lineHeight: 1.5, marginBottom: 10,
            textWrap: "pretty",
          }}>
            <span style={{ color: "var(--accent)", fontFamily: "var(--mono)", fontStyle: "normal", fontSize: 10, marginRight: 8, letterSpacing: ".15em" }}>THINKING</span>
            {turn.thinking}
          </div>
        )}
        {turn.tools && (
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: turn.text ? 10 : 0 }}>
            {turn.tools.map((t, i) => <LedgerTool key={i} tool={t} />)}
          </div>
        )}
        {turn.text && (
          <div style={{
            fontFamily: isUser ? "var(--body)" : "var(--serif)",
            fontSize: isUser ? 14 : 16,
            lineHeight: isUser ? 1.55 : 1.55,
            color: "var(--text)",
            textWrap: "pretty",
            letterSpacing: isUser ? "-.005em" : "-.005em",
          }} dangerouslySetInnerHTML={{ __html: renderLedger(turn.text) }} />
        )}
      </div>
    </div>
  );
};

function renderLedger(t) {
  let s = t.replace(/`([^`]+)`/g, '<code style="font-family:var(--mono);font-size:.84em;background:var(--bg-elevated);border:1px solid var(--border);padding:1px 6px;border-radius:5px">$1</code>');
  s = s.replace(/\*\*([^*]+)\*\*/g, '<em style="font-style:normal;font-weight:500;background:linear-gradient(transparent 60%, var(--accent-soft) 60%);padding:0 2px">$1</em>');
  s = s.replace(/^(\d+)\.\s+(.+)$/gm, '<div style="display:grid;grid-template-columns:28px 1fr;gap:6px;margin:4px 0"><span style="color:var(--accent);font-family:var(--mono);font-size:12px;text-align:right">$1.</span><span>$2</span></div>');
  s = s.replace(/\n/g, "<br/>");
  return s;
}

const LedgerTool = ({ tool }) => {
  const [open, setOpen] = useState(true);
  const argsLine = "$ " + tool.name + "(" + Object.entries(tool.args)
    .map(([k,v]) => `${k}=${typeof v === "string" ? `"${v}"` : JSON.stringify(v)}`).join(", ") + ")";
  const statusColor = tool.status === "ok" ? "#3f9f66" : tool.status === "running" ? "var(--accent)" : "var(--danger)";
  return (
    <div style={{
      border: "1px solid var(--border)", borderRadius: 6,
      background: "var(--bg-elevated)", overflow: "hidden",
      fontFamily: "var(--mono)", fontSize: 11.5,
    }}>
      <div style={{
        display: "grid", gridTemplateColumns: "auto 1fr auto", alignItems: "center", gap: 10,
        padding: "5px 10px", background: "var(--bg-accent)",
        borderBottom: open ? "1px solid var(--border)" : "none",
      }}>
        <span style={{
          color: statusColor,
          fontSize: 10, letterSpacing: ".12em", fontWeight: 600,
        }}>● {tool.status.toUpperCase()}</span>
        <span style={{
          color: "var(--text-strong)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}>{argsLine}</span>
        <span style={{ color: "var(--muted-soft)", fontSize: 10.5 }}>{tool.dur} · <span onClick={() => setOpen(o => !o)} style={{ cursor: "pointer", color: "var(--muted)" }}>{open ? "hide" : "show"}</span></span>
      </div>
      {open && (
        <div style={{ padding: "6px 10px", color: "var(--text)", whiteSpace: "pre-wrap" }}>
          <span style={{ color: "var(--muted-soft)" }}>{">"}</span> {tool.out}
        </div>
      )}
    </div>
  );
};

const ComposerB = () => (
  <div style={{
    borderTop: "1px solid var(--border)",
    background: "linear-gradient(180deg, var(--bg-accent) 0%, var(--bg) 100%)",
    padding: "12px 0 14px",
  }}>
    <div style={{
      display: "grid", gridTemplateColumns: "118px 1fr",
      paddingRight: 24,
    }}>
      <div style={{
        paddingRight: 16, borderRight: "1px solid var(--border)",
        textAlign: "right",
        fontFamily: "var(--mono)", fontSize: 11, color: "var(--muted-soft)",
      }}>
        <div style={{ fontSize: 9.5, letterSpacing: ".22em", textTransform: "uppercase", color: "var(--muted)", fontWeight: 600 }}>You</div>
        <div style={{ marginTop: 4 }}>10:45</div>
        <div style={{ fontSize: 9.5, opacity: .7, marginTop: 2 }}>§ 05</div>
      </div>
      <div style={{ padding: "0 0 0 22px" }}>
        <div style={{
          border: "1px solid var(--border-strong)", borderRadius: 10,
          background: "var(--bg-elevated)",
          boxShadow: "0 1px 0 rgba(255,255,255,.6) inset, 0 8px 24px rgba(60,40,20,.08)",
        }}>
          <div style={{ padding: "11px 14px 9px", fontSize: 14, color: "var(--muted)", lineHeight: 1.4 }}>
            Continue the conversation<span style={{ color: "var(--muted-soft)" }}>… or </span>
            <span style={{ color: "var(--accent)" }}>/run</span><span style={{ color: "var(--muted-soft)" }}>, </span>
            <span style={{ color: "var(--accent)" }}>/diff</span><span style={{ color: "var(--muted-soft)" }}>, </span>
            <span style={{ color: "var(--accent)" }}>/memory</span>
            <span style={{ color: "var(--muted-soft)" }}>…</span>
          </div>
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "8px 10px", borderTop: "1px solid var(--border)",
            fontFamily: "var(--mono)", fontSize: 10.5, color: "var(--muted)",
          }}>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}><span style={{ width: 5, height: 5, borderRadius: 999, background: "#3f9f66" }} /> ready</span>
              <span>·</span>
              <span>ctx 12.4k / 200k</span>
              <span>·</span>
              <span>0 attachments</span>
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              <button style={ledgerChip}>⌘K</button>
              <button title="Attach file" style={ledgerChip}>📎 attach</button>
              <button style={{
                padding: "4px 14px", border: "none", borderRadius: 7,
                background: "var(--accent)", color: "#fff8f2", cursor: "pointer",
                fontSize: 11.5, fontWeight: 600, fontFamily: "inherit",
                letterSpacing: ".02em",
                boxShadow: "0 1px 0 rgba(255,255,255,.18) inset, 0 3px 10px rgba(201,103,58,.28)",
              }}>SEND ↵</button>
            </div>
          </div>
        </div>

      </div>
    </div>
  </div>
);

/* Hierarchical sessions: Agent → Incarnations (1:N). Used by ChatB. */
const AGENT_TREE = [
  {
    name: "main", label: "main", glyph: "✦",
    model: "openrouter/kimi-k2.5", isDefault: true,
    sessions: [
      { name: "README rewrite", when: "yesterday", msgs: 42 },
      { name: "OAuth scopes", when: "Apr 18", msgs: 18 },
      { name: "vector store init", when: "Apr 16", msgs: 9 },
    ],
  },
  {
    name: "test-agent", label: "test-agent", glyph: "T",
    model: "anthropic/claude-sonnet-4.5", isDefault: false, expanded: true,
    sessions: [
      { name: "rate-limit triage", when: "10:42", msgs: 8, active: true },
      { name: "cron sweep", when: "yesterday", msgs: 14 },
      { name: "skill rebuild", when: "Apr 14", msgs: 31 },
      { name: "perf regression", when: "Apr 12", msgs: 22 },
    ],
  },
];

const LedgerSessionsRail = ({ collapsed = false, onToggle }) => {
  const [open, setOpen] = useState({ "main": false, "test-agent": true });
  const [q, setQ] = useState("");
  if (collapsed) {
    return (
      <aside style={{
        width: 52, minWidth: 52,
        borderRight: "1px solid var(--border)",
        background: "linear-gradient(180deg, var(--bg-accent) 0%, var(--panel) 60%)",
        display: "flex", flexDirection: "column", alignItems: "center",
        padding: "12px 0", gap: 10,
      }}>
        <button onClick={onToggle} title="Expand index" style={{
          width: 28, height: 28, border: "1px solid var(--border)", borderRadius: 7,
          background: "var(--bg-elevated)", color: "var(--muted)", cursor: "pointer",
          display: "grid", placeItems: "center", fontFamily: "var(--mono)", fontSize: 12,
        }}>›</button>
        <div style={{ height: 1, width: 24, background: "var(--border)" }} />
        {AGENT_TREE.map((a) => (
          <button key={a.name} title={a.label} style={{
            width: 32, height: 32, borderRadius: 8, border: "none",
            background: a.isDefault
              ? "var(--bg-elevated)"
              : "radial-gradient(circle at 30% 30%, #e08a5f, #b95c31 70%)",
            color: a.isDefault ? "var(--muted)" : "#fff8f2",
            display: "grid", placeItems: "center", cursor: "pointer",
            fontFamily: "var(--mono)", fontSize: 12, fontWeight: 700,
            boxShadow: a.isDefault ? "inset 0 0 0 1px var(--border-strong)" : "none",
          }}>{a.glyph}</button>
        ))}
      </aside>
    );
  }
  return (
    <aside style={{
      width: 244, minWidth: 244,
      borderRight: "1px solid var(--border)",
      background: "linear-gradient(180deg, var(--bg-accent) 0%, var(--panel) 60%)",
      display: "flex", flexDirection: "column",
      fontSize: 12, minHeight: 0,
    }}>
      <div style={{ padding: "10px 12px 10px", borderBottom: "1px solid var(--border)" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
          <div style={{
            display: "flex", alignItems: "center", gap: 8,
            fontFamily: "var(--mono)", fontSize: 10, letterSpacing: ".22em",
            textTransform: "uppercase", color: "var(--muted-soft)", fontWeight: 600,
          }}>
            <button onClick={onToggle} title="Collapse index" style={{
              width: 20, height: 20, border: "1px solid var(--border)", borderRadius: 6,
              background: "var(--bg-elevated)", color: "var(--muted)", cursor: "pointer",
              display: "grid", placeItems: "center", fontFamily: "var(--mono)", fontSize: 11,
              letterSpacing: 0,
            }}>‹</button>
            Index
          </div>
          <button style={{
            fontFamily: "var(--mono)", fontSize: 10.5, padding: "2px 7px",
            border: "1px solid var(--border)", borderRadius: 6,
            background: "var(--bg-elevated)", color: "var(--muted)", cursor: "pointer",
            letterSpacing: ".06em",
          }}>＋ new</button>
        </div>
        <div style={{
          display: "flex", alignItems: "center", gap: 6,
          padding: "5px 8px", border: "1px solid var(--border)", borderRadius: 8,
          background: "var(--bg-elevated)",
        }}>
          <span style={{ color: "var(--muted-soft)", fontSize: 11 }}>⌕</span>
          <input
            value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="Find agent or incarnation…"
            style={{
              flex: 1, border: "none", background: "transparent", outline: "none",
              fontFamily: "inherit", fontSize: 12, color: "var(--text)", minWidth: 0,
            }}
          />
          <span style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted-soft)" }}>⌘K</span>
        </div>
      </div>
      <div style={{ overflowY: "auto", padding: "6px 6px 8px" }}>
        {AGENT_TREE.map((a) => {
          const isOpen = open[a.name];
          const total = a.sessions.length;
          const filt = q ? a.sessions.filter(s => (a.name + " " + s.name).toLowerCase().includes(q.toLowerCase())) : a.sessions;
          return (
            <div key={a.name} style={{ marginBottom: 4 }}>
              <button onClick={() => setOpen(o => ({ ...o, [a.name]: !o[a.name] }))} style={{
                display: "grid", gridTemplateColumns: "12px 20px 1fr auto", gap: 7,
                alignItems: "center", width: "100%",
                padding: "6px 8px", borderRadius: 7, border: "1px solid transparent",
                background: "transparent", cursor: "pointer", textAlign: "left",
                fontFamily: "inherit",
              }}>
                <span style={{
                  fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted-soft)",
                  transform: isOpen ? "rotate(90deg)" : "none", transition: "transform .15s",
                  display: "inline-block",
                }}>▸</span>
                <span style={{
                  width: 20, height: 20, borderRadius: 6,
                  background: a.isDefault
                    ? "var(--bg-elevated)"
                    : "radial-gradient(circle at 30% 30%, #e08a5f, #b95c31 70%)",
                  border: a.isDefault ? "1px solid var(--border-strong)" : "none",
                  color: a.isDefault ? "var(--muted)" : "#fff8f2",
                  display: "grid", placeItems: "center",
                  fontFamily: "var(--mono)", fontSize: 10.5, fontWeight: 700,
                }}>{a.glyph}</span>
                <span style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
                  <span style={{
                    fontWeight: 600, fontSize: 12.5, color: "var(--text-strong)",
                    letterSpacing: "-.005em",
                    whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                  }}>
                    {a.label}
                    {a.isDefault && <span style={{
                      marginLeft: 6, fontFamily: "var(--mono)", fontSize: 9,
                      letterSpacing: ".14em", color: "var(--muted-soft)",
                      padding: "1px 5px", border: "1px solid var(--border)", borderRadius: 999,
                    }}>DEFAULT</span>}
                  </span>
                  <span style={{ fontFamily: "var(--mono)", fontSize: 9.5, color: "var(--muted-soft)", letterSpacing: "-.005em" }}>
                    {a.model.replace(/^[^/]+\//, "")}
                  </span>
                </span>
                <span style={{
                  fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted-soft)",
                  padding: "1px 6px", border: "1px solid var(--border)", borderRadius: 999,
                }}>{total}</span>
              </button>
              {isOpen && (
                <div style={{ position: "relative", marginLeft: 20, paddingLeft: 0 }}>
                  <div style={{
                    position: "absolute", left: 9, top: 2, bottom: 4,
                    width: 1, background: "var(--border)",
                  }} />
                  {filt.map((s, i) => (
                    <button key={i} style={{
                      display: "grid",
                      gridTemplateColumns: "16px 1fr auto",
                      alignItems: "center", gap: 6, width: "100%",
                      padding: "5px 8px 5px 4px", margin: "1px 0",
                      border: "1px solid transparent", borderRadius: 6,
                      background: s.active ? "var(--bg-elevated)" : "transparent",
                      borderColor: s.active ? "var(--border)" : "transparent",
                      cursor: "pointer", textAlign: "left", fontFamily: "inherit",
                      color: "var(--text)",
                    }}>
                      <span style={{
                        fontFamily: "var(--mono)", fontSize: 10,
                        color: s.active ? "var(--accent)" : "var(--muted-soft)",
                        textAlign: "center",
                      }}>{s.active ? "●" : "─"}</span>
                      <span style={{
                        whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                        fontWeight: s.active ? 600 : 500, fontSize: 12,
                        color: s.active ? "var(--text-strong)" : "var(--text)",
                      }}>{s.name}</span>
                      <span style={{ fontFamily: "var(--mono)", fontSize: 9.5, color: "var(--muted-soft)" }}>{s.when}</span>
                    </button>
                  ))}
                  <button style={{
                    display: "block", padding: "3px 8px 6px 24px",
                    border: "none", background: "transparent", cursor: "pointer",
                    fontFamily: "var(--mono)", fontSize: 10.5, color: "var(--accent)",
                    letterSpacing: ".04em",
                  }}>＋ new incarnation</button>
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div style={{
        marginTop: "auto", padding: "8px 12px",
        borderTop: "1px solid var(--border)",
        fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted-soft)",
        letterSpacing: ".04em",
      }}>
        2 agents · 7 incarnations
      </div>
    </aside>
  );
};

const ChatB = ({ showContext = true, showSessions = true }) => {
  const [navCollapsed, setNavCollapsed] = useState(false);
  const [indexCollapsed, setIndexCollapsed] = useState(false);
  const toggleAll = () => {
    const next = !navCollapsed;
    setNavCollapsed(next);
    setIndexCollapsed(next);
  };
  const navCol = navCollapsed ? 52 : 180;
  const idxCol = !showSessions ? 0 : (indexCollapsed ? 52 : 244);
  const cols = showSessions ? `${navCol}px ${idxCol}px 1fr` : `${navCol}px 1fr`;
  return (
  <div style={{
    width: "100%", height: "100%",
    background: "var(--bg)", color: "var(--text)",
    fontFamily: "var(--body)",
    display: "grid", gridTemplateRows: "auto 1fr",
    overflow: "hidden",
  }}>
    <Topbar dense onToggleNav={toggleAll} navCollapsed={navCollapsed} />
    <div style={{ display: "grid", gridTemplateColumns: cols, minHeight: 0 }}>
      <Sidebar active="Chat" dense collapsed={navCollapsed} />
      {showSessions && <LedgerSessionsRail collapsed={indexCollapsed} onToggle={() => setIndexCollapsed(c => !c)} />}
      <main style={{ display: "grid", gridTemplateRows: "auto 1fr auto", minHeight: 0, background: "var(--panel)" }}>
        {/* editorial masthead with vital context folded in */}
        <div style={{
          display: "grid", gridTemplateColumns: "1fr auto", alignItems: "center",
          padding: "12px 22px", borderBottom: "1px solid var(--border)",
          background: "var(--bg-accent)",
          gap: 14,
        }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 5, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <span style={{
                width: 26, height: 26, borderRadius: 7, flexShrink: 0,
                background: "radial-gradient(circle at 30% 30%, #e08a5f, #b95c31 70%)",
                color: "#fff8f2", display: "grid", placeItems: "center",
                fontFamily: "var(--mono)", fontSize: 12, fontWeight: 700,
              }}>T</span>
              <div style={{
                fontFamily: "var(--serif)", fontSize: 26, fontWeight: 500,
                letterSpacing: "-.025em", color: "var(--text-strong)", lineHeight: 1,
              }}>test-agent</div>
              <span style={{
                fontFamily: "var(--serif)", fontStyle: "italic", fontSize: 20,
                color: "var(--muted-soft)", lineHeight: 1, fontWeight: 400,
              }}> / </span>
              <div style={{
                fontFamily: "var(--serif)", fontSize: 22, fontWeight: 500,
                letterSpacing: "-.02em", color: "var(--accent)", lineHeight: 1,
              }}>rate-limit triage</div>
              <span style={{
                fontFamily: "var(--mono)", fontSize: 9.5, letterSpacing: ".14em",
                color: "var(--muted-soft)", padding: "2px 7px",
                border: "1px solid var(--border)", borderRadius: 999,
              }}>INCARNATION · 8 MSG</span>
            </div>
            <div style={{
              display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap",
              fontFamily: "var(--mono)", fontSize: 10.5, color: "var(--muted)",
              letterSpacing: "-.005em",
            }}>
              <span><span style={{ color: "var(--muted-soft)" }}>id</span> sess_8af2…4c1d</span>
              <span style={{ color: "var(--muted-soft)" }}>·</span>
              <span><span style={{ color: "var(--muted-soft)" }}>model</span> <span style={{ color: "var(--text)" }}>anthropic/claude-sonnet-4.5</span></span>
              <span style={{ color: "var(--muted-soft)" }}>·</span>
              <span><span style={{ color: "var(--muted-soft)" }}>ws</span> <span style={{ color: "var(--text)" }}>/tmp/test-agent-workspace</span></span>
              <span style={{ color: "var(--muted-soft)" }}>·</span>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <span style={{ color: "var(--muted-soft)" }}>p95</span>
                <Sparkline />
                <span style={{ color: "var(--text)" }}>412ms</span>
              </span>
            </div>
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            <button style={ledgerChip}>memory</button>
            <button style={ledgerChip}>fork</button>
            <button style={{...ledgerChip, color: "var(--accent)", borderColor: "var(--accent-soft)"}}>＋ new incarnation</button>
          </div>
        </div>
        <div style={{ overflowY: "auto", padding: "0 22px" }}>
          {(() => { let u = 0; return transcript.map((t, i) => { if (t.role === "user") u++; return <LedgerTurn key={i} turn={t} idx={i} userIdx={u} />; }); })()}
          <div style={{
            display: "grid", gridTemplateColumns: "118px 1fr",
            borderTop: "1px solid var(--border)", padding: "12px 0",
          }}>
            <div style={{
              paddingRight: 16, borderRight: "1px solid var(--border)",
              textAlign: "right", fontFamily: "var(--mono)", fontSize: 11,
              color: "var(--muted-soft)",
            }}>
              <div style={{ fontSize: 9.5, letterSpacing: ".22em", textTransform: "uppercase", color: "var(--accent)", fontWeight: 600 }}>Aurelia</div>
              <div style={{ marginTop: 4 }}>10:44</div>
            </div>
            <div style={{ padding: "0 0 0 22px", display: "flex", alignItems: "center", gap: 8, color: "var(--muted)", fontSize: 12.5 }}>
              <span style={{ fontFamily: "var(--serif)", fontStyle: "italic" }}>reloading test-agent</span>
              <span style={{ display: "inline-flex", gap: 3 }}>
                <span style={dot} /><span style={{...dot, animationDelay: ".15s"}} /><span style={{...dot, animationDelay: ".3s"}} />
              </span>
            </div>
          </div>
        </div>
        <ComposerB />
      </main>
    </div>
  </div>
  );
};

/* ============================================================
   VARIANT C — Aurelia · Unified
   One rail. Chat/Agents/Logs lift into the topbar as a
   segmented control. The agent → incarnation tree is the
   spine across all three views.
   ============================================================ */

const TopbarC = ({ onToggleNav, navCollapsed = false }) => {
  return (
    <header style={{
      display: "grid", gridTemplateColumns: "auto 1fr auto",
      alignItems: "center", gap: 14,
      padding: "8px 16px", borderBottom: "1px solid var(--border)",
      background: "var(--panel)",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <button onClick={onToggleNav} aria-label="Toggle nav" title={navCollapsed ? "Expand rail" : "Collapse rail"} style={{
          width: 28, height: 28, border: "1px solid var(--border)", borderRadius: 7,
          background: "var(--bg-elevated)", display: "grid", placeItems: "center", cursor: "pointer",
        }}>
          <span style={{ fontFamily: "var(--mono)", fontSize: 13, color: "var(--muted)" }}>{navCollapsed ? "›≡" : "≡"}</span>
        </button>
        <div style={{
          width: 22, height: 22, borderRadius: 6,
          background: "linear-gradient(135deg, var(--accent), #9e4e2a)",
          display: "grid", placeItems: "center",
          fontFamily: "var(--mono)", fontSize: 11, fontWeight: 700, color: "#fff8f2",
        }}>A</div>
        <div style={{ fontFamily: "var(--serif)", fontSize: 16, fontWeight: 500, letterSpacing: "-.01em" }}>Aurelia</div>
        <span style={{
          fontFamily: "var(--mono)", fontSize: 9.5, padding: "1px 6px",
          border: "1px solid var(--border)", borderRadius: 999,
          color: "var(--muted)", letterSpacing: ".08em",
        }}>local</span>
      </div>
      <div />
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{
          fontFamily: "var(--mono)", fontSize: 10.5, color: "var(--muted)",
          padding: "3px 8px", border: "1px solid var(--border)", borderRadius: 999,
        }}><span style={{ color: "#7a9d6a" }}>●</span> cluster ok</span>
        <div style={{
          width: 26, height: 26, borderRadius: "50%",
          background: "linear-gradient(135deg, #d49b6a, #9e4e2a)",
          color: "#fff8f2", display: "grid", placeItems: "center",
          fontFamily: "var(--mono)", fontSize: 10.5, fontWeight: 700,
        }}>OC</div>
      </div>
    </header>
  );
};

const Crumbs = ({ items }) => (
  <div style={{
    display: "flex", alignItems: "center", gap: 6,
    fontFamily: "var(--mono)", fontSize: 10.5, letterSpacing: ".14em",
    textTransform: "uppercase", fontWeight: 600,
    minHeight: 22,
  }}>
    {items.map((it, i) => (
      <React.Fragment key={i}>
        {i > 0 && <span style={{ color: "var(--muted-soft)", opacity: .5, fontWeight: 400 }}>/</span>}
        {it.current
          ? <span style={{ color: "var(--accent)" }}>{it.label}</span>
          : <button onClick={it.onClick} style={{
              border: "none", background: "transparent", padding: 0, cursor: "pointer",
              fontFamily: "inherit", fontSize: "inherit", letterSpacing: "inherit",
              textTransform: "inherit", fontWeight: "inherit",
              color: "var(--muted-soft)",
            }} onMouseOver={(e) => e.currentTarget.style.color = "var(--text)"}
              onMouseOut={(e) => e.currentTarget.style.color = "var(--muted-soft)"}>{it.label}</button>}
      </React.Fragment>
    ))}
  </div>
);

const UnifiedRail = ({ collapsed = false, onToggle, view = "Chat", onView }) => {
  const [open, setOpen] = useState({ "main": false, "test-agent": true });
  const [q, setQ] = useState("");
  const [mode, setMode] = useState("tree"); // "tree" | "menu"
  if (collapsed) {
    return (
      <aside style={{
        width: 56, minWidth: 56,
        borderRight: "1px solid var(--border)",
        background: "linear-gradient(180deg, var(--bg-accent) 0%, var(--panel) 60%)",
        display: "flex", flexDirection: "column", alignItems: "center",
        padding: "10px 0", gap: 8,
      }}>
        <button onClick={onToggle} title="Expand" style={{
          width: 30, height: 30, border: "1px solid var(--border)", borderRadius: 8,
          background: "var(--bg-elevated)", color: "var(--muted)", cursor: "pointer",
          display: "grid", placeItems: "center", fontFamily: "var(--mono)", fontSize: 12,
        }}>›</button>
        <div style={{ height: 1, width: 28, background: "var(--border)" }} />
        {AGENT_TREE.map((a) => (
          <button key={a.name} title={a.label} style={{
            width: 36, height: 36, borderRadius: 9, border: "none",
            background: a.isDefault
              ? "var(--bg-elevated)"
              : "radial-gradient(circle at 30% 30%, #e08a5f, #b95c31 70%)",
            color: a.isDefault ? "var(--muted)" : "#fff8f2",
            display: "grid", placeItems: "center", cursor: "pointer",
            fontFamily: "var(--mono)", fontSize: 13, fontWeight: 700,
            boxShadow: a.isDefault ? "inset 0 0 0 1px var(--border-strong)" : "none",
          }}>{a.glyph}</button>
        ))}
        <button title="New agent" style={{
          marginTop: 4,
          width: 32, height: 32, borderRadius: 8, border: "1px dashed var(--border-strong)",
          background: "transparent", color: "var(--muted-soft)", cursor: "pointer",
          fontFamily: "var(--mono)", fontSize: 16,
        }}>＋</button>
      </aside>
    );
  }
  // Context-aware caption — same spine, different right pane
  const caption = view === "Chat" ? "incarnations" : view === "Samsara" ? "runtime status" : "log streams";
  if (mode === "menu") {
    const items = [
      ["Chat", "💬", "transcript view"],
      ["Samsara", "◉", "runtime status"],
      ["Logs", "≡", "live tail"],
    ];
    return (
      <aside style={{
        width: 268, minWidth: 268,
        borderRight: "1px solid var(--border)",
        background: "linear-gradient(180deg, var(--bg-accent) 0%, var(--panel) 55%)",
        display: "flex", flexDirection: "column",
      }}>
        <div style={{ padding: "12px 14px 10px", borderBottom: "1px solid var(--border)" }}>
          <div style={{
            fontFamily: "var(--mono)", fontSize: 10, letterSpacing: ".22em",
            textTransform: "uppercase", color: "var(--muted-soft)", fontWeight: 600,
          }}>Aurelia</div>
        </div>
        <div style={{ padding: "10px 8px", display: "flex", flexDirection: "column", gap: 2 }}>
          {items.map(([name, glyph, hint]) => {
            const isActive = name === view;
            return (
              <button key={name} onClick={() => { onView && onView(name); setMode("tree"); }} style={{
                display: "grid", gridTemplateColumns: "28px 1fr auto", gap: 10, alignItems: "center",
                padding: "9px 10px", border: "none", borderRadius: 8, cursor: "pointer",
                textAlign: "left",
                background: isActive ? "var(--accent-subtle)" : "transparent",
                color: isActive ? "var(--text-strong)" : "var(--text)",
              }}>
                <span style={{
                  width: 26, height: 26, borderRadius: 7,
                  display: "grid", placeItems: "center",
                  background: isActive ? "var(--panel)" : "var(--bg-elevated)",
                  border: "1px solid " + (isActive ? "var(--accent-soft)" : "var(--border)"),
                  color: isActive ? "var(--accent)" : "var(--muted)",
                  fontFamily: "var(--mono)", fontSize: 13,
                }}>{glyph}</span>
                <span style={{ fontFamily: "var(--body)", fontSize: 13.5, fontWeight: isActive ? 600 : 500, letterSpacing: "-.005em" }}>{name}</span>
                <span style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted-soft)", letterSpacing: ".04em" }}>{hint}</span>
              </button>
            );
          })}
        </div>
        <div style={{
          marginTop: "auto", padding: "8px 14px",
          borderTop: "1px solid var(--border)",
          fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted-soft)",
          letterSpacing: ".04em",
        }}>
          2 agents · 7 incarnations
        </div>
      </aside>
    );
  }
  return (
    <aside style={{
      width: 268, minWidth: 268,
      borderRight: "1px solid var(--border)",
      background: "linear-gradient(180deg, var(--bg-accent) 0%, var(--panel) 55%)",
      display: "flex", flexDirection: "column",
      fontFamily: "var(--mono)", fontSize: 12,
      color: "var(--text)",
    }}>
      <div style={{ padding: "12px 14px 10px", borderBottom: "1px solid var(--border)" }}>
        <Crumbs items={[
          { label: "Aurelia", onClick: () => setMode("menu") },
          { label: view, current: true },
        ]} />
        {view === "Chat" && (
        <div style={{
          marginTop: 9,
          display: "flex", alignItems: "center", gap: 7,
          padding: "5px 9px", border: "1px solid var(--border)", borderRadius: 7,
          background: "var(--panel)", color: "var(--muted)",
        }}>
          <span style={{ opacity: .55 }}>⌕</span>
          <input
            value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="Find agent or incarnation…"
            style={{
              flex: 1, border: "none", outline: "none", background: "transparent",
              fontFamily: "inherit", fontSize: 11.5, color: "var(--text)",
            }}
          />
        </div>
        )}
      </div>
      <div style={{ padding: "8px 6px", overflowY: "auto", flex: 1 }}>
        {view !== "Chat" ? (
          <ComingSoonRail view={view} />
        ) : AGENT_TREE.map((a) => {
          const isOpen = open[a.name];
          const filt = q ? a.sessions.filter(s => (a.name + " " + s.name).toLowerCase().includes(q.toLowerCase())) : a.sessions;
          return (
            <div key={a.name} style={{ marginBottom: 4 }}>
              <button onClick={() => setOpen(o => ({...o, [a.name]: !o[a.name]}))} style={{
                display: "grid", gridTemplateColumns: "14px 22px 1fr auto",
                alignItems: "center", gap: 8,
                width: "100%", padding: "5px 8px",
                border: "none", borderRadius: 6, cursor: "pointer",
                background: "transparent", color: "var(--text)",
                fontFamily: "var(--mono)", fontSize: 12, fontWeight: 600,
                textAlign: "left", letterSpacing: "-.005em",
              }}>
                <span style={{ color: "var(--muted-soft)", fontSize: 10 }}>{isOpen ? "▾" : "▸"}</span>
                <span style={{
                  width: 20, height: 20, borderRadius: 5,
                  background: a.isDefault
                    ? "var(--bg-elevated)"
                    : "radial-gradient(circle at 30% 30%, #e08a5f, #b95c31 70%)",
                  color: a.isDefault ? "var(--muted)" : "#fff8f2",
                  display: "grid", placeItems: "center",
                  fontSize: 10.5, fontWeight: 700,
                  boxShadow: a.isDefault ? "inset 0 0 0 1px var(--border-strong)" : "none",
                }}>{a.glyph}</span>
                <span>{a.label}{a.isDefault && <span style={{
                  marginLeft: 6, fontFamily: "var(--mono)", fontSize: 8.5,
                  letterSpacing: ".14em", color: "var(--muted-soft)",
                  padding: "1px 5px", border: "1px solid var(--border)", borderRadius: 4,
                  fontWeight: 600,
                }}>DEFAULT</span>}</span>
                <span style={{ color: "var(--muted-soft)", fontSize: 10.5, fontWeight: 500 }}>{filt.length}</span>
              </button>
              {isOpen && (
                <div style={{ position: "relative", paddingLeft: 24 }}>
                  <div style={{
                    position: "absolute", left: 17, top: 2, bottom: 8,
                    width: 1, background: "var(--border)",
                  }} />
                  {filt.map((s, i) => (
                    <button key={i} style={{
                      display: "grid", gridTemplateColumns: "1fr auto auto", gap: 8,
                      alignItems: "center", width: "100%", padding: "4px 8px",
                      border: "none", borderRadius: 5, cursor: "pointer", textAlign: "left",
                      background: s.active ? "var(--accent-subtle)" : "transparent",
                      color: s.active ? "var(--text-strong)" : "var(--text)",
                      fontFamily: "var(--body)", fontSize: 12.5,
                      letterSpacing: "-.005em", marginBottom: 1,
                    }}>
                      <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {s.active && <span style={{ color: "var(--accent)", marginRight: 5 }}>●</span>}
                        {s.name}
                      </span>
                      <span style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted-soft)" }}>{s.msgs}</span>
                      <span style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted-soft)" }}>{s.when}</span>
                    </button>
                  ))}
                  <button style={{
                    display: "block", padding: "3px 8px 6px",
                    border: "none", background: "transparent", cursor: "pointer",
                    fontFamily: "var(--mono)", fontSize: 10.5, color: "var(--accent)",
                    letterSpacing: ".04em",
                  }}>＋ new incarnation</button>
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div style={{
        padding: "8px 14px",
        borderTop: "1px solid var(--border)",
        fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted-soft)",
        letterSpacing: ".04em",
        display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        <span>{view === "Chat" ? "2 agents · 7 incarnations" : view.toLowerCase() + " · not yet wired"}</span>
        <span style={{ fontFamily: "var(--mono)" }}>⌘K</span>
      </div>
    </aside>
  );
};

const ComingSoonRail = ({ view }) => {
  const map = {
    "Samsara": {
      stubs: [
        ["cluster", "0 nodes"],
        ["incarnations", "live count"],
        ["queues", "in/out"],
        ["restarts", "today"],
        ["spend", "per agent"],
      ],
    },
    "Logs": {
      stubs: [
        ["all streams", "tail"],
        ["errors", "filtered"],
        ["tool calls", "trace"],
        ["model i/o", "raw"],
        ["audit", "history"],
      ],
    },
  };
  const m = map[view] || { stubs: [] };
  return (
    <div style={{ padding: "6px 4px 12px", display: "flex", flexDirection: "column", gap: 1 }}>
      {m.stubs.map(([label, hint]) => (
        <div key={label} style={{
          display: "grid", gridTemplateColumns: "1fr auto", alignItems: "center",
          padding: "7px 10px", borderRadius: 6,
          fontFamily: "var(--body)", fontSize: 12.5,
          color: "var(--muted-soft)",
          opacity: .8,
        }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 8, fontWeight: 500 }}>
            <span style={{ width: 6, height: 6, borderRadius: 999, background: "var(--border-strong)" }} />
            {label}
          </span>
          <span style={{ fontFamily: "var(--mono)", fontSize: 10, letterSpacing: ".04em" }}>{hint}</span>
        </div>
      ))}
      <div style={{
        marginTop: 14, padding: "10px 12px",
        border: "1px dashed var(--border-strong)",
        borderRadius: 8,
        background: "var(--bg-elevated)",
        fontFamily: "var(--mono)", fontSize: 10, letterSpacing: ".18em",
        color: "var(--muted-soft)", textAlign: "center", fontWeight: 600,
      }}>COMING SOON</div>
    </div>
  );
};

const ComingSoon = ({ view }) => {
  const map = {
    "Samsara": { label: "SAMSARA", title: "Runtime status", blurb: "Live view of agent incarnations: per-tick spend, queue depth, failure modes, restart cadence. The wheel keeps turning.", glyph: "◉" },
    "Logs": { label: "LOGS", title: "Live tail", blurb: "Structured event stream across all agents and incarnations — filtered, searchable, replayable.", glyph: "≡" },
  };
  const m = map[view] || { label: view.toUpperCase(), title: view, blurb: "", glyph: "·" };
  return (
    <div style={{
      display: "grid", placeItems: "center", padding: "0 32px",
      background: "var(--panel)",
      gridColumn: "1 / -1",
    }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 18, alignItems: "center", textAlign: "center", maxWidth: 460 }}>
        <div style={{
          width: 88, height: 88, borderRadius: 18,
          display: "grid", placeItems: "center",
          background: "var(--bg-accent)",
          border: "1px solid var(--border)",
          color: "var(--accent)", fontFamily: "var(--mono)", fontSize: 38,
        }}>{m.glyph}</div>
        <div style={{
          fontFamily: "var(--mono)", fontSize: 10.5, letterSpacing: ".24em",
          color: "var(--muted-soft)", fontWeight: 600,
        }}>{m.label} · COMING SOON</div>
        <div style={{
          fontFamily: "var(--serif)", fontSize: 32, fontWeight: 500,
          letterSpacing: "-.025em", color: "var(--text-strong)", lineHeight: 1.1,
        }}>{m.title}</div>
        <div style={{
          fontFamily: "var(--serif)", fontStyle: "italic", fontSize: 15,
          color: "var(--muted)", lineHeight: 1.55, textWrap: "pretty",
        }}>{m.blurb}</div>
      </div>
    </div>
  );
};

const ChatC = () => {
  const [view, setView] = useState("Chat");
  const [collapsed, setCollapsed] = useState(false);
  return (
    <div style={{
      width: "100%", height: "100%",
      background: "var(--bg)", color: "var(--text)",
      fontFamily: "var(--body)",
      display: "grid", gridTemplateRows: "auto 1fr",
      overflow: "hidden",
    }}>
      <TopbarC onToggleNav={() => setCollapsed(c => !c)} navCollapsed={collapsed} />
      <div style={{ display: "grid", gridTemplateColumns: `${collapsed ? 56 : 268}px 1fr`, minHeight: 0 }}>
        <UnifiedRail collapsed={collapsed} onToggle={() => setCollapsed(c => !c)} view={view} onView={setView} />
        <main style={{ display: "grid", gridTemplateRows: view === "Chat" ? "auto 1fr auto" : "1fr", minHeight: 0, background: "var(--panel)" }}>
          {view === "Chat" && (
          <div style={{
            display: "grid", gridTemplateColumns: "1fr auto", alignItems: "center",
            padding: "12px 24px", borderBottom: "1px solid var(--border)",
            background: "var(--bg-accent)",
            gap: 14,
          }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 5, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                <span style={{
                  width: 26, height: 26, borderRadius: 7, flexShrink: 0,
                  background: "radial-gradient(circle at 30% 30%, #e08a5f, #b95c31 70%)",
                  color: "#fff8f2", display: "grid", placeItems: "center",
                  fontFamily: "var(--mono)", fontSize: 12, fontWeight: 700,
                }}>T</span>
                <div style={{
                  fontFamily: "var(--serif)", fontSize: 26, fontWeight: 500,
                  letterSpacing: "-.025em", color: "var(--text-strong)", lineHeight: 1,
                }}>test-agent</div>
                <span style={{
                  fontFamily: "var(--serif)", fontStyle: "italic", fontSize: 20,
                  color: "var(--muted-soft)", lineHeight: 1, fontWeight: 400,
                }}> / </span>
                <div style={{
                  fontFamily: "var(--serif)", fontSize: 22, fontWeight: 500,
                  letterSpacing: "-.02em", color: "var(--accent)", lineHeight: 1,
                }}>rate-limit triage</div>
                <span style={{
                  fontFamily: "var(--mono)", fontSize: 9.5, letterSpacing: ".14em",
                  color: "var(--muted-soft)", padding: "2px 7px",
                  border: "1px solid var(--border)", borderRadius: 999,
                }}>INCARNATION · 8 MSG</span>
              </div>
              <div style={{
                display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap",
                fontFamily: "var(--mono)", fontSize: 10.5, color: "var(--muted)",
                letterSpacing: "-.005em",
              }}>
                <span><span style={{ color: "var(--muted-soft)" }}>id</span> sess_8af2…4c1d</span>
                <span style={{ color: "var(--muted-soft)" }}>·</span>
                <span><span style={{ color: "var(--muted-soft)" }}>model</span> <span style={{ color: "var(--text)" }}>anthropic/claude-sonnet-4.5</span></span>
                <span style={{ color: "var(--muted-soft)" }}>·</span>
                <span><span style={{ color: "var(--muted-soft)" }}>ws</span> <span style={{ color: "var(--text)" }}>/tmp/test-agent-workspace</span></span>
                <span style={{ color: "var(--muted-soft)" }}>·</span>
                <span style={{
                  display: "inline-flex", alignItems: "center", gap: 6,
                  padding: "2px 9px", borderRadius: 999,
                  border: "1px solid var(--accent-soft)",
                  background: "var(--accent-subtle)",
                  color: "var(--accent)", fontWeight: 600,
                }}>
                  <span style={{ color: "var(--muted-soft)", fontWeight: 500 }}>spent</span>
                  <span>$0.0427</span>
                </span>
              </div>
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              <button style={{
                fontFamily: "var(--mono)", fontSize: 10.5, padding: "2px 7px",
                border: "1px solid var(--border)", borderRadius: 6,
                background: "var(--bg-elevated)", color: "var(--accent)", cursor: "pointer",
                letterSpacing: ".06em",
              }}>memory</button>
              <button style={{...ledgerChip}}>fork</button>
            </div>
          </div>
          )}
          {view === "Chat" ? (
            <div style={{ overflowY: "auto", padding: "0 24px" }}>
              {(() => { let u = 0; return transcript.map((t, i) => { if (t.role === "user") u++; return <LedgerTurn key={i} turn={t} idx={i} userIdx={u} />; }); })()}
              <div style={{
                display: "grid", gridTemplateColumns: "118px 1fr",
                borderTop: "1px solid var(--border)", padding: "12px 0",
              }}>
                <div style={{
                  paddingRight: 16, borderRight: "1px solid var(--border)",
                  textAlign: "right", fontFamily: "var(--mono)", fontSize: 11,
                  color: "var(--muted-soft)",
                }}>
                  <div style={{ fontSize: 9.5, letterSpacing: ".22em", textTransform: "uppercase", color: "var(--accent)", fontWeight: 600 }}>Aurelia</div>
                  <div style={{ marginTop: 4 }}>10:44</div>
                </div>
                <div style={{ padding: "0 0 0 22px", display: "flex", alignItems: "center", gap: 8, color: "var(--muted)", fontSize: 12.5 }}>
                  <span style={{ fontFamily: "var(--serif)", fontStyle: "italic" }}>reloading test-agent</span>
                  <span style={{ display: "inline-flex", gap: 3 }}>
                    <span style={dot} /><span style={{...dot, animationDelay: ".15s"}} /><span style={{...dot, animationDelay: ".3s"}} />
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <ComingSoon view={view} />
          )}
          {view === "Chat" && <ComposerB />}
        </main>
      </div>
    </div>
  );
};

window.ChatA = ChatA;
window.ChatB = ChatB;
window.ChatC = ChatC;
