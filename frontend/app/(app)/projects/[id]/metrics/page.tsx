export default function MetricsPage({ params }: { params: { id: string } }) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-text-muted text-sm">
      Metrics — project {params.id} — coming soon
    </div>
  );
}
