import { Ctx } from "../context";

/** One editor feature (F1 select-to-impact, F2 CodeLens, ...). Each lives in its own file in this folder. */
export interface Feature {
  id: string;
  activate(ctx: Ctx): void;
}
