export default function TeamPage({ params }: { params: { id: string } }) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-text-muted text-sm">
      Team Suggestion — project {params.id} — coming soon
    </div>
  );
}
