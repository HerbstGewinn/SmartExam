import streamlit as st
import networkx as nx
from pyvis.network import Network
import streamlit.components.v1 as components
import PyPDF2
import openai
import xml.etree.ElementTree as ET
import re  # We will use this to clean up the response
import argon2
from st_supabase_connection import SupabaseConnection
from supabase import Client

# OpenAI GPT-4 Integration (Insert your OpenAI API Key via Streamlit Secrets)
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Supabase login form
def login_form(
    * ,
    title: str = "Authentication",
    user_tablename: str = "users",
    username_col: str = "username",
    password_col: str = "password",
    create_title: str = "Create new account :baby: ",
    login_title: str = "Login to existing account :prince: ",
    allow_guest: bool = False,  
    allow_create: bool = True,
    create_username_label: str = "Create an email username",
    create_username_placeholder: str = None,
    create_username_help: str = None,
    create_password_label: str = "Create a password",
    create_password_placeholder: str = None,
    create_password_help: str = "Password cannot be recovered if lost",
    create_submit_label: str = "Create account",
    create_success_message: str = "Account created and logged-in :tada:",
    login_username_label: str = "Enter your email username",
    login_username_placeholder: str = None,
    login_username_help: str = None,
    login_password_label: str = "Enter your password",
    login_password_placeholder: str = None,
    login_password_help: str = None,
    login_submit_label: str = "Login",
    login_success_message: str = "Login succeeded :tada:",
    login_error_message: str = "Wrong username/password :x: ",
    email_constraint_fail_message: str = "Please sign up with a valid email address (must contain @).",
) -> Client:
    """Creates a user login form in Streamlit apps with simpler password criteria and email validation."""

    client = st.connection(name="supabase", type=SupabaseConnection)
    auth = argon2.PasswordHasher()

    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if "username" not in st.session_state:
        st.session_state["username"] = None

    if not st.session_state["authenticated"]:
        with st.expander(title, expanded=True):
            if allow_create:
                create_tab, login_tab = st.tabs([create_title, login_title])
            else:
                login_tab = st.container()

            if allow_create:
                with create_tab:
                    with st.form(key="create"):
                        username = st.text_input(label=create_username_label, placeholder=create_username_placeholder, help=create_username_help)
                        password = st.text_input(label=create_password_label, placeholder=create_password_placeholder, help=create_password_help, type="password")
                        hashed_password = auth.hash(password)
                        if st.form_submit_button(label=create_submit_label, type="primary"):
                            if "@" not in username:
                                st.error(email_constraint_fail_message)
                                st.stop()

                            try:
                                client.table(user_tablename).insert({username_col: username, password_col: hashed_password}).execute()
                            except Exception as e:
                                st.error(e.message)
                            else:
                                st.session_state["authenticated"] = True
                                st.session_state["username"] = username
                                st.success(create_success_message)
                                st.rerun()

            with login_tab:
                with st.form(key="login"):
                    username = st.text_input(label=login_username_label, placeholder=login_username_placeholder, help=login_username_help)
                    password = st.text_input(label=login_password_label, placeholder=login_password_placeholder, help=login_password_help, type="password")

                    if st.form_submit_button(label=login_submit_label, type="primary"):
                        response = client.table(user_tablename).select(f"{username_col}, {password_col}").eq(username_col, username).execute()

                        if len(response.data) > 0:
                            db_password = response.data[0]["password"]
                            if auth.verify(db_password, password):
                                st.session_state["authenticated"] = True
                                st.session_state["username"] = username
                                st.success(login_success_message)
                                st.rerun()
                            else:
                                st.error(login_error_message)
                        else:
                            st.error(login_error_message)

    return client

# Function to extract text from PDF
def extract_text_from_pdf(pdf_file):
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

# Function to interact with GPT-4 to summarize text (Note: This is synchronous)
def summarize_text(api_key, text):
    system_message = """
    You are an expert summarizer. Your task is to provide a concise (Sentences + bullet points) and informative summary of the given text.
    Focus on the main ideas, key points, and essential information.
    Ensure that your summary is coherent, well-structured, and captures the essence of the original text.
    Aim for a summary that is approximately 20-25% of the length of the original text.
    """
    
    prompt = f"Here is the text for summarization: {text}"

    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ],
        max_tokens=4960  # Adjust based on expected summary length
    )
    
    return response.choices[0].message.content

# Function to extract entities and relationships using GPT-4 (Note: This is synchronous)
def get_entities_and_relations(api_key, text):
    system_message = """
    You are an expert in natural language processing and knowledge extraction.
    Given a text, identify the main entities and their relationships.
    Return your response in the following XML format:
    <output>
    <entities>
    <entity>Entity1</entity>
    <entity>Entity2</entity>
    ...
    </entities>
    <relations>
    <relation>
    <source>SourceEntity</source>
    <target>TargetEntity</target>
    <type>RelationType</type>
    </relation>
    ...
    </relations>
    </output>
    Ensure that the XML is well-formed and does not contain any syntax errors. You must absolutely at all times 
    return your response in the format presented regardless of how large the document is. If the document is
    long and overwhelming then still do your best in returning as many entities as possible, without making a mistake.
    Do not include the relations about authors and their books in the knowledge graph.
    """
    
    prompt = f"Here is the text for analysis: {text}\nExtract entities and relationships from this text in the format presented."

    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ],
        max_tokens=4960
    )
    
    return response.choices[0].message.content

# Clean the XML response from GPT-4 by removing any markdown formatting
def clean_xml_response(xml_response):
    # Remove the ```xml and ``` that may wrap the response
    cleaned_response = re.sub(r"^```xml\s*|```$", "", xml_response.strip())
    return cleaned_response

# Function to parse XML response and create a knowledge graph
def generate_graph_from_xml(xml_response):
    # Clean the XML response
    cleaned_xml_response = clean_xml_response(xml_response)
    
    try:
        # Parse the cleaned XML response
        root = ET.fromstring(cleaned_xml_response)
        entities = [entity.text for entity in root.find('entities').findall('entity')]
        relationships = [(relation.find('source').text, relation.find('target').text, relation.find('type').text) 
                         for relation in root.find('relations').findall('relation')]
        
        # Initialize a graph
        G = nx.Graph()

        # Add entities as nodes
        for entity in entities:
            G.add_node(entity)

        # Add relationships as edges
        for source, target, relation in relationships:
            G.add_edge(source, target, label=relation)

        return G
    except ET.ParseError as e:
        st.error(f"Failed to parse XML: {e}")
        return None

# Main app function
def main():
    # Authentication check
    client = login_form()

    if st.session_state["authenticated"]:
        st.title("🧠 Upload Lectures- Generate your Knowledge Graph")
        st.write("Upload a PDF, get a summary, and generate a knowledge graph.")

        # File uploader to upload a PDF
        uploaded_pdf = st.file_uploader("Choose a PDF file", type="pdf")

        # Check if a PDF file is uploaded
        if uploaded_pdf is not None:
            # Step 1: Extract text from the uploaded PDF
            pdf_text = extract_text_from_pdf(uploaded_pdf)
            
            # Step 2: Summarize the text using GPT-4
            st.subheader("Summarizing PDF content...")
            
            # Call the summarize function (synchronous)
            summary = summarize_text(openai.api_key, pdf_text)
            
            # Display the summary
            
            st.write(summary)

            # Step 3: Extract entities and relationships using GPT-4
            st.subheader("Generating Knowledge Graph...")
            
            # Call the entity and relation extraction function (synchronous)
            xml_response = get_entities_and_relations(openai.api_key, pdf_text)
            
            # Step 4: Generate a knowledge graph from the GPT-4 response
            graph = generate_graph_from_xml(xml_response)
            
            if graph:
                # Step 5: Visualize the graph using PyVis
                net = Network(height='750px', width='100%', bgcolor='#222222', font_color='white')
                net.from_nx(graph)  # Convert the NetworkX graph into a PyVis graph
                
                # Save and display the graph
                net.save_graph('knowledge_graph.html')
                HtmlFile = open('knowledge_graph.html', 'r', encoding='utf-8')
                components.html(HtmlFile.read(), height=800)
                
                # Step 6: Provide a download button for the graph
                with open('knowledge_graph.html', 'rb') as file:
                    st.download_button(label="Download Knowledge Graph", data=file, file_name="knowledge_graph.html", mime="text/html")
            else:
                st.error("Failed to generate the knowledge graph.")

        else:
            st.warning("Please upload a PDF file to generate a knowledge graph.")

if __name__ == "__main__":
    main()
