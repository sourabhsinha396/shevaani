export default function Loading() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <div className="bg-muted h-5 w-32 animate-pulse rounded" />
      <div className="bg-muted mt-6 h-10 w-3/4 animate-pulse rounded" />
      <div className="bg-muted mt-3 h-5 w-1/2 animate-pulse rounded" />
      <div className="bg-muted mt-8 h-56 animate-pulse rounded-xl" />
      <div className="bg-muted mt-4 h-32 animate-pulse rounded-xl" />
    </div>
  );
}
