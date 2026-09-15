export type Case = { id: string; merged_into_id: string|null; status: string; verification_status: string; urgency_level: string; incident_type: string; needs: string[]; ai_confidence: number; location_status: string; location: {lat: number | null; lon: number | null}; region: string | null; human_review_required: boolean; assigned_team_id: string | null; version: number; report_count: number; created_at: string; updated_at: string };
export type LocationCandidate = {provider_id:string;display_name:string;lat:number;lon:number;precision:string;match_score:number;provenance:string};
export type TranslationProvenance = {route:string[];model_revisions:string[];pivoted:boolean;protection_version?:string|null;protected_categories?:string[];warnings?:string[]};
export type AudioMetadata = {id:string;state:'QUARANTINED'|'SCAN_PASSED'|'SCAN_ERROR'|'RELEASED'|'REJECTED';version:number;scan_verdict:string|null;scan_reason_code:string|null;scanner_revision:string|null;duration_ms:number;decision_reason:string|null};
export type Transcript = {id:string;state:'QUEUED'|'RUNNING'|'DONE'|'FAILED';attempts:number;original_text:string|null;language:string|null;model_revision:string|null;duration_seconds:number|null;confidence:number|null;warnings:string[];error_code:string|null;corrected_text:string|null;corrected_language:string|null;correction_reason:string|null;version:number};
export type Report = {id: string; source: string; original_text: string; original_language: string; address_raw: string | null; processing_status: string; audio:AudioMetadata|null;transcript:Transcript|null;analysis: {translated_text?: Record<string,string>; translation_provenance?:Record<string,TranslationProvenance>;warnings?: string[]; pipeline_version?: string;location_candidates?:LocationCandidate[]}};
export type Detail = Case & {reports: Report[]};
export type Team = {id: string; name: string};
export type MapLayer = {id:string;kind:string;name:string;provenance:string;updated_at:string;geojson:Exclude<import('maplibre-gl').GeoJSONSourceSpecification['data'],string>};
export class ApiError extends Error { constructor(public status: number, message: string) { super(message); } }
export async function request<T>(token: string, path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch('/api/v1' + path, { method: body === undefined ? 'GET' : 'POST', headers: {Authorization: `Bearer ${token}`, ...(body === undefined ? {} : {'Content-Type':'application/json'})}, body: body === undefined ? undefined : JSON.stringify(body), signal });
  if (!response.ok) { const value = await response.json().catch(() => ({})); throw new ApiError(response.status, typeof value.detail === 'string' ? value.detail : `HTTP ${response.status}`); }
  return response.json();
}
export function coordinatePair(lat: string, lon: string, messages={required:'İki koordinat da gerekli',invalid:'Geçersiz koordinat'}) {
  if (!lat.trim() || !lon.trim()) throw new Error(messages.required);
  const a = Number(lat), b = Number(lon);
  if (!Number.isFinite(a) || !Number.isFinite(b) || Math.abs(a) > 90 || Math.abs(b) > 180) throw new Error(messages.invalid);
  return {lat:a, lon:b};
}
export async function uploadAudio<T>(token:string,reportId:string,audio:Blob):Promise<T>{
  const response=await fetch(`/api/v1/reports/${reportId}/audio`,{method:'POST',headers:{Authorization:`Bearer ${token}`,'Content-Type':'audio/wav'},body:audio});
  if(!response.ok){const value=await response.json().catch(()=>({}));throw new ApiError(response.status,typeof value.detail==='string'?value.detail:`HTTP ${response.status}`);}
  return response.json();
}
