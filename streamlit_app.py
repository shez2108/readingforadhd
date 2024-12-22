import streamlit as st
import pypdf
import re
import os
import anthropic
from transformers import GPT2Tokenizer

st.title("ADHD Reader")


st.write(
    """
    #### Do you have trouble reading eBooks from your Kindle?
    #### Do you find that your eyes can't help moving across the page?
    #### Or that the content you're reading goes in one ear then out the other?
    """
)

st.write(
    "Name the text, input a PDF and let's chunk it up!"
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
                    "content": f"Based on the following text, create a two-question test comprehension (no answers needed):{full_text}"
                }
            ]
        )
        
        # The response is already a string, no need for complex formatting
        
        questions = format_claude_response(message.content)
        return questions
    except Exception as e:
        return f"Error creating test: {str(e)}"

"""def split_for_claude(text, max_tokens=4096):
    #Split text into chunks that fit within the token limit.#
    words = text.split()
    chunks = []
    current_chunk = []
    current_length = 0
    
    for word in words:
        current_chunk.append(word)
        current_length += len(word) + 1  # +1 for the space
        
        if current_length >= max_tokens:
            chunks.append(' '.join(current_chunk))
            current_chunk = []
            current_length = 0
    
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks"""

def split_for_claude(text, max_tokens=4096):
    """
    Split text into chunks that fit within Claude's token limit while preserving paragraph
    and sentence structure for better comprehension question generation.
    
    Args:
        text (str): The text to split
        max_tokens (int): Maximum tokens per chunk
    """
    # Initialize tokenizer
    tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
    
    # Split into paragraphs first
    paragraphs = text.split('\n\n')
    
    chunks = []
    current_chunk = []
    current_tokens = 0
    
    for paragraph in paragraphs:
        # Split paragraph into sentences
        sentences = re.split(r'(?<=[.!?])\s+', paragraph)
        
        for sentence in sentences:
            sentence_tokens = tokenizer.encode(sentence)
            sentence_token_count = len(sentence_tokens)
            
            # If single sentence exceeds token limit, split it
            if sentence_token_count > max_tokens:
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
                    current_chunk = []
                    current_tokens = 0
                
                # Split long sentence into smaller pieces
                words = sentence.split()
                temp_chunk = []
                temp_tokens = 0
                
                for word in words:
                    word_tokens = tokenizer.encode(word + ' ')
                    if temp_tokens + len(word_tokens) > max_tokens:
                        chunks.append(' '.join(temp_chunk))
                        temp_chunk = [word]
                        temp_tokens = len(word_tokens)
                    else:
                        temp_chunk.append(word)
                        temp_tokens += len(word_tokens)
                
                if temp_chunk:
                    current_chunk = temp_chunk
                    current_tokens = temp_tokens
                continue
            
            # Check if adding this sentence would exceed the limit
            if current_tokens + sentence_token_count > max_tokens:
                chunks.append(' '.join(current_chunk))
                current_chunk = [sentence]
                current_tokens = sentence_token_count
            else:
                current_chunk.append(sentence)
                current_tokens += sentence_token_count
    
    # Add any remaining text
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks
    
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
        # Split the full text into manageable chunks
        text_segments = split_for_claude(full_text, max_tokens=200000)
        st.write(len(text_segments))
        all_tests = []
        for segment in text_segments:
            test = create_test(segment)
            all_tests.append(test)
        
        combined_tests = "\n\n".join(all_tests)
        st.write(combined_tests)
        st.download_button(
            label="Download Text File",
            data = full_text,
            file_name = f'{name}.txt',
            mime="text/plain"
        )
        st.download_button(
            label="Download Questions",
            data = combined_tests,
            file_name = f'{name}_test.txt',
            mime="text/plain"
        )

st.write(
    """
    *Note: This is specifically built for handling PDFs. It divides the text into chunks and increases the space between those chunks, with the aim of making it easier to digest words on the page. 
    It also prints a test for you to make sure you're keeping sufficient track of the book's narrative. You must save the result and export it to your Kindle app.*
    """
)
