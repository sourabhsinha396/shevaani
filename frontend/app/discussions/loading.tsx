/**
 * The catalogue fetches on the client, so without this the route transition
 * lands on an empty page for as long as the request takes. Card-shaped
 * placeholders rather than a spinner: the layout does not jump when the real
 * cards arrive, which is the whole reason to bother.
 */
export default function Loading() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-12">
      <div className="bg-muted h-9 w-64 animate-pulse rounded" />
      <div className="bg-muted mt-3 h-5 w-96 max-w-full animate-pulse rounded" />
      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="bg-muted h-44 animate-pulse rounded-xl" />
        ))}
      </div>
    </div>
  );
}
