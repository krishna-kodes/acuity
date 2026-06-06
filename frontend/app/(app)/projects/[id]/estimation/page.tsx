export default function EstimationPage({ params }: { params: { id: string } }) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-text-muted text-sm">
      Effort Estimation — project {params.id} — coming soon
    </div>
  );
}
