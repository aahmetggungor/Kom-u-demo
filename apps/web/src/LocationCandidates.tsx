import type { Report } from './api';
import { formatText, type Catalogue } from './i18n';

export function LocationCandidates({reports,editable,onChoose,copy}:{reports:Report[];editable:boolean;onChoose:(lat:number,lon:number)=>void;copy:Catalogue}) {
  const precisionNames:Record<string,string>={building:copy.building,street:copy.street,area:copy.area};
  const candidates=reports.flatMap(report=>(report.analysis.location_candidates??[]).map(candidate=>({...candidate,reportId:report.id})));
  if(!candidates.length)return null;
  return <section className="location-candidates" aria-label={copy.possibleLocations}>
    <h3>{copy.possibleLocations}</h3><p>{copy.locationCandidatesHelp}</p>
    {candidates.map((candidate,index)=><article key={`${candidate.reportId}-${candidate.provider_id}-${index}`}>
      <strong>{candidate.display_name}</strong>
      <small>{precisionNames[candidate.precision]??candidate.precision} · {formatText(copy.textMatch,{value:Math.round(candidate.match_score*100)})} · {candidate.provenance}</small>
      <small>{candidate.lat.toFixed(5)}, {candidate.lon.toFixed(5)}</small>
      {editable&&<button className="quiet" onClick={()=>onChoose(candidate.lat,candidate.lon)}>{copy.copyToForm}</button>}
    </article>)}
  </section>;
}
