// Pure workflow-state transformation. No ambient DOM, graph or storage access.
// Host menu/property dispatch and workflow-registry consumers remain pending.
export const ROLES = Object.freeze({
  send_prompt_target: { label: 'Send Prompt Target', emoji: '\uD83D\uDCDD' },
  send_gen_params: { label: 'Send Gen Params Target', emoji: '\uD83D\uDD27' },
  meta_primary_model: { label: 'Meta hints: Primary Model', emoji: '\uD83D\uDCA1' },
  meta_primary_sampler: { label: 'Meta hints: Primary Sampler', emoji: '\uD83D\uDCA1' },
  meta_positive_prompt: { label: 'Meta hints: Positive Prompt', emoji: '\uD83D\uDCA1' },
  meta_negative_prompt: { label: 'Meta hints: Negative Prompt', emoji: '\uD83D\uDCA1' },
});

const PREFIX = /^(\u2709\uFE0F?|\u2699\uFE0F?|\uD83D\uDCDD|\uD83C\uDF9B\uFE0F?|\uD83D\uDD27|\uD83D\uDCA1)\s*/;

export function markState(state, role) {
  if (!Object.hasOwn(ROLES, role)) return state;
  const properties = { ...state.properties, lm_marker_role: role };
  if (!properties.lm_marker_original_title) {
    properties.lm_marker_original_title = state.title || '';
  }
  return {
    ...state, properties,
    title: `${ROLES[role].emoji} ${properties.lm_marker_original_title}`,
  };
}

export function clearState(state) {
  const properties = { ...state.properties };
  delete properties.lm_marker_role;
  const cleaned = state.title?.replace(PREFIX, '');
  let title = state.title;
  if (cleaned && cleaned !== state.title) title = cleaned;
  else if (properties.lm_marker_original_title !== undefined) {
    title = properties.lm_marker_original_title;
  }
  delete properties.lm_marker_original_title;
  return { ...state, title, properties };
}
