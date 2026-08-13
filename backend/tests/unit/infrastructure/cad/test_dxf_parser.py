from infrastructure.cad.parsers.dxf.dxf_parser import DXFParser

def test_dxf_parser_supports_format():
    parser = DXFParser()
    assert parser.supports_format(".dxf") == True

def test_dxf_parser_rejects_unsupported_format():
    parser = DXFParser()
    assert parser.supports_format(".dwg") == False

def test_parse_returns_raw_cad_data_type():
    pass
