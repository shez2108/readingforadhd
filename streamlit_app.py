import streamlit as st
import pypdf
import re
import os
import anthropic

st.title("ADHD Reader")
st.write(
    "Input a PDF and let the app chunk it up!"
)


def clean_text(text):
    """Clean and format extracted text."""
    # Remove multiple spaces and newlines
    text = re.sub(r'\s+', ' ', text)
    # Split into paragraphs on period followed by space
    paragraphs = re.split(r'(?<=\.)\s+', text)
    return [p.strip() for p in paragraphs if p.strip()]

def chunk_text(text, words_per_chunk=8):
    """Split text into chunks of approximately n words."""
    words = text.split()
    chunks = []
    current_chunk = []
    
    for word in words:
        current_chunk.append(word)
        # Create a new chunk after reaching word limit or finding sentence end
        if len(current_chunk) >= words_per_chunk or word.endswith(('.', '?', '!')):
            chunks.append(' '.join(current_chunk))
            current_chunk = []
    
    # Add any remaining words
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks


def pdf_to_text(file, text_path=None):
    reader = pypdf.PdfReader(file)
    all_text = []
    # Process each page and extract the text
    for page_num in range(len(reader.pages)):
        # Extract text from page
        page = reader.pages[page_num]
        text = page.extract_text()

        # Clean and format text
        paragraphs = clean_text(text)
        
        # Chunk each paragraph into 8 words per chunk
        for para in paragraphs:
            chunks = chunk_text(para, words_per_chunk=8)
            all_text.extend(chunks)
            all_text.append('')  # Add extra space between paragraphs

    return all_text

name = st.text_input("Enter the name of the book")
if name:
    name = name.replace(' ', '_').lower()
    document = st.file_uploader("Import a PDF", type="pdf")
    convert_button = st.button("Convert!")
    if convert_button:
        st.write("Button Clicked!")
        text_chunks = pdf_to_text(document)
        # Create the full text content
        full_text = '\n\n\n'.join(text_chunks)
        st.download_button(
            label="Download Text File",
            data = full_text,
            file_name = f'{name}.txt',
            mime="text/plain"
        )
