export default function TechStackPage({ params }: { params: { id: string } }) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-text-muted text-sm">
      Tech Stack — project {params.id} — coming soon
    </div>
  );
}
