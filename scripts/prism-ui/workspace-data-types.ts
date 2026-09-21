export type SourceRecord = { id: string; locator: Record<string, unknown>; data: Record<string, unknown> };
export type SourceSummary = { source_id: string; filename: string; sha256: string; kind: string; status: string; record_count: number };
export type SourceData = SourceSummary & { records: SourceRecord[]; review: { snapshot_id: string; latest: Record<string, { event_id: string; action: string; author: string; reviewer_kind: string; note: string }> } };
export type ReviewExport = { url: string; run_url: string; training_candidates: number };
