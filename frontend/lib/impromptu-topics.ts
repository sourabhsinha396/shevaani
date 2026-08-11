import type { ImpromptuTopic } from "./types";

/**
 * The fallback topic bank, used only when the API is unreachable - which
 * includes build time, when the backend container usually isn't up yet. Same
 * deal as `DEFAULT_SITE_CONFIG`: degrading to a working tool beats degrading
 * to a spinner.
 *
 * The canonical bank lives in the `impromptu_topics` table (seeded by
 * migration 0013, grown from sqladmin). This copy only has to be plausible,
 * not complete, so it carries the General track alone - the specialised
 * tracks (MBA, IELTS, cabin crew…) exist only where someone maintains them.
 */

const EVERYDAY = "Everyday things";
const ABSTRACT = "Big ideas";
const OPINION = "Hot takes";
const INTERVIEW = "Interview classics";

function general(texts: string[], category: string): ImpromptuTopic[] {
  return texts.map((text) => ({ text, category, track: "General", difficulty: null }));
}

export const FALLBACK_TOPICS: ImpromptuTopic[] = [
  ...general(
    [
      "Low tide",
      "The first rain",
      "Ceiling fans",
      "Street food",
      "Cutting chai",
      "Traffic jams",
      "Power cuts",
      "Local trains",
      "Sunday mornings",
      "House plants",
      "Umbrellas",
      "Standing in queues",
      "Auto-rickshaws",
      "Loose change",
      "Alarm clocks",
      "Wedding buffets",
      "Rooftops",
      "Gully cricket",
      "Old photographs",
      "Handwriting",
      "The window seat",
      "Mangoes",
      "School tiffin",
      "Barbershops",
      "Night markets",
      "Railway stations",
      "Your grandparents' house",
      "Flying kites",
      "Stray dogs",
      "Steel tumblers",
      "Bus conductors",
      "Shortcuts through lanes",
      "Pressure cookers",
      "Monsoon evenings",
      "Borrowed books",
      "Phone chargers",
      "Lift small talk",
      "Packing a suitcase",
    ],
    EVERYDAY,
  ),
  ...general(
    [
      "Courage",
      "Patience",
      "Luck",
      "Silence",
      "Nostalgia",
      "Ambition",
      "Boredom",
      "Curiosity",
      "Regret",
      "Discipline",
      "Jealousy",
      "Gratitude",
      "Failure",
      "Second chances",
      "Small talk",
      "White lies",
      "Overthinking",
      "Homesickness",
      "Beginnings",
      "Growing up",
      "Letting go",
      "Comfort zones",
      "Procrastination",
      "Peer pressure",
      "Self-doubt",
      "Kindness to strangers",
      "Waiting",
      "Being early",
      "Changing your mind",
    ],
    ABSTRACT,
  ),
  ...general(
    [
      "Marks matter less than people think",
      "Everyone should live alone at least once",
      "Social media does more good than harm",
      "Homework should be abolished",
      "Small towns are better than big cities",
      "Money can buy happiness",
      "AI will create more jobs than it destroys",
      "Breakfast is overrated",
      "Group projects teach more than exams",
      "Everyone should learn to cook",
      "Work from home is here to stay",
      "Cricket gets too much attention in India",
      "Fluent English is not the same as intelligence",
      "College is not for everyone",
      "Board games beat video games",
      "It is okay to quit things",
      "Every student should take a gap year",
      "Cash is better than cards",
      "Winters are better than summers",
      "Reading the book beats watching the film",
    ],
    OPINION,
  ),
  ...general(
    [
      "Tell me about a time you failed",
      "Describe yourself in three words",
      "Why should we pick you?",
      "A skill you taught yourself",
      "Your proudest moment",
      "A decision you would redo",
      "Where do you see yourself in five years?",
      "A time you disagreed with a senior",
      "Your biggest strength, with proof",
      "Explain your hobby like I'm five",
      "A lesson a mistake taught you",
      "The best advice you ever received",
      "A time you changed someone's mind",
      "What would your friends say about you?",
    ],
    INTERVIEW,
  ),
];
