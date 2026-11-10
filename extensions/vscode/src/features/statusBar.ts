import { Feature } from "./types";

export const statusBar: Feature = {
  id: "statusBar",
  activate(ctx) {
    ctx.status.command = "codetwin.selectTests";
    ctx.status.text = "$(beaker) CodeTwin";
    ctx.status.show();
    ctx.onDidDecide((d) => {
      const risk = (d.residual_risk * 100).toFixed(1);
      ctx.status.text = `$(beaker) ${d.decision === "proceed" ? "proceed" : "run more"} · risk ${risk}%`;
    });
  },
};
