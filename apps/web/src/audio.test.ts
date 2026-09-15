import {afterEach,describe,expect,it,vi} from 'vitest';
import {AudioInputError,encodePcmWav,fileAsPcmWav,validatePcmWav} from './audio';
import {uploadAudio} from './api';

afterEach(()=>vi.unstubAllGlobals());

describe('bounded PCM WAV input',()=>{
  const tone=(rate=48_000,seconds=0.25)=>Float32Array.from({length:rate*seconds},(_,index)=>Math.sin(2*Math.PI*440*index/rate)*0.25);
  it('encodes browser samples as canonical 16 kHz mono PCM',async()=>{
    const blob=encodePcmWav(tone(),48_000),metadata=validatePcmWav(await blob.arrayBuffer());
    expect(blob.type).toBe('audio/wav');expect(metadata.durationMs).toBe(250);expect(metadata.byteCount).toBe(8044);
  });
  it('rejects silence, malformed data, excessive duration and wrong MIME',async()=>{
    expect(()=>encodePcmWav(new Float32Array(48_000),48_000)).toThrow(AudioInputError);
    expect(()=>validatePcmWav(new ArrayBuffer(44))).toThrow(AudioInputError);
    expect(()=>encodePcmWav(tone(48_000,31),48_000)).not.toThrow();
    const valid=encodePcmWav(tone(),48_000);
    await expect(fileAsPcmWav(new File([valid],'voice.mp3',{type:'audio/mpeg'}))).rejects.toThrow(AudioInputError);
  });
  it.each([401,403,409])('keeps upload HTTP %s explicit for safe retry handling',async status=>{
    vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({detail:`HTTP_${status}`}),{status,headers:{'Content-Type':'application/json'}})));
    await expect(uploadAudio('test-token','report-id',new Blob(['wav'],{type:'audio/wav'}))).rejects.toMatchObject({status});
  });
});
