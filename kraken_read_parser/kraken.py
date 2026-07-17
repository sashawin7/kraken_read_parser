"""Kraken2 execution, validation, report summaries, and provenance."""
from __future__ import annotations
import json,subprocess,time
from dataclasses import dataclass,asdict
from datetime import datetime,timezone
from pathlib import Path
from .metadata import base_metadata,file_identity,run_metadata_schema,write_metadata
from .parser import parse_kraken2_file
from .report import parse_report,report_format,derive_standard_report,ReportParseError
from .database import validate_kraken_database,capture_version
from .schemas import KRAKEN_SUMMARY_SCHEMA
from .validation import *
@dataclass(frozen=True)
class KrakenOutputs:
 output_tsv:Path; report_tsv:Path; stderr_log:Path; metadata_json:Path; summary_json:Path; top_taxa_tsv:Path; minimizer_report_tsv:Path|None=None
def planned_outputs(outdir:Path,sample_id:str,report_minimizer_data:bool=False)->KrakenOutputs:
 base=outdir/f'{sample_id}.kraken2'
 return KrakenOutputs(outdir/f'{sample_id}.kraken2.tsv',outdir/f'{sample_id}.kraken2.report.tsv',outdir/f'{sample_id}.kraken2.stderr.log',outdir/f'{sample_id}.run_metadata.json',outdir/f'{sample_id}.kraken2.summary.json',outdir/f'{sample_id}.kraken2.top_taxa.tsv',outdir/f'{sample_id}.kraken2.report.minimizer.tsv' if report_minimizer_data else None)
def build_kraken2_command(*,kraken2_bin:str,db:Path,threads:int,outputs:KrakenOutputs,r1:Path,r2:Path,memory_mapping=False,report_minimizer_data=False)->list[str]:
 c=[kraken2_bin,'--paired','--db',str(db),'--threads',str(threads),'--output',str(outputs.output_tsv),'--report',str(outputs.minimizer_report_tsv or outputs.report_tsv)]
 if memory_mapping:c.append('--memory-mapping')
 if report_minimizer_data:c.append('--report-minimizer-data')
 return c+[str(r1),str(r2)]
def sanity_check_output(path:Path,*,rows=1000,require_paired=True):
 checked=paired=0
 for r in parse_kraken2_file(path,strict=True):
  checked+=1; paired+=r.has_mate_separator
  if checked>=rows:break
 if not checked:raise ValueError(f'Kraken2 output is empty: {path}')
 if require_paired and paired<checked:raise ValueError(f'Kraken2 output does not look like paired output: {paired}/{checked} checked rows contain |:|')
 return checked,paired
def _summary(rows,sample,expected,raw,report,limit):
 un=[r for r in rows if r.taxid==0 and r.name.lower()=='unclassified']
 root=[r for r in rows if r.taxid==1 and r.name.lower() in {'root','root '}]
 if len(un)!=1 or len(root)!=1:raise ReportParseError('report must contain exactly one unclassified and one root accounting row')
 total=root[0].clade_fragments; unc=un[0].clade_fragments; classified=total-unc
 if classified<0:raise ReportParseError('unclassified fragments exceed root total')
 fmt='minimizer_enriched' if rows[0].minimizers is not None else 'standard'
 candidates=[r for r in rows if r.taxid not in (0,1)]
 direct=sorted(candidates,key=lambda r:(-r.direct_fragments,r.taxid,r.name))[:limit]; clade=sorted(candidates,key=lambda r:(-r.clade_fragments,r.taxid,r.name))[:limit]
 return {**KRAKEN_SUMMARY_SCHEMA,'package_version':base_metadata()['package_version'],'sample_id':sample,'report_path':str(report),'report_format':fmt,'raw_kraken_output_path':str(raw),'expected_pairs':expected,'classified_pairs':classified,'unclassified_pairs':unc,'total_reported_pairs':total,'classification_percentage':(100*classified/total if total else None),'unclassified_percentage':(100*unc/total if total else None),'report_rows':len(rows),'top_direct_assignment_taxa':[asdict(x) for x in direct],'top_clade_assignment_taxa':[asdict(x) for x in clade],'warnings':[],'generated_at':datetime.now(timezone.utc).isoformat()},direct,clade
def _write_top(path,sample,direct,clade):
 with path.open('w',encoding='utf-8') as f:
  f.write('sample_id\tsummary_type\trank_code\ttaxid\tname\tdirect_fragments\tclade_fragments\tpercent\tminimizers\tdistinct_minimizers\tdistinct_minimizer_fraction\n')
  for typ,rows in [('top_direct',direct),('top_clade',clade)]:
   for r in rows:
    frac='' if r.minimizers in (None,0) or r.distinct_minimizers is None else str(r.distinct_minimizers/r.minimizers)
    f.write('\t'.join(map(str,[sample,typ,r.rank_code,r.taxid,r.name,r.direct_fragments,r.clade_fragments,r.percent,'' if r.minimizers is None else r.minimizers,'' if r.distinct_minimizers is None else r.distinct_minimizers,frac]))+'\n')
def run_kraken2(*,r1:Path,r2:Path,db:Path,sample_id:str,outdir:Path,threads:int,kraken2_bin='kraken2',overwrite=False,check_output_lines=1000,dry_run=False,memory_mapping=False,report_minimizer_data=False,expected_pairs=None,top_taxa_limit=100)->dict:
 validate_sample_id(sample_id); validate_positive_integer(threads,'threads');validate_positive_integer(check_output_lines,'check_output_lines');validate_positive_integer(top_taxa_limit,'top_taxa_limit');
 if expected_pairs is not None:validate_positive_integer(expected_pairs,'expected_pairs')
 r1=r1.resolve();r2=r2.resolve();db=db.resolve();outdir=outdir.resolve();require_regular_nonempty_file(r1,'R1 FASTQ');require_regular_nonempty_file(r2,'R2 FASTQ');ensure_outdir(outdir); database=validate_kraken_database(db); outputs=planned_outputs(outdir,sample_id,report_minimizer_data); protect_outputs([p for p in outputs.__dict__.values() if p],overwrite=overwrite);require_executable(kraken2_bin)
 command=build_kraken2_command(kraken2_bin=kraken2_bin,db=db,threads=threads,outputs=outputs,r1=r1,r2=r2,memory_mapping=memory_mapping,report_minimizer_data=report_minimizer_data); start=datetime.now(timezone.utc)
 m=base_metadata()|run_metadata_schema()|{'sample_id':sample_id,'r1':str(r1),'r2':str(r2),'kraken2_db':str(db),'outdir':str(outdir),'inputs':{'r1':file_identity(r1),'r2':file_identity(r2)},'database_provenance':database,'threads':threads,'memory_mapping':memory_mapping,'report_minimizer_data':report_minimizer_data,'top_taxa_limit':top_taxa_limit,'expected_pairs':expected_pairs,'kraken2_executable':kraken2_bin,'kraken2_version':capture_version(kraken2_bin),'command':command,'start_time':start.isoformat(),'output_files':{k:str(v) if v else None for k,v in outputs.__dict__.items()}}
 if dry_run:return m|{'dry_run':True,'run_status':'dry_run','end_time':start.isoformat(),'elapsed_seconds':0.0,'exit_code':None}
 m.update(dry_run=False,run_status='running',exit_code=None);write_metadata(outputs.metadata_json,m);t=time.monotonic()
 with outputs.stderr_log.open('w',encoding='utf-8') as e: p=subprocess.run(command,stdout=subprocess.DEVNULL,stderr=e,text=True)
 m.update(end_time=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-t,exit_code=p.returncode)
 if p.returncode:
  m.update(run_status='kraken_failed',error={'message':f'Kraken2 failed with exit code {p.returncode}'},output_identities={k:file_identity(v) for k,v in outputs.__dict__.items() if v and v.exists()});write_metadata(outputs.metadata_json,m);raise RuntimeError(m['error']['message']+f'; see {outputs.stderr_log}')
 try:
  for x,label in ((outputs.output_tsv,'Kraken2 output'),((outputs.minimizer_report_tsv or outputs.report_tsv),'Kraken2 report')):require_regular_nonempty_file(x,label)
  checked,paired=sanity_check_output(outputs.output_tsv,rows=check_output_lines)
  source=outputs.minimizer_report_tsv or outputs.report_tsv
  if report_minimizer_data: derive_standard_report(source,outputs.report_tsv)
  rows=list(parse_report(source)); summary,direct,clade=_summary(rows,sample_id,expected_pairs,outputs.output_tsv,source,top_taxa_limit)
  summary['reconciliation']={'expected_pairs':expected_pairs,'reported_pairs':summary['total_reported_pairs'],'matched':expected_pairs is None or expected_pairs==summary['total_reported_pairs']}
  _write_top(outputs.top_taxa_tsv,sample_id,direct,clade); outputs.summary_json.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
  if not summary['reconciliation']['matched']:raise ValueError(f'Kraken2 exited successfully but reconciliation failed: expected {expected_pairs}, reported {summary["total_reported_pairs"]}; report {source}')
  m.update(run_status='completed',sanity_check_rows_requested=check_output_lines,sanity_check_rows_inspected=checked,paired_rows_found=paired,report_format=summary['report_format'],report_accounting={k:summary[k] for k in ('classified_pairs','unclassified_pairs','total_reported_pairs')},reconciliation=summary['reconciliation'])
 except Exception as exc:
  m.update(run_status='post_run_validation_failed',error={'type':type(exc).__name__,'message':str(exc)}) ;m['output_identities']={k:file_identity(v) for k,v in outputs.__dict__.items() if v and v.exists()};write_metadata(outputs.metadata_json,m);raise
 m['output_identities']={k:file_identity(v) for k,v in outputs.__dict__.items() if v and v.exists()};write_metadata(outputs.metadata_json,m);return m
