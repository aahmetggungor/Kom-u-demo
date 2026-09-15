import { Suspense, lazy, useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, coordinatePair, request, type Case, type Detail, type Report, type Team } from './api';
import { catalogues, formatText, initialLocale, type Catalogue, type UiLocale } from './i18n';
import { LocationCandidates } from './LocationCandidates';
import { RegroupPanel } from './RegroupPanel';
import './style.css';

const CoordinationMap = lazy(() => import('./Map').then(module => ({default: module.CoordinationMap})));
const localeTags: Record<UiLocale,string> = {tr:'tr-TR',el:'el-GR',en:'en-GB'};
type ConnectionState = 'disconnected'|'connecting'|'live'|'reconnecting';

function labels(copy: Catalogue) {
  return {
    urgency: {CRITICAL:copy.urgencyCritical,HIGH:copy.urgencyHigh,MEDIUM:copy.urgencyMedium,LOW:copy.urgencyLow,UNKNOWN:copy.urgencyUnknown} as Record<string,string>,
    needs: {rescue:copy.needRescue,medical:copy.needMedical,water:copy.needWater,shelter:copy.needShelter,food:copy.needFood} as Record<string,string>,
    status: {OPEN:copy.statusOpen,DISPATCHED:copy.statusDispatched,RESOLVED:copy.statusResolved,MERGED:copy.statusMerged} as Record<string,string>,
  };
}

export default function App() {
  const [uiLocale,setUiLocale] = useState<UiLocale>(initialLocale);
  const copy = catalogues[uiLocale], names = labels(copy);
  const t = (key:keyof Catalogue, values?:Record<string,string|number>) => formatText(copy[key],values);
  const [token,setToken] = useState(''), [entry,setEntry] = useState('');
  const [role,setRole] = useState(''), [cases,setCases] = useState<Case[]>([]), [total,setTotal] = useState(0), [detail,setDetail] = useState<Detail|null>(null);
  const [teams,setTeams] = useState<Team[]>([]), [error,setError] = useState(''), [notice,setNotice] = useState('');
  const [connection,setConnection] = useState<ConnectionState>('disconnected'), [updated,setUpdated] = useState<Date|null>(null);
  const [urgency,setUrgency] = useState(''), [verification,setVerification] = useState(''), [language,setLanguage] = useState('');
  const [incident,setIncident] = useState(''), [status,setStatus] = useState(''), [region,setRegion] = useState(''), [teamFilter,setTeamFilter] = useState(''), [timeRange,setTimeRange] = useState('');
  const [text,setText] = useState(''), [reportLanguage,setReportLanguage] = useState('tr'), [address,setAddress] = useState('');
  const [busy,setBusy] = useState(false), [showForm,setShowForm] = useState(false);
  const selected = useRef<string|null>(null), pending = useRef<{client_id:string;text:string;source:string;language:string;occurred_at:string;address_raw:string}|null>(null);
  const fetchSequence = useRef(0), detailSequence = useRef(0), sessionGeneration = useRef(0);

  useEffect(()=>{
    document.documentElement.lang=uiLocale;
    window.localStorage.setItem('komsu-ui-language',uiLocale);
  },[uiLocale]);

  const logout = useCallback(() => {
    sessionGeneration.current++; fetchSequence.current++; detailSequence.current++;
    selected.current=null; pending.current=null;
    setToken('');setEntry('');setRole('');setCases([]);setTeams([]);setDetail(null);
    setTotal(0);setUpdated(null);setText('');setAddress('');setNotice('');setShowForm(false);setBusy(false);setConnection('disconnected');
  },[]);
  const allowed = role === 'admin' || role === 'coordinator';
  const fail = useCallback((e:unknown) => {
    setError(e instanceof Error ? e.message : catalogues[uiLocale].operationFailed);
    if(e instanceof ApiError && e.status === 401) logout();
  },[logout,uiLocale]);
  const refresh = useCallback(async () => {
    if (!token) return;
    const sequence = ++fetchSequence.current;
    const params = new URLSearchParams({limit:'100'});
    for(const [key,value] of Object.entries({urgency,verification,language,incident_type:incident,status,region,team_id:teamFilter})) if(value) params.set(key,value);
    if(timeRange)params.set('since',new Date(Date.now()-Number(timeRange)*60*60*1000).toISOString());
    const result = await request<{items:Case[];total:number}>(token,'/cases?'+params).catch(e=>{if(sequence===fetchSequence.current)throw e;return null;});
    if(!result || sequence !== fetchSequence.current) return;
    setCases(result.items); setTotal(result.total); setUpdated(new Date());
  },[token,urgency,verification,language,incident,status,region,teamFilter,timeRange]);
  const selectCase = useCallback(async(id:string) => {
    selected.current=id; const sequence=++detailSequence.current, generation=sessionGeneration.current;
    try {
      const result=await request<Detail>(token,`/cases/${id}`);
      if(sequence===detailSequence.current && selected.current===id) setDetail(result);
    } catch(e) { if(generation===sessionGeneration.current) fail(e); }
  },[token,fail]);

  useEffect(() => {refresh().catch(fail);},[refresh,fail]);
  useEffect(() => {
    if(!token) return;
    let disposed=false, socket:WebSocket|undefined, timer:ReturnType<typeof setTimeout>|undefined, cursor=0;
    const connect=()=>{
      setConnection('connecting');
      socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/api/v1/events/ws`);
      socket.onopen=()=>socket?.send(JSON.stringify({token,after:cursor}));
      socket.onmessage=(e)=>{
        if(disposed)return;
        const message=JSON.parse(e.data); setConnection('live');
        if(message.items.length){cursor=message.items.at(-1).id;refresh().catch(fail);if(selected.current)selectCase(selected.current);}
      };
      socket.onclose=()=>{if(disposed)return;setConnection('reconnecting');timer=setTimeout(connect,5000);};
      socket.onerror=()=>socket?.close();
    };
    connect();
    const poll=setInterval(()=>refresh().catch(fail),15000);
    return()=>{disposed=true;socket?.close();clearTimeout(timer);clearInterval(poll);};
  },[token,refresh,selectCase,fail]);

  async function login(e:React.FormEvent){
    e.preventDefault();setError('');
    try {const result=await request<{role:string}>(entry,'/auth/me');const list=await request<Team[]>(entry,'/teams');setRole(result.role);setTeams(list);setToken(entry);setEntry('');}
    catch(e){fail(e);}
  }
  async function submit(e:React.FormEvent){
    e.preventDefault();setBusy(true);setError('');const generation=sessionGeneration.current;
    try{
      if(!pending.current)pending.current={client_id:crypto.randomUUID(),text,source:'manual',language:reportLanguage,occurred_at:new Date().toISOString(),address_raw:address};
      const result=await request<{case_id:string}>(token,'/reports',pending.current);
      if(generation!==sessionGeneration.current)return;
      pending.current=null;setText('');setAddress('');setShowForm(false);setNotice(copy.receivedNotice);
      await refresh();if(generation===sessionGeneration.current)await selectCase(result.case_id);
    }catch(e){if(generation===sessionGeneration.current)fail(e);}finally{if(generation===sessionGeneration.current)setBusy(false);}
  }
  const stats={critical:cases.filter(c=>c.urgency_level==='CRITICAL').length,review:cases.filter(c=>c.human_review_required).length,unlocated:cases.filter(c=>c.location.lat===null).length};
  const connectionText={disconnected:copy.disconnected,connecting:copy.connecting,live:copy.live,reconnecting:copy.reconnecting}[connection];

  return <>
    <header>
      <a className="brand" href="/">komşu<span>γείτονας</span></a><div className="header-divider"/>
      <div className="workspace"><strong>{copy.workspace}</strong><span>{copy.workspaceSub}</span></div>
      <label className="ui-language"><span>{copy.language}</span><select value={uiLocale} onChange={e=>setUiLocale(e.target.value as UiLocale)}><option value="tr">Türkçe</option><option value="el">Ελληνικά</option><option value="en">English</option></select></label>
      <div className="connection"><i className={connection==='live'?'live':''}/>{connectionText}</div>
      {token&&<button className="quiet" onClick={logout}>{copy.logout}</button>}
    </header>
    <div className="environment">{copy.environment} <span>{copy.environmentWarning}</span></div>
    {!token ? <main className="login">
      <div className="eyebrow">{copy.loginEyebrow}</div><h1>{copy.loginTitleA}<br/>{copy.loginTitleB}</h1><p>{copy.loginIntro}</p>
      <form onSubmit={login}><label>{copy.accessKey}<input type="password" autoComplete="off" value={entry} onChange={e=>setEntry(e.target.value)} required placeholder={copy.accessKeyPlaceholder}/></label><button type="submit">{copy.openDashboard}</button></form><small>{copy.memoryOnly}</small>
    </main> : <main className="dashboard">
      <div className="page-title"><div><div className="eyebrow">{copy.operationView}</div><h1>{copy.pageTitle}</h1><p>{updated?t('lastUpdate',{time:updated.toLocaleTimeString(localeTags[uiLocale])}):copy.waitingData} · {role}</p></div><button disabled={role==='observer'} onClick={()=>setShowForm(!showForm)}>{copy.newReport}</button></div>
      <div className="stats">
        <div><span>{copy.filteredCases}</span><strong>{total.toString().padStart(2,'0')}</strong><small>{t('firstCases',{count:cases.length})}</small></div>
        <div className="critical"><span>{copy.criticalPriority}</span><strong>{stats.critical.toString().padStart(2,'0')}</strong><small>{copy.visibleAi}</small></div>
        <div><span>{copy.humanReview}</span><strong>{stats.review.toString().padStart(2,'0')}</strong><small>{copy.pendingVisible}</small></div>
        <div><span>{copy.awaitingLocation}</span><strong>{stats.unlocated.toString().padStart(2,'0')}</strong><small>{copy.hiddenFromMap}</small></div>
      </div>
      {showForm&&<form className="report-form" onSubmit={submit}><div><h2>{copy.reportTitle}</h2><p>{copy.reportRetryHelp}</p></div><label>{copy.originalMessage}<textarea value={text} disabled={!!pending.current} required maxLength={8000} onChange={e=>setText(e.target.value)}/></label><label>{copy.address}<input value={address} disabled={!!pending.current} onChange={e=>setAddress(e.target.value)} maxLength={1000}/></label><label>{copy.language}<select value={reportLanguage} disabled={!!pending.current} onChange={e=>setReportLanguage(e.target.value)}><option value="tr">Türkçe</option><option value="el">Ελληνικά</option><option value="en">English</option></select></label><button disabled={busy}>{busy?copy.sending:pending.current?copy.resend:copy.sendReport}</button></form>}
      <div className="filters">
        <label>{copy.priority}<select value={urgency} onChange={e=>setUrgency(e.target.value)}><option value="">{copy.all}</option>{Object.entries(names.urgency).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label>
        <label>{copy.verification}<select value={verification} onChange={e=>setVerification(e.target.value)}><option value="">{copy.all}</option><option value="UNVERIFIED">{copy.unverified}</option><option value="VERIFIED">{copy.verified}</option><option value="REJECTED">{copy.rejected}</option></select></label>
        <label>{copy.language}<select value={language} onChange={e=>setLanguage(e.target.value)}><option value="">TR / EL / EN</option><option value="tr">Türkçe</option><option value="el">Ελληνικά</option><option value="en">English</option></select></label>
        <label>{copy.disaster}<select value={incident} onChange={e=>setIncident(e.target.value)}><option value="">{copy.all}</option><option value="earthquake">{copy.earthquake}</option><option value="flood">{copy.flood}</option><option value="wildfire">{copy.wildfire}</option><option value="unknown">{copy.unknown}</option></select></label>
        <label>{copy.status}<select value={status} onChange={e=>setStatus(e.target.value)}><option value="">{copy.all}</option>{Object.entries(names.status).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label>
        <label>{copy.team}<select value={teamFilter} onChange={e=>setTeamFilter(e.target.value)}><option value="">{copy.all}</option>{teams.map(team=><option value={team.id} key={team.id}>{team.name}</option>)}</select></label>
        <label>{copy.timeRange}<select value={timeRange} onChange={e=>setTimeRange(e.target.value)}><option value="">{copy.anyTime}</option><option value="1">{copy.lastHour}</option><option value="6">{copy.lastSixHours}</option><option value="24">{copy.lastDay}</option><option value="168">{copy.lastWeek}</option></select></label>
        <label>{copy.region}<input placeholder={copy.exactRegion} value={region} onChange={e=>setRegion(e.target.value)}/></label>
      </div>
      <div className="board">
        <section className="case-list"><div className="section-label"><h2>{copy.queue}</h2><span>{t('showing',{count:cases.length})}</span></div>{cases.length===0?<div className="empty">{copy.noCases}<br/><small>{copy.addReportHint}</small></div>:cases.map(c=><button key={c.id} className={'case-card '+(detail?.id===c.id?'selected':'')} onClick={()=>selectCase(c.id)}><div className="case-top"><span className={'badge '+c.urgency_level}>{names.urgency[c.urgency_level]||c.urgency_level}</span><span>#{c.id.slice(0,8)}</span></div><h3>{c.needs.map(n=>names.needs[n]||n).join(' · ')||copy.firstReview}</h3><p>{c.region||copy.regionUnknown}</p><div className="case-meta"><span>{t('reports',{count:c.report_count})}</span><span>{c.verification_status==='VERIFIED'?'✓ '+copy.verified:copy.reviewNeeded}</span></div></button>)}</section>
        <section className="map-section"><Suspense fallback={<div className="empty" role="status">{copy.mapLoading}</div>}><CoordinationMap cases={cases} onSelect={selectCase} token={token} copy={copy} locale={uiLocale}/></Suspense><div className="map-footer"><span>{copy.originalPreserved}</span><span>{copy.humanDecides}</span></div></section>
      </div>
      {detail&&<CasePanel key={detail.id+':'+detail.version} detail={detail} cases={cases} token={token} teams={teams} allowed={allowed} copy={copy} locale={uiLocale} onClose={()=>{setDetail(null);selected.current=null;}} onChange={async(id?:string)=>{await refresh();await selectCase(id??detail.id);}} onError={fail}/>} 
    </main>}
    {error&&<div className="toast error" role="alert"><strong>{copy.operationFailed}</strong><span>{error}</span><button onClick={()=>setError('')} aria-label={copy.closeError}>×</button></div>}
    {notice&&<div className="toast" role="status"><span>{notice}</span><button onClick={()=>setNotice('')} aria-label={copy.closeNotice}>×</button></div>}
    <footer>Komşu / FıraTech <span>{copy.footer}</span></footer>
  </>;
}

function CasePanel({detail,cases,token,teams,allowed,copy,locale,onClose,onChange,onError}:{detail:Detail;cases:Case[];token:string;teams:Team[];allowed:boolean;copy:Catalogue;locale:UiLocale;onClose:()=>void;onChange:(id?:string)=>Promise<void>;onError:(e:unknown)=>void}){
  const names=labels(copy), t=(key:keyof Catalogue,values?:Record<string,string|number>)=>formatText(copy[key],values);
  const [lat,setLat]=useState(detail.location.lat?.toString()||''),[lon,setLon]=useState(detail.location.lon?.toString()||''),[reason,setReason]=useState(''),[urgency,setUrgency]=useState(detail.urgency_level),[team,setTeam]=useState(teams[0]?.id||''),[busy,setBusy]=useState(false),[language,setLanguage]=useState<UiLocale>(locale);
  async function action(kind:'review'|'dispatch'){
    setBusy(true);
    try{
      const body=kind==='review'?{expected_version:detail.version,verification_status:'VERIFIED',urgency_level:urgency,location:coordinatePair(lat,lon,{required:copy.coordinatesRequired,invalid:copy.invalidCoordinates}),confirm_location:true,reason}:{expected_version:detail.version,team_id:team};
      await request(token,`/cases/${detail.id}/${kind}`,body);await onChange();
    }catch(e){onError(e);}finally{setBusy(false);}
  }
  return <aside className="detail" aria-label={copy.caseDetails}>
    <div className="detail-head"><div><div className="eyebrow">#{detail.id.slice(0,8)}</div><h2>{names.status[detail.status]} · {names.urgency[detail.urgency_level]}</h2></div><button className="quiet" onClick={onClose} aria-label={copy.closeDetails}>✕</button></div>
    <div className="review-note">{detail.location_status==='CONFIRMED'?copy.locationConfirmed:copy.locationUnconfirmed}<small>{t('aiConfidence',{value:Math.round(detail.ai_confidence*100)})}</small></div>
    <label>{copy.translationLanguage}<select value={language} onChange={e=>setLanguage(e.target.value as UiLocale)}><option value="tr">Türkçe</option><option value="el">Ελληνικά</option><option value="en">English</option></select></label>
    {detail.reports.map(r=><article className="original" key={r.id}><div className="eyebrow">{copy.originalLabel} · {r.original_language.toUpperCase()} · {r.source}</div><p lang={r.original_language}>{r.original_text}</p>{r.address_raw&&<small>{t('addressDescription',{value:r.address_raw})}</small>}<TranslationBlock report={r} language={language} copy={copy}/><small>{t('processing',{status:r.processing_status,version:r.analysis.pipeline_version||copy.pending})}</small></article>)}
    <LocationCandidates reports={detail.reports} editable={allowed&&detail.status==='OPEN'} onChoose={(a,b)=>{setLat(String(a));setLon(String(b));}} copy={copy}/>
    {allowed&&detail.status==='OPEN'&&<div className="human-actions"><h3>{copy.coordinatorReview}</h3><p>{copy.verifyLocationHelp}</p><div className="coordinate-inputs"><label>{copy.latitude}<input value={lat} onChange={e=>setLat(e.target.value)} inputMode="decimal"/></label><label>{copy.longitude}<input value={lon} onChange={e=>setLon(e.target.value)} inputMode="decimal"/></label></div><label>{copy.priority}<select value={urgency} onChange={e=>setUrgency(e.target.value)}>{Object.entries(names.urgency).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label><label>{copy.reviewReason}<textarea value={reason} onChange={e=>setReason(e.target.value)} maxLength={500}/></label><button disabled={busy||reason.trim().length<3} onClick={()=>action('review')}>{copy.verifyCase}</button><hr/><label>{copy.dispatchTeam}<select value={team} onChange={e=>setTeam(e.target.value)}>{teams.map(item=><option value={item.id} key={item.id}>{item.name}</option>)}</select></label><button className="dispatch" disabled={busy||!team||detail.verification_status!=='VERIFIED'||detail.location_status!=='CONFIRMED'} onClick={()=>action('dispatch')}>{copy.dispatch}</button></div>}
    {detail.merged_into_id&&<button onClick={()=>onChange(detail.merged_into_id!)}>{copy.openMerged}</button>}
    {allowed&&detail.status==='OPEN'&&<RegroupPanel detail={detail} cases={cases} token={token} copy={copy} onChange={onChange} onError={onError}/>} 
  </aside>;
}

function TranslationBlock({report,language,copy}:{report:Report;language:string;copy:Catalogue}){
  const t=(key:keyof Catalogue,values?:Record<string,string|number>)=>formatText(copy[key],values);
  if(language===report.original_language)return <div className="translation"><strong>{copy.originalLanguage}</strong>{copy.useOriginal}</div>;
  const value=report.analysis.translated_text?.[language],meta=report.analysis.translation_provenance?.[language];
  if(!value)return <div className="translation">{copy.noTranslation}</div>;
  const route=(meta?.route||[report.original_language,language]).join('→').toUpperCase();
  return <div className="translation"><strong>{t('aiTranslation',{route})}</strong>{value}<small>{meta?.pivoted?copy.pivotWarning:''}{copy.verifyTranslation}{meta?.warnings?.length?t('automaticWarning',{warnings:meta.warnings.join(', ')}):''}</small></div>;
}
