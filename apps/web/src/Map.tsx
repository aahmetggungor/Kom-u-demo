import { useEffect, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import { type GeoJSONSource } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import {request,type Case,type MapLayer} from './api';
import {formatText,type Catalogue,type UiLocale} from './i18n';

maplibregl.setWorkerUrl(workerUrl);
const localeTags:Record<UiLocale,string>={tr:'tr-TR',el:'el-GR',en:'en-GB'};

export function CoordinationMap({cases,onSelect,token,copy,locale}:{cases:Case[];onSelect:(id:string)=>void;token:string;copy:Catalogue;locale:UiLocale}) {
  const element=useRef<HTMLDivElement>(null),map=useRef<maplibregl.Map|null>(null),select=useRef(onSelect);select.current=onSelect;
  const [ready,setReady]=useState(false),[error,setError]=useState(''),[visiblePoints,setVisiblePoints]=useState(0);
  const [layers,setLayers]=useState<MapLayer[]>([]),[enabled,setEnabled]=useState<string[]>([]),[layerError,setLayerError]=useState('');
  useEffect(()=>{
    const controller=new AbortController();
    request<MapLayer[]>(token,'/map/layers',undefined,controller.signal).then(setLayers).catch(()=>{if(!controller.signal.aborted)setLayerError(copy.layerFailed);});
    return()=>controller.abort();
  },[token,copy.layerFailed]);
  useEffect(()=>{
    if(!element.current)return;
    setReady(false);let instance:maplibregl.Map;let resize:ResizeObserver|undefined;
    try{
      instance=new maplibregl.Map({container:element.current,center:[27.4,38.0],zoom:6,style:{version:8,sources:{},layers:[{id:'background',type:'background',paint:{'background-color':'#e5edec'}}]},attributionControl:false});
      map.current=instance;resize=new ResizeObserver(()=>instance.resize());resize.observe(element.current);instance.addControl(new maplibregl.NavigationControl(),'top-right');
      instance.on('load',()=>{instance.addSource('cases',{type:'geojson',data:{type:'FeatureCollection',features:[]}});instance.addLayer({id:'cases',type:'circle',source:'cases',paint:{'circle-radius':10,'circle-color':['match',['get','urgency'],'CRITICAL','#b83e2f','HIGH','#bd791e','#285b68'],'circle-stroke-width':3,'circle-stroke-color':'#ffffff'}});instance.on('click','cases',e=>{const id=e.features?.[0]?.properties?.id;if(id)select.current(id);});setReady(true);});
      instance.on('error',()=>setError(copy.mapUnavailable));instance.on('idle',()=>{if(instance.getLayer('cases'))setVisiblePoints(instance.queryRenderedFeatures({layers:['cases']}).length);});
    }catch{setError(copy.mapStartFailed);}
    return()=>{resize?.disconnect();instance?.remove();map.current=null;};
  },[copy.mapStartFailed,copy.mapUnavailable]);
  useEffect(()=>{
    if(!ready||!map.current?.getSource('cases'))return;
    const located=cases.filter(c=>c.location.lat!==null&&c.location.lon!==null);
    (map.current.getSource('cases') as GeoJSONSource).setData({type:'FeatureCollection',features:located.map(c=>({type:'Feature',properties:{id:c.id,urgency:c.urgency_level},geometry:{type:'Point',coordinates:[c.location.lon!,c.location.lat!]}}))});
  },[cases,ready]);
  useEffect(()=>{
    const instance=map.current;if(!ready||!instance?.getSource('cases'))return;
    for(const layer of layers){
      const id='gis-'+layer.id,color=layer.kind==='closed_road'?'#a2342b':layer.kind==='hospital'?'#365cb2':layer.kind==='shelter'?'#7c4598':'#24734a';
      if(!instance.getSource(id)){instance.addSource(id,{type:'geojson',data:layer.geojson});instance.addLayer({id:id+'-line',type:'line',source:id,filter:['==',['geometry-type'],'LineString'],paint:{'line-color':color,'line-width':5}},'cases');instance.addLayer({id:id+'-point',type:'circle',source:id,filter:['==',['geometry-type'],'Point'],paint:{'circle-color':color,'circle-radius':7,'circle-stroke-color':'#fff','circle-stroke-width':2}},'cases');}
      for(const suffix of ['-line','-point'])instance.setLayoutProperty(id+suffix,'visibility',enabled.includes(layer.id)?'visible':'none');
    }
  },[layers,enabled,ready]);
  return <div className="map-shell"><div className="map" ref={element} aria-label={copy.mapAria}/><div className="map-note"><strong>{copy.locationWorkspace}</strong><span>{error||(ready?copy.noBaseMap:copy.mapEngineLoading)}</span></div><div className="gis-controls" aria-label={copy.institutionLayers}><strong>{copy.institutionLayers}</strong>{layerError?<small role="status">{layerError}</small>:layers.length===0?<small>{copy.noInstitutionData}</small>:layers.map(layer=><label key={layer.id}><span><input type="checkbox" checked={enabled.includes(layer.id)} onChange={e=>setEnabled(current=>e.target.checked?[...current,layer.id]:current.filter(id=>id!==layer.id))}/>{layer.name}</span><small>{formatText(copy.layerLoaded,{source:layer.provenance,time:new Date(layer.updated_at).toLocaleString(localeTags[locale])})}</small></label>)}</div><div className="map-legend"><span>{formatText(copy.visiblePoints,{count:visiblePoints})}</span><span>{copy.reportedLocation}</span></div></div>;
}
