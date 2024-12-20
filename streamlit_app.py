import streamlit as st
import pypdf
import re
import os
import anthropic

st.title("ADHD Reader")
st.write(
    "Input a PDF and let the app chunk it up!"
)

st.write(
    """
    #### Do you have trouble reading eBooks from your Kindle?
    #### Do you find that your eyes can't help moving across the page?
    #### Or that the content you're reading goes in one ear then out the other?
    *Note: This is specifically built for handling PDFs. It divides the text into chunks and increases the space between those chunks, with the aim of making it easier to digest words on the page. 
    It also prints a test for you to make sure you're keeping sufficient track of the book's narrative. You must save the result and export it to your Kindle app.**
    """
)

# Near the top of your file, after imports
try:
    api_key = st.secrets["ANTHROPIC_API_KEY"]
    
    client = anthropic.Anthropic(
        api_key=api_key
    )
except Exception as e:
    st.error(f"Error setting up Anthropic client: {e}")
    st.stop()  # Stop execution if we can't set up the client

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

def format_claude_response(response):
    """Clean and format Claude's response for better display"""
    # Extract the text from the TextBlock
    if isinstance(response, list) and len(response) > 0:
        # Get the raw text from the TextBlock
        raw_text = response[0].text
        
        # Split into sections
        sections = raw_text.split("\n\n")
        
        # Remove any introductory text
        if "I'll create a test" in sections[0]:
            sections = sections[1:]
        
        # Join with double newlines for better spacing
        formatted_text = "\n\n".join(sections)
        
        # Remove extra quotes and escape characters
        formatted_text = formatted_text.replace("\\n", "\n").replace("\"", "")
        
        return formatted_text
    return "No response to format"
    
def create_test(text):
    message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=8192,
            messages=[
                {"role": "user", "content": f"Hello, Claude. Give me a test on the chapters this document {full_text}. No multiple choice."}
            ]
        )
    response = message.content
    questions = format_claude_response(response)
    return questions
    
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
        test = create_test(full_text) 
        st.write(test)
        st.download_button(
            label="Download Text File",
            data = full_text,
            file_name = f'{name}.txt',
            mime="text/plain"
        )
        st.download_button(
            label="Download Questions",
            data = test,
            file_name = f'{name}_test.txt',
            mime="text/plain"
        )
