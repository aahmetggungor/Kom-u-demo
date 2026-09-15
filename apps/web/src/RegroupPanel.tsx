import { useEffect, useState } from 'react';
import {request,type Case,type Detail} from './api';
import {formatText,type Catalogue} from './i18n';
import {SimilarCases} from './SimilarCases';

export function RegroupPanel({detail,cases,token,copy,onChange,onError}:{detail:Detail;cases:Case[];token:string;copy:Catalogue;onChange:(id?:string)=>Promise<void>;onError:(e:unknown)=>void}) {
  const [targetId,setTargetId]=useState(''), [target,setTarget]=useState<Detail|null>(null);
  const [reason,setReason]=useState(''), [confirmed,setConfirmed]=useState(false), [busy,setBusy]=useState(false), [selected,setSelected]=useState<string[]>([]);
  useEffect(()=>{
    setTarget(null);setConfirmed(false);
    if(!targetId)return;
    const controller=new AbortController();
    request<Detail>(token,`/cases/${targetId}`,undefined,controller.signal).then(setTarget).catch(e=>{if(!controller.signal.aborted)onError(e);});
    return()=>controller.abort();
  },[targetId,token,onError]);
  async function act(kind:'merge'|'split'){
    setBusy(true);
    try{
      const body=kind==='merge'?{target_case_id:target!.id,expected_source_version:detail.version,expected_target_version:target!.version,reason}:{expected_version:detail.version,report_ids:selected,reason};
      const result=await request<Case>(token,`/cases/${detail.id}/${kind}`,body);
      await onChange(result.id);
    }catch(e){onError(e);}finally{setBusy(false);}
  }
  const pending=detail.reports.some(r=>['QUEUED','RUNNING'].includes(r.processing_status));
  return <section className="regroup">
    <SimilarCases caseId={detail.id} token={token} onSelect={setTargetId} copy={copy}/>
    <h3>{copy.regroup}</h3><p>{copy.regroupHelp}</p>{pending&&<p role="status">{copy.analysisPending}</p>}
    <label>{copy.mergeTarget}<select value={targetId} onChange={e=>setTargetId(e.target.value)}><option value="">{copy.selectTarget}</option>{cases.filter(c=>c.id!==detail.id&&c.status==='OPEN').map(c=><option key={c.id} value={c.id}>#{c.id.slice(0,8)} · {c.region??copy.regionUnclear} · {formatText(copy.reports,{count:c.report_count})}</option>)}</select></label>
    {target&&<div className="target-preview"><strong>{formatText(copy.targetVersion,{id:target.id.slice(0,8),version:target.version})}</strong>{target.reports.map(r=><p key={r.id} lang={r.original_language}>{r.original_text}</p>)}</div>}
    <label>{copy.regroupReason}<textarea value={reason} onChange={e=>setReason(e.target.value)} maxLength={500}/></label>
    <label className="confirm-group"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>{copy.regroupConfirm}</label>
    <button disabled={busy||pending||!target||!confirmed||reason.trim().length<3} onClick={()=>act('merge')}>{copy.merge}</button>
    {detail.reports.length>1&&<><h3>{copy.splitReports}</h3>{detail.reports.map(r=><label className="confirm-group" key={r.id}><input type="checkbox" checked={selected.includes(r.id)} onChange={e=>setSelected(current=>e.target.checked?[...current,r.id]:current.filter(id=>id!==r.id))}/><span>{r.original_language.toUpperCase()} · {r.original_text.slice(0,180)}</span></label>)}<button disabled={busy||pending||!confirmed||reason.trim().length<3||selected.length===0||selected.length===detail.reports.length} onClick={()=>act('split')}>{copy.split}</button></>}
  </section>;
}
