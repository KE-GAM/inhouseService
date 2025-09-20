import React, { useEffect, useMemo, useState } from "react";

/**
 * NotaOfficeMap – a single-file, drop‑in React component
 * ------------------------------------------------------
 * Purpose
 *  - Replace text-only desk/room lists with a clickable SVG floor plan
 *  - Show live availability (Red/White or Red/Blue) for each resource
 *  - Click a resource to open its reservation list and quick actions
 *
 * How to use
 *  <NotaOfficeMap
 *     fetchStatus={async () => fetch("/api/deskroom/status").then(r => r.json())}
 *     fetchReservations={async (id) => fetch(`/api/deskroom/${id}/reservations`).then(r => r.json())}
 *     onReserve={(id) => openModal(id)}   // optional
 *     colorScheme="red-white"             // or "red-blue"
 *  />
 *
 * Notes
 *  - This component does NOT require a raster image. The floor plan is an SVG you can edit.
 *  - To go real-time, wire a WebSocket that calls setLiveStatus() whenever an update arrives.
 *  - All geometry (x,y,width,height) is editable in the ROOMS / DESKS arrays.
 */

// ----------------------------- Types -----------------------------
export type ResourceStatus = "available" | "occupied" | "maintenance";
export type ResourceType = "room" | "desk";

export interface ResourceBase {
  id: string;
  name: string;
  type: ResourceType;
  status: ResourceStatus;
}

export interface ReservationItem {
  id: string;
  resourceId: string;
  user: string;
  start: string; // ISO
  end: string;   // ISO
}

// ----------------------- Geometry (editable) ----------------------
// Adjust to match your actual office. Coordinates are in SVG px.
// Rooms first (big blocks), then individual desks/focus seats.
const ROOMS = [
  { id: "lounge", name: "Lounge", x: 20, y: 20, w: 300, h: 160 },
  { id: "mini-lib", name: "Mini Library", x: 340, y: 20, w: 300, h: 160 },
  { id: "meeting-big", name: "Big Conf. Room", x: 660, y: 20, w: 260, h: 160 },
  { id: "ownership", name: "Ownership Room", x: 660, y: 200, w: 260, h: 160 },
  { id: "snack", name: "Snack Bar", x: 20, y: 200, w: 260, h: 120 },
  { id: "cowork", name: "Coworking", x: 300, y: 200, w: 340, h: 260 },
];

const DESKS = [
  // Coworking round tables (dots)
  { id: "cw-d1", name: "CW-1", x: 340, y: 240, r: 12 },
  { id: "cw-d2", name: "CW-2", x: 380, y: 240, r: 12 },
  { id: "cw-d3", name: "CW-3", x: 420, y: 240, r: 12 },
  { id: "cw-d4", name: "CW-4", x: 460, y: 240, r: 12 },
  { id: "cw-d5", name: "CW-5", x: 500, y: 240, r: 12 },
  { id: "cw-d6", name: "CW-6", x: 540, y: 240, r: 12 },
  // Library focus seats (small rectangles)
  { id: "lib-f1", name: "Focus-1", x: 360, y: 60, w: 22, h: 22 },
  { id: "lib-f2", name: "Focus-2", x: 390, y: 60, w: 22, h: 22 },
  { id: "lib-f3", name: "Focus-3", x: 420, y: 60, w: 22, h: 22 },
  { id: "lib-f4", name: "Focus-4", x: 450, y: 60, w: 22, h: 22 },
];

// --------------------------- Component ---------------------------
interface Props {
  colorScheme?: "red-white" | "red-blue";
  fetchStatus?: () => Promise<ResourceBase[]>;
  fetchReservations?: (resourceId: string) => Promise<ReservationItem[]>;
  onReserve?: (resourceId: string) => void;
}

const defaultStatusSeed: ResourceBase[] = [
  // seed mock; replaced by fetchStatus when provided
  ...ROOMS.map(r => ({ id: r.id, name: r.name, type: "room" as const, status: "available" as const })),
  ...DESKS.map(d => ({ id: d.id, name: d.name, type: "desk" as const, status: Math.random() < 0.25 ? "occupied" : "available" as const })),
];

export default function NotaOfficeMap({
  colorScheme = "red-white",
  fetchStatus,
  fetchReservations,
  onReserve,
}: Props) {
  const [liveStatus, setLiveStatus] = useState<ResourceBase[]>(defaultStatusSeed);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = useMemo(() => liveStatus.find(r => r.id === selectedId) || null, [liveStatus, selectedId]);
  const [reservations, setReservations] = useState<ReservationItem[] | null>(null);
  const [loading, setLoading] = useState(false);

  // Initial and periodic status fetch
  useEffect(() => {
    let stop = false;
    const pull = async () => {
      if (!fetchStatus) return; // keep mock if not provided
      try {
        const data = await fetchStatus();
        if (!stop && Array.isArray(data)) setLiveStatus(prev => mergeStatus(prev, data));
      } catch (e) {
        // swallow; keep mock
      }
    };
    pull();
    const t = setInterval(pull, 10_000); // poll every 10s
    return () => { stop = true; clearInterval(t); };
  }, [fetchStatus]);

  // Example WebSocket hook (pseudo)
  // useEffect(() => {
  //   const ws = new WebSocket("wss://your.server/ws/deskroom");
  //   ws.onmessage = (ev) => {
  //     const update = JSON.parse(ev.data); // { id, status }
  //     setLiveStatus(prev => prev.map(r => r.id === update.id ? { ...r, status: update.status } : r));
  //   };
  //   return () => ws.close();
  // }, []);

  useEffect(() => {
    if (!selected || !fetchReservations) { setReservations(null); return; }
    (async () => {
      setLoading(true);
      try {
        const data = await fetchReservations(selected.id);
        setReservations(data);
      } finally { setLoading(false); }
    })();
  }, [selected?.id]);

  const colors = getColors(colorScheme);

  return (
    <div className="w-full grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-4">
      {/* Map Panel */}
      <div className="rounded-2xl shadow p-3 bg-white border border-gray-200">
        <div className="flex items-center justify-between px-2 py-1">
          <h2 className="text-lg font-semibold">Nota Office – Live Desk & Room Map</h2>
          <Legend colors={colors} />
        </div>
        <svg viewBox="0 0 960 520" className="w-full h-[520px]">
          {/* Canvas background */}
          <rect x={0} y={0} width={960} height={520} rx={16} fill="#fafafa" stroke="#e5e7eb" />

          {/* Rooms */}
          {ROOMS.map(room => {
            const s = liveStatus.find(r => r.id === room.id);
            const fill = statusFill(s?.status || "available", colors);
            return (
              <g key={room.id} onClick={() => setSelectedId(room.id)} className="cursor-pointer">
                <rect x={room.x} y={room.y} width={room.w} height={room.h} rx={10} fill={fill.bg} stroke={fill.stroke} strokeWidth={2} />
                <text x={room.x + 12} y={room.y + 24} fontSize={14} fontWeight={600} fill="#111827">{room.name}</text>
                {/* Occupancy dot */}
                <circle cx={room.x + room.w - 18} cy={room.y + 18} r={7} fill={fill.dot} />
              </g>
            );
          })}

          {/* Desks / seats */}
          {DESKS.map(d => {
            const s = liveStatus.find(r => r.id === d.id);
            const fill = statusFill(s?.status || "available", colors);

            if ("r" in d) {
              return (
                <g key={d.id} onClick={() => setSelectedId(d.id)} className="cursor-pointer">
                  <circle cx={d.x} cy={d.y} r={d.r} fill={fill.bg} stroke={fill.stroke} strokeWidth={2} />
                  <circle cx={d.x} cy={d.y} r={5} fill={fill.dot} />
                </g>
              );
            }
            return (
              <g key={d.id} onClick={() => setSelectedId(d.id)} className="cursor-pointer">
                <rect x={d.x} y={d.y} width={d.w!} height={d.h!} rx={4} fill={fill.bg} stroke={fill.stroke} strokeWidth={2} />
                <circle cx={d.x + d.w! - 6} cy={d.y + 6} r={4} fill={fill.dot} />
              </g>
            );
          })}
        </svg>
      </div>

      {/* Detail / Reservations Panel */}
      <div className="rounded-2xl shadow bg-white border border-gray-200 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
          <div>
            <div className="text-sm text-gray-500">Selected</div>
            <div className="text-lg font-semibold">{selected ? `${selected.name} (${selected.type})` : "None"}</div>
          </div>
          {selected && onReserve && (
            <button
              className="px-3 py-1.5 rounded-lg text-sm font-medium bg-black text-white hover:opacity-90"
              onClick={() => onReserve(selected.id)}
            >Reserve</button>
          )}
        </div>

        <div className="p-4">
          {!selected && <p className="text-sm text-gray-500">Click any room/desk on the map to see reservations.</p>}
          {selected && (
            <>
              <div className="mb-3 text-sm">
                <span className="text-gray-500 mr-2">Status:</span>
                <StatusBadge status={selected.status} colors={colors} />
              </div>
              <div className="text-sm text-gray-500 mb-2">Reservations</div>
              {loading && <div className="text-sm">Loading…</div>}
              {!loading && (!reservations || reservations.length === 0) && (
                <div className="text-sm text-gray-500">No reservations.</div>
              )}
              {!loading && reservations && reservations.length > 0 && (
                <ul className="space-y-2">
                  {reservations.map(r => (
                    <li key={r.id} className="border border-gray-200 rounded-lg p-2">
                      <div className="font-medium text-sm">{r.user}</div>
                      <div className="text-xs text-gray-500">{fmt(r.start)} → {fmt(r.end)}</div>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// --------------------------- Utilities ---------------------------
function mergeStatus(curr: ResourceBase[], incoming: ResourceBase[]): ResourceBase[] {
  const map = new Map(curr.map(r => [r.id, r] as const));
  for (const n of incoming) map.set(n.id, { ...(map.get(n.id) || n), ...n });
  return Array.from(map.values());
}

function fmt(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString();
}

function getColors(scheme: "red-white" | "red-blue") {
  if (scheme === "red-blue") {
    return {
      availableBg: "#e6f0ff",
      availableStroke: "#90b4ff",
      availableDot: "#1967ff",
      occupiedBg: "#ffe6e6",
      occupiedStroke: "#ff9aa5",
      occupiedDot: "#e11900",
      maintenanceBg: "#fff7e6",
      maintenanceStroke: "#ffd699",
      maintenanceDot: "#b26b00",
    } as const;
  }
  // red-white
  return {
    availableBg: "#ffffff",
    availableStroke: "#cbd5e1",
    availableDot: "#111827",
    occupiedBg: "#ffe6e6",
    occupiedStroke: "#ff9aa5",
    occupiedDot: "#e11900",
    maintenanceBg: "#fff7e6",
    maintenanceStroke: "#ffd699",
    maintenanceDot: "#b26b00",
  } as const;
}

function statusFill(status: ResourceStatus, colors: ReturnType<typeof getColors>) {
  switch (status) {
    case "occupied": return { bg: colors.occupiedBg, stroke: colors.occupiedStroke, dot: colors.occupiedDot };
    case "maintenance": return { bg: colors.maintenanceBg, stroke: colors.maintenanceStroke, dot: colors.maintenanceDot };
    default: return { bg: colors.availableBg, stroke: colors.availableStroke, dot: colors.availableDot };
  }
}

function Legend({ colors }: { colors: ReturnType<typeof getColors> }) {
  const Item = ({ c, label }: { c: string; label: string }) => (
    <div className="flex items-center gap-2 text-xs text-gray-700">
      <span className="inline-block w-3 h-3 rounded-full" style={{ background: c }} />
      {label}
    </div>
  );
  return (
    <div className="flex items-center gap-4">
      <Item c={colors.availableDot} label="Available" />
      <Item c={colors.occupiedDot} label="Occupied" />
      <Item c={colors.maintenanceDot} label="Maintenance" />
    </div>
  );
}

function StatusBadge({ status, colors }: { status: ResourceStatus; colors: ReturnType<typeof getColors> }) {
  const s = statusFill(status, colors);
  return (
    <span className="inline-flex items-center gap-2 px-2 py-1 rounded-md border text-xs"
          style={{ background: s.bg, borderColor: s.stroke }}>
      <span className="w-2 h-2 rounded-full" style={{ background: s.dot }} />
      {status}
    </span>
  );
}
