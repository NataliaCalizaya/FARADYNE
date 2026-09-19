import pytest
import fitz
from app.services.pdf_interpreter_service import PDFInterpreterService

def create_sample_vector_pdf() -> bytes:
    """Creates an in-memory PDF containing vector drawing (rectangle) and text cota (+7.90)."""
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    
    # Draw a vector rectangle
    shape = page.new_shape()
    shape.draw_rect(fitz.Rect(10, 10, 100, 100))
    shape.finish(color=(1, 0, 0), fill=None, width=1.5)
    shape.commit()
    
    # Insert height text cota
    page.insert_text(fitz.Point(30, 50), "+7.90", fontsize=12)
    
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes

def create_non_vector_pdf() -> bytes:
    """Creates an in-memory PDF without any vector drawings (text only)."""
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    page.insert_text(fitz.Point(30, 50), "Plano sin vectores", fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes

def test_validate_and_read_pdf_valid():
    pdf_bytes = create_sample_vector_pdf()
    doc = PDFInterpreterService.validate_and_read_pdf(pdf_bytes, "test.pdf")
    assert doc is not None
    doc.close()

def test_validate_and_read_pdf_invalid_no_vectors():
    pdf_bytes = create_non_vector_pdf()
    with pytest.raises(ValueError, match="El PDF no contiene geometría vectorial interpretable."):
        PDFInterpreterService.validate_and_read_pdf(pdf_bytes, "test_no_vectors.pdf")

def test_interpret_pdf_data():
    pdf_bytes = create_sample_vector_pdf()
    doc = PDFInterpreterService.validate_and_read_pdf(pdf_bytes, "test.pdf")
    result = PDFInterpreterService.interpret_pdf_data(doc)
    doc.close()

    assert "poligonos" in result
    assert "lineas" in result
    assert "capas" in result
    assert "cotas_altura" in result
    assert "bounding_box" in result

    # Check cotas_altura extraction
    cotas = result["cotas_altura"]
    assert len(cotas) == 1
    assert cotas[0]["valor"] == 7.9
    assert cotas[0]["texto"] == "+7.90"

    # Check parsed vectors
    assert len(result["poligonos"]) > 0 or len(result["lineas"]) > 0
