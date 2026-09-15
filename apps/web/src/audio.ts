export const MAX_AUDIO_BYTES=2_000_000,MAX_AUDIO_SECONDS=30,SAMPLE_RATE=16_000;

export class AudioInputError extends Error {
  constructor(public code:'UNSUPPORTED'|'PERMISSION_DENIED'|'INVALID',message:string){super(message);}
}

function uint16(view:DataView,offset:number){return view.getUint16(offset,true);}
function uint32(view:DataView,offset:number){return view.getUint32(offset,true);}

export function validatePcmWav(bytes:ArrayBuffer):{durationMs:number;byteCount:number}{
  if(bytes.byteLength<44||bytes.byteLength>MAX_AUDIO_BYTES)throw new AudioInputError('INVALID','Audio size is outside bounds');
  const view=new DataView(bytes),ascii=(offset:number,length:number)=>String.fromCharCode(...new Uint8Array(bytes,offset,length));
  if(ascii(0,4)!=='RIFF'||ascii(8,4)!=='WAVE'||ascii(12,4)!=='fmt '||ascii(36,4)!=='data')throw new AudioInputError('INVALID','Only canonical PCM WAV is accepted');
  if(uint16(view,20)!==1||uint16(view,22)!==1||uint32(view,24)!==SAMPLE_RATE||uint16(view,34)!==16)throw new AudioInputError('INVALID','WAV must be mono 16-bit PCM at 16 kHz');
  const pcmBytes=uint32(view,40);
  if(pcmBytes!==bytes.byteLength-44||pcmBytes%2!==0)throw new AudioInputError('INVALID','WAV data length is invalid');
  const durationMs=Math.round(pcmBytes*1000/(SAMPLE_RATE*2));
  if(durationMs<200||durationMs>MAX_AUDIO_SECONDS*1000)throw new AudioInputError('INVALID','Audio duration is outside bounds');
  let squares=0,peak=0;
  for(let offset=44;offset<bytes.byteLength;offset+=2){const sample=view.getInt16(offset,true);squares+=sample*sample;peak=Math.max(peak,Math.abs(sample));}
  const rms=Math.sqrt(squares/(pcmBytes/2))/32768;
  if(rms<0.003||peak/32768<0.01)throw new AudioInputError('INVALID','Audio is silent');
  return {durationMs,byteCount:bytes.byteLength};
}

export function encodePcmWav(samples:Float32Array,inputRate:number):Blob{
  if(!Number.isFinite(inputRate)||inputRate<SAMPLE_RATE||samples.length<inputRate*0.2)throw new AudioInputError('INVALID','Recording is too short');
  const outputLength=Math.min(SAMPLE_RATE*MAX_AUDIO_SECONDS,Math.floor(samples.length*SAMPLE_RATE/inputRate));
  const bytes=new ArrayBuffer(44+outputLength*2),view=new DataView(bytes);
  const text=(offset:number,value:string)=>[...value].forEach((char,index)=>view.setUint8(offset+index,char.charCodeAt(0)));
  text(0,'RIFF');view.setUint32(4,36+outputLength*2,true);text(8,'WAVE');text(12,'fmt ');view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,SAMPLE_RATE,true);view.setUint32(28,SAMPLE_RATE*2,true);view.setUint16(32,2,true);view.setUint16(34,16,true);text(36,'data');view.setUint32(40,outputLength*2,true);
  const ratio=inputRate/SAMPLE_RATE;
  for(let index=0;index<outputLength;index++){
    const start=Math.floor(index*ratio),end=Math.max(start+1,Math.floor((index+1)*ratio));let sum=0;
    for(let source=start;source<Math.min(end,samples.length);source++)sum+=samples[source];
    const value=Math.max(-1,Math.min(1,sum/(end-start)));
    view.setInt16(44+index*2,value<0?value*32768:value*32767,true);
  }
  validatePcmWav(bytes);
  return new Blob([bytes],{type:'audio/wav'});
}

export async function fileAsPcmWav(file:File):Promise<Blob>{
  if(!['audio/wav','audio/x-wav'].includes(file.type)||file.size>MAX_AUDIO_BYTES)throw new AudioInputError('INVALID','Select a bounded WAV file');
  const bytes=await file.arrayBuffer();validatePcmWav(bytes);return new Blob([bytes],{type:'audio/wav'});
}

export class BrowserPcmRecorder {
  private context?:AudioContext;private stream?:MediaStream;private source?:MediaStreamAudioSourceNode;private processor?:ScriptProcessorNode;private chunks:Float32Array[]=[];private samples=0;
  async start(){
    if(!navigator.mediaDevices?.getUserMedia||typeof AudioContext==='undefined')throw new AudioInputError('UNSUPPORTED','Browser recording is unavailable');
    try{this.stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true}});}
    catch(error){throw new AudioInputError((error as DOMException)?.name==='NotAllowedError'?'PERMISSION_DENIED':'UNSUPPORTED','Microphone access failed');}
    this.context=new AudioContext();this.source=this.context.createMediaStreamSource(this.stream);this.processor=this.context.createScriptProcessor(4096,1,1);this.chunks=[];this.samples=0;
    this.processor.onaudioprocess=event=>{const maximum=this.context!.sampleRate*MAX_AUDIO_SECONDS;if(this.samples>=maximum)return;const input=event.inputBuffer.getChannelData(0),copy=new Float32Array(input.slice(0,maximum-this.samples));this.chunks.push(copy);this.samples+=copy.length;};
    this.source.connect(this.processor);this.processor.connect(this.context.destination);
  }
  async stop(discard=false):Promise<Blob|null>{
    const rate=this.context?.sampleRate??0;this.processor?.disconnect();this.source?.disconnect();this.stream?.getTracks().forEach(track=>track.stop());await this.context?.close();
    const combined=new Float32Array(this.samples);let offset=0;for(const chunk of this.chunks){combined.set(chunk,offset);offset+=chunk.length;}
    this.context=undefined;this.stream=undefined;this.source=undefined;this.processor=undefined;this.chunks=[];this.samples=0;
    return discard?null:encodePcmWav(combined,rate);
  }
}
