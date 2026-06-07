"use client";

import { Tooltip } from "@base-ui/react/tooltip";
import { Info } from "lucide-react";

interface MetricInfoProps {
  what: string;
  why: string;
  target?: string;
}

export function MetricInfo({ what, why, target }: MetricInfoProps) {
  return (
    <Tooltip.Provider>
      <Tooltip.Root>
        <Tooltip.Trigger className="inline-flex items-center text-text-muted hover:text-foreground transition-colors cursor-default">
          <Info className="size-3.5" />
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Positioner side="top" sideOffset={6}>
            <Tooltip.Popup className="z-50 max-w-[260px] rounded-lg border border-border bg-card p-3 shadow-lg text-xs text-foreground space-y-2">
              <div>
                <p className="font-semibold mb-0.5">What it measures</p>
                <p className="text-text-secondary">{what}</p>
              </div>
              <div>
                <p className="font-semibold mb-0.5">Why it matters</p>
                <p className="text-text-secondary">{why}</p>
              </div>
              {target && (
                <div>
                  <p className="font-semibold mb-0.5">Target</p>
                  <p className="text-text-secondary">{target}</p>
                </div>
              )}
            </Tooltip.Popup>
          </Tooltip.Positioner>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  );
}
