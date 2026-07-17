"""Run metadata helpers."""
from __future__ import annotations
import json,os,platform,sys,tempfile
from pathlib import Path
from typing import Any,Mapping
from . import __version__
from .schemas import RUN_METADATA_SCHEMA
def base_metadata()->dict[str,Any]: return {'package_version':__version__,'python_version':sys.version,'platform':platform.platform()}
def file_identity(path:Path)->dict[str,Any]:
 d={'path':str(path.resolve())}
 try:
  s=path.stat(); d.update(exists=True,regular_file=path.is_file(),readable=os.access(path,os.R_OK),size_bytes=s.st_size,mtime_ns=s.st_mtime_ns)
 except OSError as e:d.update(exists=False,error=str(e))
 return d
def run_metadata_schema()->dict[str,Any]: return dict(RUN_METADATA_SCHEMA)
def write_metadata(path:Path,metadata:Mapping[str,Any])->None:
 path.parent.mkdir(parents=True,exist_ok=True); fd,tmp=tempfile.mkstemp(prefix='.'+path.name+'.',dir=path.parent);
 try:
  with os.fdopen(fd,'w',encoding='utf-8') as f: json.dump(dict(metadata),f,indent=2,sort_keys=True); f.write('\n'); f.flush(); os.fsync(f.fileno())
  os.replace(tmp,path)
 finally:
  if os.path.exists(tmp): os.unlink(tmp)
