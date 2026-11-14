import { useState } from "react";
import { Check, ChevronDown, Copy, FileCode } from "lucide-react";
import { iconProps } from "../icons";
import { lineCount, sketchName } from "../sketch";
import { Collapsible, Tooltip } from "./ui";

/** Collapsible generated sketch for Write firmware reports. */
export function FirmwareCard({ firmware, defaultOpen = false }: { firmware: string; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const [copied, setCopied] = useState(false);
  if (!firmware.trim()) {
    return null;
  }
  const lines = lineCount(firmware);
  const name = sketchName(firmware);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(firmware);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard can be denied.
    }
  };

  return (
    <section aria-label="Generated firmware">
      <Collapsible.Root open={open} onOpenChange={setOpen}>
        <div className="border border-line bg-white" style={{ borderRadius: 8 }}>
          <div className="flex items-center gap-2 px-4 py-3">
            <Collapsible.Trigger className="flex min-w-0 flex-1 items-center gap-2 text-left text-sm text-ink" aria-label={open ? "Collapse firmware" : "Expand firmware"}>
              <FileCode {...iconProps} className="shrink-0 text-muted" />
              <span className="font-medium">Firmware</span>
              <span className="truncate font-mono text-xs text-muted">{name}</span>
              <span className="num shrink-0 text-xs text-muted">{lines} lines</span>
              <ChevronDown {...iconProps} className={`ml-auto shrink-0 text-muted transition-transform ${open ? "rotate-180" : ""}`} />
            </Collapsible.Trigger>
            <Tooltip content={copied ? "Copied" : "Copy firmware"}>
              <button type="button" aria-label="Copy firmware" className="key inline-flex h-8 w-8 items-center justify-center rounded-md border border-line text-muted hover:text-ink" onClick={copy}>
                {copied ? <Check {...iconProps} /> : <Copy {...iconProps} />}
              </button>
            </Tooltip>
          </div>
          <Collapsible.Content className="fold">
            <pre className="scroll max-h-[420px] overflow-auto border-t border-line bg-[#FAFAFA] p-4 font-mono text-[13px] leading-5 text-ink">{firmware}</pre>
          </Collapsible.Content>
        </div>
      </Collapsible.Root>
    </section>
  );
}
