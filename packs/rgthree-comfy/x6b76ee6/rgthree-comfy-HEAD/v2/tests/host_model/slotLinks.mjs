// Test shim for the host frontend's `@/lib/litegraph/src/node/slotLinks` (frontend 1.53.4,
// slotLinks.ts:39-46): "The link targeting an input slot, resolved in the owning graph."
// The host reads it from its link store; the test graph answers it from its own link table.
export function inputLink(graph, nodeId, slot) {
  return graph.inputLink(String(nodeId), slot)
}
