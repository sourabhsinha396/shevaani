import type { ImpromptuTopic } from "./types";

/**
 * The rigged spin, for recording lessons.
 *
 * `/admin/impromptu` stages a topic; the next spin of the tool *in the same
 * browser* runs the whole reel theatre and lands on it, then the stage is
 * clear and spins are random again. localStorage is the entire mechanism, and
 * deliberately so:
 *
 * - it reaches only the browser that staged it, so a learner mid-practice can
 *   never be handed the operator's script;
 * - it needs no backend, no cache window, no cleanup job - closing the
 *   browser or spinning once disposes of it;
 * - nothing about it appears on screen, which is the point of using it on
 *   camera.
 *
 * Anyone could set this key in their own devtools. That is not a hole: it
 * rigs their own browser's dice, which they were free to do anyway. The
 * /admin page is a convenience, not the boundary.
 */

const STAGE_KEY = "shevaani.impromptu.staged";

export function stageTopic(topic: Pick<ImpromptuTopic, "text"> & Partial<ImpromptuTopic>): void {
  try {
    localStorage.setItem(STAGE_KEY, JSON.stringify(topic));
  } catch {
    // Storage full or blocked - staging is a convenience, never worth a crash.
  }
}

export function readStagedTopic(): ImpromptuTopic | null {
  try {
    const raw = localStorage.getItem(STAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<ImpromptuTopic>;
    if (typeof parsed.text !== "string" || parsed.text.trim().length === 0) return null;
    return {
      text: parsed.text,
      category: parsed.category ?? "Staged",
      track: parsed.track ?? "Staged",
      difficulty: null,
    };
  } catch {
    return null;
  }
}

/** Read-and-clear: the stage holds exactly one spin. */
export function consumeStagedTopic(): ImpromptuTopic | null {
  const topic = readStagedTopic();
  if (topic) clearStagedTopic();
  return topic;
}

export function clearStagedTopic(): void {
  try {
    localStorage.removeItem(STAGE_KEY);
  } catch {
    // Same rule as above.
  }
}
