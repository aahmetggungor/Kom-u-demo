import {useEffect,useState} from 'react';
import {request} from './api';
import {formatText,type Catalogue} from './i18n';

type Candidate={case_id:string;semantic_similarity:number;distance_m:number|null;time_delta_seconds:number};
type Result={enabled:boolean;model_revision:string|null;items:Candidate[]};
export function SimilarCases({caseId,token,onSelect,copy}:{caseId:string;token:string;onSelect:(id:string)=>void;copy:Catalogue}){
  const [result,setResult]=useState<Result|null>(null),[error,setError]=useState(false);
  useEffect(()=>{
    setResult(null);setError(false);
    const controller=new AbortController();
    let timer:ReturnType<typeof setTimeout>|undefined;
    async function refresh(){
      try{const value=await request<Result>(token,`/cases/${caseId}/similar`,undefined,controller.signal);if(!controller.signal.aborted){setResult(value);setError(false);}}
      catch{if(!controller.signal.aborted)setError(true);}
      finally{if(!controller.signal.aborted)timer=setTimeout(refresh,15000);}
    }
    void refresh();
    return()=>{controller.abort();clearTimeout(timer);};
  },[caseId,token]);
  return <section><h3>{copy.semanticSuggestions}</h3>{error?<p role="status">{copy.suggestionsFailed}</p>:!result?<p>{copy.suggestionsLoading}</p>:!result.enabled?<p>{copy.modelDisabled}</p>:<>
    <p>{copy.similarityWarning}</p>
    {result.items.length===0?<p>{copy.noComparable}</p>:result.items.map(item=><div key={item.case_id}>
      <button type="button" onClick={()=>onSelect(item.case_id)}>{formatText(copy.compareReports,{id:item.case_id.slice(0,8)})}</button>
      <p>{formatText(copy.similarityLine,{score:item.semantic_similarity.toFixed(3),distance:item.distance_m===null?copy.unknownDistance:`${Math.round(item.distance_m)} m`,minutes:Math.round(item.time_delta_seconds/60)})}</p>
    </div>)}<small>{copy.bgeReview}</small></>}</section>;
}
