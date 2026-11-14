/** Light grey page skeletons — no full-page spinners. */
export function RunsSkeleton() {
  return (
    <div aria-busy="true" className="space-y-3">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="h-11 rounded-md bg-[#F5F5F5]" />
      ))}
    </div>
  );
}

export function RunPageSkeleton() {
  return (
    <div aria-busy="true" className="space-y-6">
      <div className="h-4 w-24 rounded bg-[#F5F5F5]" />
      <div className="h-24 rounded-lg border border-line bg-[#F5F5F5]" />
      <div className="h-48 rounded-lg border border-line bg-[#F5F5F5]" />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-24 rounded-lg border border-line bg-[#F5F5F5]" />
        ))}
      </div>
    </div>
  );
}
