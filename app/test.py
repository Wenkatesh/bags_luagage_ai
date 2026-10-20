
from app.chunking import split_text
from app.extractor import extract_page_chunks

sample_text = """
Example Corporate Gifts provides employee welcome kits and branded
promotional merchandise. Its catalogue includes customized backpacks
and laptop bags for corporate customers.

Contact: sales@example.com
Website: https://example.com
"""

chunks = split_text(sample_text)

results = extract_page_chunks(
    chunks=chunks,
    domain="example.com",
    source_url="https://example.com/",
    company_title="Example Corporate Gifts",
)

for result in results:
    print(result)
