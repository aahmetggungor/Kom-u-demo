import {describe,expect,it} from 'vitest';
import {catalogues,formatText,type UiLocale} from './i18n';

const locales:UiLocale[]=['tr','el','en'];
const placeholders=(value:string)=>[...value.matchAll(/\{(\w+)\}/g)].map(match=>match[1]).sort();

describe('dashboard localisation',()=>{
  it('keeps the same complete key set in every catalogue',()=>{
    const expected=Object.keys(catalogues.tr).sort();
    for(const locale of locales)expect(Object.keys(catalogues[locale]).sort()).toEqual(expected);
  });

  it('keeps interpolation placeholders aligned across languages',()=>{
    for(const key of Object.keys(catalogues.tr) as (keyof typeof catalogues.tr)[]){
      const expected=placeholders(catalogues.tr[key]);
      for(const locale of locales)expect(placeholders(catalogues[locale][key]),`${locale}.${key}`).toEqual(expected);
    }
  });

  it('does not silently fall back to Turkish copy',()=>{
    const keys=Object.keys(catalogues.tr) as (keyof typeof catalogues.tr)[];
    for(const locale of ['el','en'] as const){
      expect(keys.filter(key=>catalogues[locale][key]===catalogues.tr[key]),locale).toEqual([]);
    }
  });

  it('formats values without leaving unresolved placeholders',()=>{
    expect(formatText(catalogues.en.similarityLine,{score:'0.812',distance:'42 m',minutes:3})).toBe('Cosine similarity: 0.812 · Distance: 42 m · Time difference: 3 min');
    expect(formatText(catalogues.el.reports,{count:4})).toBe('4 αναφορές');
  });
});
