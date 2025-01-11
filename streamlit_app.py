import streamlit as st
import pypdf
import re
import os
import anthropic
from transformers import GPT2Tokenizer
import time
from io import BytesIO
from docx import Document

st.set_page_config(
    page_title="Breaking Down Difficult Texts",
    page_icon="📚",
    layout="centered"
)


# Custom CSS
st.markdown("""
    <style>
    .main {
        padding: 2rem;
    }
    .stTitle {
        color: #1E88E5;
        font-size: 3rem !important;
    }
    .stAlert {
        padding: 1rem;
        border-radius: 0.5rem;
    }
    </style>
""", unsafe_allow_html=True)

# Main title with icon
st.title("📚 ADHD/Dyslexia Reader")

# Create three columns for the intro questions
col1, col2, col3 = st.columns(3)

with col1:
    st.info("🤔 Do you have trouble reading eBooks from your Kindle?")
with col2:
    st.warning("👀 Do you find that your eyes can't help moving across the page?")
with col3:
    st.error("🧠 Does content go in one ear and out the other?")

st.write(
    "Name the text, input a PDF and let's break it down!"
)

# Add a divider
st.divider()

# Main instruction with better styling
st.markdown("### 📝 Let's make reading easier for you!")

tab1, tab2, tab3 = st.tabs(["Import PDF", "Import ePub", "Import Text File"])

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

def bold_initial_letters(text):
    # Split the text into words
    words = text.split()
    
    # Process each word
    result = []
    for word in words:
        if len(word) > 0:
            # Bold the first n characters based on word length
            bold_count = min(len(word), len(word) // 2)  # Bold half the word length
            if bold_count == 0:  # Ensure at least one letter is bold
                bold_count = 1
                
            bolded_part = word[:bold_count]
            regular_part = word[bold_count:]
            result.append(f"**{bolded_part}**{regular_part}")
    
    # Join the words back together
    return ' '.join(result)

def pdf_to_docx(file, text_path=None):
    reader = pypdf.PdfReader(file)
    all_text = []
    # Process each page and extract the text
    for page_num in range(len(reader.pages)):
        # Extract text from page
        page = reader.pages[page_num]
        text = page.extract_text()
        # Clean and format text
        paragraphs = clean_text(text)
        for para in paragraphs:
            chunks = bold_initial_letters(para)
            all_text.extend(chunks)
    return all_text

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
    # Debug: Check if we have text
    if not text:
        return "No text provided to create test from"
    
    try:
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,#
            messages=[
                {
                    "role": "user", 
                    "content": f"Based on the following text, create a test comprehension (no answers needed):{text}"
                }
            ]
        )
        
        # The response is already a string, no need for complex formatting
        
        questions = format_claude_response(message.content)
        time.sleep(60)
        return questions
    except Exception as e:
        return f"Error creating test: {str(e)}"
        
def split_for_claude(text, max_tokens=200000):
    """
    Split text into chunks that fit within Claude's token limit,
    using the 3 characters ≈ 1 token approximation.
    """
    # Calculate approximate characters allowed (4 chars per token)
    max_chars = max_tokens * 3
    
    words = text.split()
    chunks = []
    current_chunk = []
    current_length = 0
    
    for word in words:
        word_length = len(word) + 1  # +1 for the space
        estimated_tokens = word_length / 3  # Estimate tokens for this word
        
        if current_length + estimated_tokens > max_chars:
            chunks.append(' '.join(current_chunk))
            current_chunk = [word]
            current_length = word_length
        else:
            current_chunk.append(word)
            current_length += word_length
    
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks

with tab1:
    # initialize the search_type in session state if it doesn't exist
    if 'reading_type' not in st.session_state:
        st.session_state.search_type = None

    # Replace the button checks with radio buttons
    search_type = st.radio("Select Reading Type", ["Chunked", "Bionic"])
    if search_type == 'Chunked':
        name = st.text_input("Enter the name of the book")
        if name:
            name = name.replace(' ', '_').lower()
            document = st.file_uploader("Import a PDF", type="pdf")
            convert_button = st.button("Convert!")
            if convert_button:
                st.write("Button Clicked!")
                text_chunks = pdf_to_text(document)
                # Create the full text content
                full_text = '\n\n'.join(text_chunks)
                # Split the full text into manageable chunks
                text_segments = split_for_claude(full_text, max_tokens=200000)
                st.write(len(text_segments))
                all_tests = []
                for segment in text_segments:
                    test = create_test(segment)
                    all_tests.append(test)
                    time.sleep(120)
            
                combined_tests = "\n\n".join(all_tests)
                st.write(combined_tests)
                st.download_button(
                    label="Download Text File",
                    data=full_text,
                    file_name=f'{name}.txt',
                    mime="text/plain"
                )
                st.download_button(
                    label="Download Questions",
                    data=combined_tests,
                    file_name=f'{name}_test.txt',
                    mime="text/plain"
                )
    if search_type == 'Bionic':
        name = st.text_input("Enter the name of the book")
        if name:
            name = name.replace(' ', '_').lower()
            document = st.file_uploader("Import a PDF", type="pdf")
            convert_button = st.button("Convert!")
            if convert_button:
                st.write("Button Clicked!")
                text_chunks = pdf_to_docx(document)
                # Create the full text content
                full_text = ' '.join(text_chunks)
                # Split the full text into manageable chunks
                text_segments = split_for_claude(full_text, max_tokens=200000)
                st.write(len(text_segments))
                all_tests = []
                for segment in text_segments:
                    test = create_test(segment)
                    all_tests.append(test)
                    time.sleep(120)
            
                combined_tests = "\n\n".join(all_tests)
                st.write(combined_tests)
                st.download_button(
                    label="Download DOCX file",
                    data=full_text,
                    file_name=f'{name}.docx',
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
                st.download_button(
                    label="Download Questions",
                    data=combined_tests,
                    file_name=f'{name}_test.txt',
                    mime="text/plain"
                )

    
# Footer note in an info box
st.info("""
    ℹ️ **Note**: This tool is specifically built for PDFs. It:
    - Divides text into easily digestible chunks
    - Increases spacing for better readability
    - Generates comprehension questions
    - Creates Kindle-compatible output
    
    Save the result and export it to your Kindle app for the best reading experience.
""")
