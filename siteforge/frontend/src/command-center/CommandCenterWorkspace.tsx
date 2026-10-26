import { useEffect, useRef } from "react";
import { createRoot, type Root } from "react-dom/client";
import CommandCenterApp from "./App";
import ccCss from "./styles.css?raw";

export default function CommandCenterWorkspace({ onExit }: {onExit: () => void}) {
  const node = useRef<HTMLDivElement>(null);
  const root = useRef<Root | null>(null);
  useEffect(() => {
    const host = node.current;
    if (!host) return;
    const shadow = host.attachShadow({mode: "open"});
    const style = document.createElement("style");
    style.textContent = `:host { display:block; min-height:100vh; font-family: Inter, "Segoe UI",sans-serif; --ink:#16231f; --muted:#66736d; --line:#dce5e0; --paper:#f3f6f4; --green:#087354; --nav:#101e19; --red:#c83d36; --orange:#d77806; } ${ccCss}`;
    shadow.append(style);
    const mount = document.createElement("div");
    shadow.append(mount);
    root.current = createRoot(mount);
    root.current.render(<><div style={{padding:"10px 20px",background:"#101e19",color:"white"}}><button type="button" style={{background:"transparent",border:"1px solid #fff",color:"#fff",padding:"8px 12px",cursor:"pointer"}} onClick={onExit}>← Back to ZerroR Workspaces</button></div><CommandCenterApp /></>);
    return () => {root.current?.unmount(); root.current = null;};
  }, [onExit]);
  return <div ref={node} aria-label="Command Center workspace" />;
}
