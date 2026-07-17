from kraken_read_parser.database import validate_kraken_database
import pytest

def test_database_validation_and_optional_taxonomy_warning(tmp_path):
 d=tmp_path/'db';d.mkdir()
 for n in ('hash.k2d','opts.k2d','taxo.k2d'): (d/n).write_text('x')
 result=validate_kraken_database(d)
 assert result['core_files']['hash.k2d']['size_bytes']==1
 assert len(result['warnings'])==2

def test_database_missing_core_fails(tmp_path):
 with pytest.raises(FileNotFoundError): validate_kraken_database(tmp_path)
