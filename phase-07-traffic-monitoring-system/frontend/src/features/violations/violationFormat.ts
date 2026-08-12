import type { ViolationType } from "../../types";

export const violationLabel = (type: ViolationType) => ({
  OVERSPEED: "Overspeed",
  NO_HELMET: "No helmet",
  WRONG_LANE: "Wrong lane",
  WRONG_DIRECTION: "Wrong direction"
})[type];
