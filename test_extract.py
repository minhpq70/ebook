import asyncio
import json
from api.services.metadata_extractor import extract_metadata_from_pdf
from PyPDF2 import PdfWriter

# Create a dummy PDF bytes containing some valid text
writer = PdfWriter()
writer.add_blank_page(width=72, height=72)
# Since writing valid text into PyPDF2 is hard, I'll just use the raw function locally.
# Wait, let's just make a mock text for OpenAI to test.
