export default function ChatPage({ params }: { params: { id: string } }) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-text-muted text-sm">
      Chat &amp; Refine — project {params.id} — coming soon
    </div>
  );
}
