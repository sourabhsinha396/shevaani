export default function Loading() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-12">
      <div className="bg-muted h-9 w-72 animate-pulse rounded" />
      <div className="bg-muted mt-3 h-5 w-96 max-w-full animate-pulse rounded" />
      <div className="mt-8 grid gap-4 sm:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="bg-muted h-24 animate-pulse rounded-xl" />
        ))}
      </div>
      <div className="bg-muted mt-6 h-64 animate-pulse rounded-xl" />
    </div>
  );
}
