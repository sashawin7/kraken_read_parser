"""Streaming Kraken2 report parsing and compatibility conversion."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
@dataclass(frozen=True)
class KrakenReportRow:
 percent: float; clade_fragments:int; direct_fragments:int; rank_code:str; taxid:int; name:str; raw_name:str; minimizers:int|None=None; distinct_minimizers:int|None=None
class ReportParseError(ValueError): pass
def parse_report(path:Path)->Iterator[KrakenReportRow]:
    shape=None
    with path.open(encoding='utf-8') as f:
      for lineno,line in enumerate(f,1):
       if not line.strip(): continue
       fields=line.rstrip('\n').split('\t')
       if len(fields) not in (6,8): raise ReportParseError(f'{path}:{lineno}: expected 6 or 8 columns, got {len(fields)}')
       if shape is None: shape=len(fields)
       elif shape != len(fields): raise ReportParseError(f'{path}:{lineno}: inconsistent column count')
       try: percent=float(fields[0]); clade=int(fields[1]); direct=int(fields[2]); taxid=int(fields[4]);
       except ValueError as exc: raise ReportParseError(f'{path}:{lineno}: invalid numeric field: {exc}') from exc
       if percent<0 or clade<0 or direct<0: raise ReportParseError(f'{path}:{lineno}: negative report value')
       mins=distinct=None
       if shape==8:
        try: mins=int(fields[5]); distinct=int(fields[6])
        except ValueError as exc: raise ReportParseError(f'{path}:{lineno}: invalid minimizer field: {exc}') from exc
        if mins<0 or distinct<0: raise ReportParseError(f'{path}:{lineno}: negative minimizer value')
        raw=fields[7]
       else: raw=fields[5]
       yield KrakenReportRow(percent,clade,direct,fields[3],taxid,raw.strip(),raw,mins,distinct)
def report_format(path:Path)->str:
    for row in parse_report(path): return 'minimizer_enriched' if row.minimizers is not None else 'standard'
    raise ReportParseError(f'Kraken2 report is empty: {path}')
def derive_standard_report(source:Path,dest:Path)->None:
    with source.open(encoding='utf-8') as inp,dest.open('w',encoding='utf-8') as out:
      for n,line in enumerate(inp,1):
       if not line.strip(): out.write(line); continue
       f=line.rstrip('\n').split('\t')
       if len(f)!=8: raise ReportParseError(f'{source}:{n}: expected enriched 8-column report')
       out.write('\t'.join(f[:5]+[f[7]])+'\n')
