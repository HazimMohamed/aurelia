/* global React, ReactDOM, ChatA, ChatB, ChatC, DesignCanvas, DCSection, DCArtboard, TweaksPanel, useTweaks, TweakSection, TweakRadio, TweakColor, TweakToggle */
const { useEffect } = React;

const DEFAULTS = /*EDITMODE-BEGIN*/{
  "accent": "#c9673a",
  "showSessions": true,
  "showLedgerSessions": true,
  "showContextStrip": true,
  "density": "comfortable"
}/*EDITMODE-END*/;

function applyAccent(hex) {
  const root = document.documentElement;
  root.style.setProperty("--accent", hex);
  // derive related tokens (cheap mix)
  const subtle = hexA(hex, .12);
  const soft = hexA(hex, .22);
  const hover = darken(hex, 0.08);
  root.style.setProperty("--accent-hover", hover);
  root.style.setProperty("--accent-subtle", subtle);
  root.style.setProperty("--accent-soft", soft);
}
function hexA(hex, a) {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0,2),16), g = parseInt(h.slice(2,4),16), b = parseInt(h.slice(4,6),16);
  return `rgba(${r},${g},${b},${a})`;
}
function darken(hex, amt) {
  const h = hex.replace("#", "");
  const r = Math.max(0, parseInt(h.slice(0,2),16) - Math.round(255*amt));
  const g = Math.max(0, parseInt(h.slice(2,4),16) - Math.round(255*amt));
  const b = Math.max(0, parseInt(h.slice(4,6),16) - Math.round(255*amt));
  return "#" + [r,g,b].map(n => n.toString(16).padStart(2,"0")).join("");
}

function App() {
  const [t, setTweak] = useTweaks(DEFAULTS);
  useEffect(() => { applyAccent(t.accent); }, [t.accent]);

  // density just scales root font slightly
  const fontPx = t.density === "compact" ? 13 : t.density === "cozy" ? 14.5 : 14;
  useEffect(() => {
    document.documentElement.style.fontSize = fontPx + "px";
  }, [fontPx]);

  return (
    <React.Fragment>
      <DesignCanvas
        title="Aurelia · Chat refinements"
        subtitle="Two directions for the main conversation surface. Both keep the warm terracotta DNA — A tightens what's there, B reimagines the transcript as an editorial ledger. Drag artboards, double-click labels to rename, click to focus."
      >
        <DCSection id="chat" title="Chat — refinements">
          <DCArtboard id="compact" label="A · Compact — denser rhythm, sessions rail, inline meta" width={1320} height={900}>
            <ChatA showSessions={t.showSessions} />
          </DCArtboard>
          <DCArtboard id="ledger" label="B · Ledger — editorial gutter, hierarchical sessions, prominent agent/incarnation" width={1480} height={900}>
            <ChatB showSessions={t.showLedgerSessions} />
          </DCArtboard>
          <DCArtboard id="unified" label="C · Unified — one rail. Chat/Agents/Logs lift into the topbar; agent tree is the spine." width={1480} height={900}>
            <ChatC />
          </DCArtboard>
        </DCSection>
      </DesignCanvas>

      <TweaksPanel title="Tweaks">
        <TweakSection label="Brand">
          <TweakColor
            label="Accent"
            value={t.accent}
            onChange={(v) => setTweak("accent", v)}
            options={["#c9673a", "#b35a2e", "#9e4e2a", "#b8893a"]}
          />
        </TweakSection>
        <TweakSection label="Density">
          <TweakRadio
            label="Base scale"
            value={t.density}
            onChange={(v) => setTweak("density", v)}
            options={[
              { value: "compact", label: "Tight" },
              { value: "comfortable", label: "Mid" },
              { value: "cozy", label: "Loose" },
            ]}
          />
        </TweakSection>
        <TweakSection label="Variant A · Compact">
          <TweakToggle
            label="Sessions rail"
            value={t.showSessions}
            onChange={(v) => setTweak("showSessions", v)}
          />
        </TweakSection>
        <TweakSection label="Variant B · Ledger">
          <TweakToggle
            label="Sessions rail"
            value={t.showLedgerSessions}
            onChange={(v) => setTweak("showLedgerSessions", v)}
          />
        </TweakSection>
      </TweaksPanel>
    </React.Fragment>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
