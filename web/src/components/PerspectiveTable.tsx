import { useEffect, useRef, useState } from "react";
import type { Client, Table } from "@perspective-dev/client";
import "@perspective-dev/viewer/dist/css/themes.css";
import "@perspective-dev/viewer/dist/css/pro.css";
import "@perspective-dev/viewer-datagrid/dist/css/perspective-viewer-datagrid.css";

type PerspectiveViewerElement = HTMLElement & {
  load: (table: unknown) => Promise<void>;
  restore: (config: Record<string, unknown>) => Promise<void>;
  delete?: () => Promise<void>;
};

type PerspectiveTableProps = {
  rows: Array<Record<string, string | number | null>>;
  ariaLabel: string;
  emptyText: string;
};

export function PerspectiveTable({ rows, ariaLabel, emptyText }: PerspectiveTableProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    let viewer: PerspectiveViewerElement | undefined;
    let table: Table | undefined;
    let client: Client | undefined;

    async function mount() {
      if (!hostRef.current || !rows.length) return;
      try {
        const [{ default: perspective }] = await Promise.all([
          import("@perspective-dev/client"),
          import("@perspective-dev/viewer"),
          import("@perspective-dev/viewer-datagrid"),
        ]);
        if (cancelled || !hostRef.current) return;
        client = await perspective.worker();
        table = await client.table(rows);
        viewer = document.createElement("perspective-viewer") as PerspectiveViewerElement;
        viewer.setAttribute("theme", "Pro Light");
        viewer.setAttribute("aria-label", ariaLabel);
        viewer.className = "perspective-grid";
        hostRef.current.replaceChildren(viewer);
        await viewer.load(table);
        await viewer.restore({ plugin: "Datagrid", settings: false });
      } catch (reason) {
        if (!cancelled) setError(reason instanceof Error ? reason.message : String(reason));
      }
    }

    void mount();
    return () => {
      cancelled = true;
      void viewer?.delete?.();
      void table?.delete?.();
      client?.terminate?.();
      hostRef.current?.replaceChildren();
    };
  }, [ariaLabel, rows]);

  if (!rows.length) return <div className="perspective-empty">{emptyText}</div>;
  if (error) return <div className="perspective-empty" role="alert">{error}</div>;
  return <div ref={hostRef} className="perspective-host" />;
}
