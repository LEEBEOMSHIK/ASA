import assert from "node:assert/strict";
import { test } from "node:test";
import { speechVideoFit, speechVideoPlacement } from "./speech-video-timing.ts";

const window = { start_seconds: 0.75, end_seconds: 2 };

test("places a clip-local observation on the full edit timeline", () => {
  assert.deepEqual(speechVideoPlacement(window, 5), { start: 5.75, end: 7 });
  assert.equal(speechVideoPlacement(window, -1), null);
  assert.equal(speechVideoPlacement(window, 3599), null);
  assert.equal(speechVideoPlacement(window, NaN), null);
});

test("uses the generated duration and actual placement to check the observation window", () => {
  assert.equal(speechVideoFit(window, 5, { start: 5.75, end: 7 }, 1), "fits");
  assert.equal(speechVideoFit(window, 5, { start: 5.75, end: 6.5 }, 1), "outside");
  assert.equal(speechVideoFit(window, 5, { start: 6, end: 8 }, 1.05), "outside");
  assert.equal(speechVideoFit(window, 5, { start: 5.5, end: 7 }, 0.5), "outside");
  assert.equal(speechVideoFit(window, 5, { start: 5.75, end: 7 }, null), "unmeasured");
});
