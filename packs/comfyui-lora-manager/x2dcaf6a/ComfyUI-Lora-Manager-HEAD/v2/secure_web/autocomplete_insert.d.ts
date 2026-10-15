/** Owned planner declarations; no public SDK surface is added. */
export interface NativeUsagePayload {
  readonly success?: unknown
  readonly usage_tips?: unknown
}
export interface NativeSyntaxSelection {
  get(): unknown
  received(data: unknown): void
  failed(): void
}
export function createSyntaxSelection(): NativeSyntaxSelection
export function planLoraInsertion(
  relativePath: string,
  effectiveSyntaxFormat: unknown,
  data: NativeUsagePayload | null,
  appendComma: boolean
): string
