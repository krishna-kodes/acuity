"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getBranding, updateBranding, resetBranding, type BrandingSettings } from "@/lib/api";

function ColorField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-semibold uppercase tracking-widest text-text-muted">
        {label}
      </label>
      <div className="flex items-center gap-2">
        <input
          type="color"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-9 h-9 rounded border border-border cursor-pointer bg-transparent p-0.5"
        />
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          maxLength={7}
          pattern="^#[0-9A-Fa-f]{6}$"
          className="w-28 px-3 py-1.5 text-sm border border-border rounded-lg bg-surface-subtle text-foreground focus:outline-none focus:ring-1 focus:ring-accent font-mono"
        />
        <span
          className="w-8 h-8 rounded border border-border"
          style={{ backgroundColor: value }}
        />
      </div>
    </div>
  );
}

function TextField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-semibold uppercase tracking-widest text-text-muted">
        {label}
      </label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-80 px-3 py-1.5 text-sm border border-border rounded-lg bg-surface-subtle text-foreground focus:outline-none focus:ring-1 focus:ring-accent"
      />
    </div>
  );
}

const DEFAULTS: Omit<BrandingSettings, "updated_at"> = {
  company_name: "",
  primary_color: "#2E5FA3",
  secondary_color: "#1A3A6B",
  prepared_by: "",
};

export default function BrandingPage() {
  const queryClient = useQueryClient();
  const { data, isPending: queryPending, isError } = useQuery({
    queryKey: ["branding"],
    queryFn: getBranding,
    refetchOnWindowFocus: false,
  });

  const [form, setForm] = useState<Omit<BrandingSettings, "updated_at">>(DEFAULTS);
  const [toast, setToast] = useState<{ ok: boolean; msg: string } | null>(null);

  useEffect(() => {
    if (data) {
      setForm({
        company_name: data.company_name,
        primary_color: data.primary_color,
        secondary_color: data.secondary_color,
        prepared_by: data.prepared_by,
      });
    }
  }, [data]);

  const showToast = (ok: boolean, msg: string) => {
    setToast({ ok, msg });
    setTimeout(() => setToast(null), ok ? 3000 : 4000);
  };

  const saveMutation = useMutation({
    mutationFn: updateBranding,
    onSuccess: (updated) => {
      queryClient.setQueryData(["branding"], updated);
      showToast(true, "Branding saved.");
    },
    onError: (err: Error) => showToast(false, err.message),
  });

  const resetMutation = useMutation({
    mutationFn: resetBranding,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["branding"] });
      showToast(true, "Restored to defaults.");
    },
    onError: (err: Error) => showToast(false, err.message),
  });

  const busy = saveMutation.isPending || resetMutation.isPending;

  return (
    <div className="px-6 py-8 max-w-2xl mx-auto flex flex-col gap-8">
      <div>
        <h1 className="text-base font-semibold text-foreground">Branding</h1>
        <p className="text-xs text-text-muted mt-0.5">
          Applied to generated proposal documents.
        </p>
      </div>

      {isError && (
        <p className="text-sm text-destructive">Failed to load branding settings. Please refresh.</p>
      )}

      {queryPending ? (
        <p className="text-sm text-text-muted">Loading…</p>
      ) : (
        <div className="bg-card border border-border rounded-xl p-6 flex flex-col gap-6">
          <TextField
            label="Company Name"
            value={form.company_name}
            onChange={(v) => setForm((f) => ({ ...f, company_name: v }))}
            placeholder="Acme Inc"
          />
          <TextField
            label="Prepared By"
            value={form.prepared_by}
            onChange={(v) => setForm((f) => ({ ...f, prepared_by: v }))}
            placeholder="PM Name"
          />
          <ColorField
            label="Primary Color (table headers)"
            value={form.primary_color}
            onChange={(v) => setForm((f) => ({ ...f, primary_color: v }))}
          />
          <ColorField
            label="Secondary Color (heading text)"
            value={form.secondary_color}
            onChange={(v) => setForm((f) => ({ ...f, secondary_color: v }))}
          />

          <div className="flex items-center gap-3 pt-2">
            <button
              type="button"
              onClick={() => saveMutation.mutate(form)}
              disabled={busy}
              className="px-4 py-2 text-sm font-medium bg-primary text-primary-foreground rounded-lg hover:bg-accent-hover disabled:opacity-50 transition-colors"
            >
              {saveMutation.isPending ? "Saving…" : "Save Branding"}
            </button>
            <button
              type="button"
              onClick={() => resetMutation.mutate()}
              disabled={busy}
              className="px-4 py-2 text-sm font-medium border border-border text-foreground rounded-lg hover:bg-surface-subtle disabled:opacity-50 transition-colors"
            >
              {resetMutation.isPending ? "Resetting…" : "Restore Defaults"}
            </button>
            {toast && (
              <span className={`text-sm ${toast.ok ? "text-success" : "text-destructive"}`}>
                {toast.msg}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
