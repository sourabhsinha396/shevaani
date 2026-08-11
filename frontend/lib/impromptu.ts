import { config } from "./config";
import { FALLBACK_TOPICS } from "./impromptu-topics";
import type { ImpromptuTopic } from "./types";

/**
 * The impromptu tool's topic bank, fetched on the server. Same pattern and
 * same reasoning as `getSiteConfig`: public, identical for every visitor,
 * wanted before first paint, cached by Next's fetch cache - so not the
 * credentialed `lib/api.ts` client.
 */

/** Topics change when somebody edits them in sqladmin, i.e. rarely. Five
 *  minutes keeps the tool page static while new tracks still show up without
 *  a redeploy. */
const REVALIDATE_SECONDS = 300;

export async function getImpromptuTopics(): Promise<ImpromptuTopic[]> {
  try {
    const response = await fetch(`${config.apiUrl}/api/v1/tools/impromptu/topics`, {
      next: { revalidate: REVALIDATE_SECONDS },
    });
    if (!response.ok) return FALLBACK_TOPICS;
    const topics = (await response.json()) as ImpromptuTopic[];
    // An empty bank means someone deactivated everything - the fallback keeps
    // the tool usable while they figure out what they meant.
    return topics.length > 0 ? topics : FALLBACK_TOPICS;
  } catch {
    return FALLBACK_TOPICS;
  }
}
