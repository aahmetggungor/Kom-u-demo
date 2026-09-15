import {describe,it,expect} from 'vitest';
import {coordinatePair} from './api';

describe('human coordinate entry',()=>{
  it('rejects blanks, non-finite and out-of-range coordinates',()=>{
    for(const values of [['','36'],['90.1','0'],['0','181'],['NaN','0'],['0','Infinity']]) expect(()=>coordinatePair(values[0],values[1])).toThrow();
  });
  it('preserves valid zero coordinates',()=>expect(coordinatePair('0','0')).toEqual({lat:0,lon:0}));
});
