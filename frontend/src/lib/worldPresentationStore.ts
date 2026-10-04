/** Client-side agent pose interpolation (v1.4 NET-002 PresentationStore). */
import type { Agent } from "@/lib/api";

type Pose = {
  x: number;
  z: number;
  tx: number;
  tz: number;
  at: number;
  behavior?: string;
};

const BLEND_MS = 420;

export class WorldPresentationStore {
  private poses = new Map<string, Pose>();

  seedFromAgents(agents: Agent[]) {
    const now = performance.now();
    for (const a of agents) {
      const x = a.world_x ?? 0;
      const z = a.world_z ?? 0;
      this.poses.set(a.id, { x, z, tx: x, tz: z, at: now, behavior: a.behavior });
    }
  }

  applyTransform(t: {
    agent_id: string;
    world_x: number;
    world_z: number;
    behavior?: string;
  }) {
    const prev = this.poses.get(t.agent_id);
    const now = performance.now();
    this.poses.set(t.agent_id, {
      x: prev?.x ?? t.world_x,
      z: prev?.z ?? t.world_z,
      tx: t.world_x,
      tz: t.world_z,
      at: now,
      behavior: t.behavior ?? prev?.behavior,
    });
  }

  applyBatch(transforms: Array<{
    agent_id: string;
    world_x: number;
    world_z: number;
    behavior?: string;
  }>) {
    for (const t of transforms) this.applyTransform(t);
  }

  /** Local prediction for controlled player between server acks. */
  setLocal(agentId: string, world_x: number, world_z: number) {
    const now = performance.now();
    this.poses.set(agentId, { x: world_x, z: world_z, tx: world_x, tz: world_z, at: now });
  }

  getInterpolated(agentId: string, now = performance.now()): { x: number; z: number } | null {
    const p = this.poses.get(agentId);
    if (!p) return null;
    const t = Math.min(1, (now - p.at) / BLEND_MS);
    return {
      x: p.x + (p.tx - p.x) * t,
      z: p.z + (p.tz - p.z) * t,
    };
  }

  getWorldPosition(
    agentId: string,
    mapWidth: number,
    mapHeight: number,
    scale: number,
  ): [number, number] | null {
    const p = this.getInterpolated(agentId);
    if (!p) return null;
    return [
      (p.x / 2) * mapWidth * scale,
      (p.z / 2) * mapHeight * scale,
    ];
  }
}

export function worldNormFromScene(
  x: number,
  z: number,
  mapWidth: number,
  mapHeight: number,
  scale: number,
): [number, number] {
  const wx = (x / (mapWidth * scale)) * 2;
  const wz = (z / (mapHeight * scale)) * 2;
  return [
    Math.max(-1, Math.min(1, wx)),
    Math.max(-1, Math.min(1, wz)),
  ];
}
