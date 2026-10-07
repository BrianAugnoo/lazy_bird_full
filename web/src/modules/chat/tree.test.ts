import { describe, expect, it } from 'vitest';
import type { Agent } from '@/core/types/api';
import { agentTree } from './tree';

const agent = (id: number, changes: Partial<Agent> = {}): Agent => ({
  id,
  session_id: 1,
  name: `a${id}`,
  description: null,
  instructions: null,
  instruction_fulls: [],
  instruction_subs: [],
  skills: [],
  tools: [],
  hooks: [],
  master: false,
  meta: null,
  sub_agents_ids: [],
  parent_agents_ids: [],
  preset: null,
  valid: true,
  errors: {},
  ...changes,
});

describe('agentTree', () => {
  it('lists the master first with its sub-agents nested once', () => {
    const agents = [
      agent(1, { parent_agents_ids: [2, 3] }),
      agent(2, { sub_agents_ids: [1] }),
      agent(3, { master: true, sub_agents_ids: [2, 1] }),
      agent(4),
    ];
    expect(agentTree(agents).map(({ agent: item, depth }) => [item.id, depth])).toEqual([
      [3, 0],
      [2, 1],
      [1, 2],
      [4, 0],
    ]);
  });

  it('still shows agents caught in a cycle', () => {
    const agents = [agent(1, { sub_agents_ids: [2], parent_agents_ids: [2] }), agent(2, { sub_agents_ids: [1], parent_agents_ids: [1] })];
    expect(agentTree(agents)).toHaveLength(2);
  });
});
