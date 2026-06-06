export default function RedactionPage({ params }: { params: { id: string } }) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-text-muted text-sm">
      Redaction Review — project {params.id} — coming soon
    </div>
  );
}
