export default function EpicsPage({ params }: { params: { id: string } }) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-text-muted text-sm">
      Epics &amp; Tasks — project {params.id} — coming soon
    </div>
  );
}
