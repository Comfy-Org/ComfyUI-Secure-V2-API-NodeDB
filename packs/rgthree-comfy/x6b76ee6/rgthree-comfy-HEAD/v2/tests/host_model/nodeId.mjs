// Test shim for the host frontend's `@/types/nodeId` (frontend 1.53.4, nodeId.ts:7-9):
// `toNodeId(value)` is `String(value)` behind a type brand.
export function toNodeId(value) {
  return String(value)
}
