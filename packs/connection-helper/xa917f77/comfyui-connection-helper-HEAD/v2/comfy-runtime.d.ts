import type { Comfy } from "./comfy-api";

declare module "/comfy/api/v2.js" {
  export const comfy: Comfy;
}
