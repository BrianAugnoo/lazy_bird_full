import type { Agent } from '@/core/types/api';

export function relativeTime(iso: string): string {
  const seconds = (Date.now() - new Date(iso).getTime()) / 1000;
  if (!Number.isFinite(seconds)) return '';
  if (seconds < 60) return 'now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  if (seconds < 86400 * 7) return `${Math.floor(seconds / 86400)}d`;
  return new Date(iso).toLocaleDateString();
}

/** Agents ordered as a tree: masters first, each followed by its sub-agents (shown once). */
export function agentTree(agents: Agent[]): Array<{ agent: Agent; depth: number }> {
  const byId = new Map(agents.map((agent) => [agent.id, agent]));
  const placed = new Set<number>();
  const result: Array<{ agent: Agent; depth: number }> = [];
  const visit = (agent: Agent, depth: number) => {
    if (placed.has(agent.id)) return;
    placed.add(agent.id);
    result.push({ agent, depth });
    for (const childId of agent.sub_agents_ids) {
      const child = byId.get(childId);
      if (child) visit(child, depth + 1);
    }
  };
  const roots = agents.filter((agent) => agent.parent_agents_ids.length === 0);
  roots.sort((a, b) => Number(b.master) - Number(a.master) || a.id - b.id);
  for (const root of roots) visit(root, 0);
  for (const agent of agents) visit(agent, 0); // cycles
  return result;
}
