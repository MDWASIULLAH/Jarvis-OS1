"use client";

import { useEffect } from "react";
import { useUIStore } from "../store/ui-store";

/**
 * Applies the persisted theme to <html data-theme> for the whole app.
 *
 * Previously this lived inside SettingsCenter, so `data-theme` was only ever set
 * once the user opened Settings -- every other screen rendered with the
 * attribute absent. Worse, it wrote the raw store value, and "system" is not a
 * value any stylesheet matches, so choosing it silently unstyled the app.
 *
 * `system` is now resolved against the OS preference and kept in sync while the
 * user changes it, which is the behaviour the setting implies.
 */
export function ThemeManager() {
  const theme = useUIStore(state => state.theme);
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      const resolved = theme === "system" ? (media.matches ? "dark" : "light") : theme;
      document.documentElement.dataset.theme = resolved;
      document.documentElement.style.colorScheme = resolved;
    };
    apply();
    if (theme !== "system") return;
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [theme]);
  return null;
}

/**
 * Runs before React hydrates so the first paint already has the right theme.
 * Reads the same zustand persist key the store writes, and falls back to light.
 */
export const themeBootstrapScript = `(function(){try{
var raw=localStorage.getItem("jarvis-ui-preferences-v5");
var t=raw?(JSON.parse(raw).state||{}).theme:"light";
if(t==="system"||!t){t=window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";}
document.documentElement.setAttribute("data-theme",t);
document.documentElement.style.colorScheme=t;
}catch(e){document.documentElement.setAttribute("data-theme","light");}})();`;
