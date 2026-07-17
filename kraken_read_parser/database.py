"""Kraken2 database preflight and explicit inspection."""
from __future__ import annotations
import subprocess,time
from datetime import datetime,timezone
from pathlib import Path
from .metadata import file_identity, write_metadata
from .validation import require_directory,require_regular_nonempty_file,ensure_outdir,protect_outputs
CORE=('hash.k2d','opts.k2d','taxo.k2d')
def validate_kraken_database(db:Path)->dict:
 db=db.resolve(); require_directory(db,'Kraken2 database'); warnings=[]; core={}
 for name in CORE:
  p=db/name; require_regular_nonempty_file(p,f'Kraken2 database core file {name}'); core[name]=file_identity(p)
 taxonomy={}
 for name in ('nodes.dmp','names.dmp'):
  candidates=(db/'taxonomy'/name,db/name); found=next((p for p in candidates if p.is_file()),None)
  taxonomy[name]=file_identity(found) if found else {'path':None,'exists':False}
  if not found: warnings.append(f'Optional taxonomy dump missing: {name}; raw classification remains available.')
 return {'database_path':str(db),'core_files':core,'taxonomy_files':taxonomy,'warnings':warnings}
def capture_version(executable:str)->dict:
 try:
  p=subprocess.run([executable,'--version'],capture_output=True,text=True,timeout=15)
  return {'argv':[executable,'--version'],'exit_code':p.returncode,'output':(p.stdout or p.stderr).strip() or None,'stderr':p.stderr.strip() or None}
 except Exception as e:return {'argv':[executable,'--version'],'exit_code':None,'output':None,'stderr':str(e)}
def inspect_database(db:Path,outdir:Path,kraken2_bin='kraken2',inspect_bin='kraken2-inspect',overwrite=False,target_lineages=())->dict:
 ensure_outdir(outdir); raw=outdir/'database.inspect.tsv'; prov=outdir/'database.provenance.json'; targets=outdir/'database.target_lineages.tsv'; protect_outputs((raw,prov,targets),overwrite=overwrite)
 result=validate_kraken_database(db); start=datetime.now(timezone.utc); t=time.monotonic(); argv=[inspect_bin,'--db',str(db.resolve())]
 try:
  p=subprocess.run(argv,capture_output=True,text=True,timeout=None)
 except Exception as e: p=None; err=str(e)
 if p is None or p.returncode != 0:
  result.update({'inspection':{'argv':argv,'exit_code':None if p is None else p.returncode,'error':err if p is None else p.stderr,'start_time':start.isoformat(),'elapsed_seconds':time.monotonic()-t}}); write_metadata(prov,result); raise RuntimeError(f'kraken2-inspect failed: {result["inspection"]["error"]}')
 raw.write_text(p.stdout,encoding='utf-8'); result.update({'schema_name':'kraken_read_parser.database_provenance','schema_version':1,'kraken2_version':capture_version(kraken2_bin),'kraken2_inspect_version':capture_version(inspect_bin),'inspection':{'argv':argv,'exit_code':p.returncode,'stderr':p.stderr,'start_time':start.isoformat(),'end_time':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-t,'raw_output_path':str(raw)}}); write_metadata(prov,result)
 # Conservative exact-name match against final report name field; inspect formats vary.
 rows=[]
 for requested in target_lineages:
  matches=[]
  for line in p.stdout.splitlines():
   cols=line.split('\t')
   if cols and cols[-1].strip()==requested: matches.append(cols)
  note='absent from inspect output' if not matches else ('ambiguous exact matches' if len(matches)>1 else 'best-effort inspect-output match; database representation only')
  rows.append('\t'.join([requested,str(len(matches)==1).lower(),'','','','','',note] if len(matches)!=1 else [requested,'true','','', '', '', '',note]))
 targets.write_text('requested_name\tmatched\tmatched_taxid\tmatched_name\trank_code\tdirect_database_minimizers\tclade_database_minimizers\tnotes\n'+'\n'.join(rows)+'\n',encoding='utf-8')
 return result
