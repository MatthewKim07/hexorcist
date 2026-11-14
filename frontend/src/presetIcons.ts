import { Activity, Bug, LucideIcon, ShieldCheck, Siren, Thermometer, ToggleLeft, Wand2 } from "lucide-react";

/** Device icon for a preset id (home cards and run header). */
export function presetIcon(id: string): LucideIcon {
  switch (id) {
    case "thermostat":
      return Thermometer;
    case "button":
      return ToggleLeft;
    case "logger":
      return Activity;
    case "alarm":
      return Siren;
    case "containment":
      return ShieldCheck;
    default:
      return Bug;
  }
}

/** Best-effort icon from a run title and mode when no preset id is known. */
export function runIcon(title: string, mode: string): LucideIcon {
  const t = title.toLowerCase();
  if (/thermostat|hysteresis/.test(t)) {
    return Thermometer;
  }
  if (/button|debounce/.test(t)) {
    return ToggleLeft;
  }
  if (/logger|units|sensor/.test(t)) {
    return Activity;
  }
  if (/alarm|siren|blocking/.test(t)) {
    return Siren;
  }
  if (/contain/.test(t)) {
    return ShieldCheck;
  }
  return mode === "build" ? Wand2 : Bug;
}
