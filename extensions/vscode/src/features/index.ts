// Every feature of the extension. To add one: create `features/<name>.ts` exporting a Feature,
// then add ONE line to this list (keep one entry per line to avoid merge conflicts).
import { commands } from "./commands";
import { statusBar } from "./statusBar";
import { Feature } from "./types";

export const features: Feature[] = [
  statusBar,
  commands,
];
