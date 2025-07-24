import streamlit as st
import os
import requests
import bleach
from datetime import datetime, timedelta
from libsql_experimental import connect
import urllib.parse
import cloudinary
import cloudinary.uploader
import cloudinary.api

# --- Cloudinary Configuration ---
# This configures the Cloudinary library using your secrets
try:
    cloudinary.config(
        cloud_name = st.secrets["CLOUDINARY_CLOUD_NAME"],
        api_key = st.secrets["CLOUDINARY_API_KEY"],
        api_secret = st.secrets["CLOUDINARY_API_SECRET"],
        secure = True
    )
except Exception as e:
    st.error(f"Cloudinary configuration failed. Check your secrets. Error: {e}")
    st.stop()


# --- DESIGN AND STYLING (CSS) ---
st.markdown("""
<style>
/* Main app background */
[data-testid="stAppViewContainer"] {
    background-image: url("https://www.transparenttextures.com/patterns/cubes.png");
    background-color: #f0f2f5;
}
.main .block-container {
    background-color: rgba(255, 255, 255, 0.95);
    border-radius: 20px;
    padding: 2rem;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.chat-bubble {
    background-color: #ffffff;
    border-radius: 15px;
    padding: 12px 18px;
    max-width: 80%;
    align-self: flex-start;
    word-wrap: break-word;
    box-shadow: 0 2px 4px rgba(0,0,0,0.08);
    border: 1px solid #e9e9e9;
}
.chat-avatar {
    width: 45px;
    height: 45px;
    border-radius: 50%;
    margin-right: 12px;
    border: 2px solid #fff;
    box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}
.chat-row {
    display: flex;
    align-items: flex-start;
    margin-bottom: 15px;
}
.chat-name {
    font-weight: bold;
    font-size: 1rem;
    margin-bottom: 4px;
    color: #0d6efd;
}
.chat-timestamp {
    font-size: 0.75rem;
    color: #6c757d;
    text-align: right;
    margin-top: 8px;
}
.footer {
    text-align: center;
    padding-top: 2rem;
    color: gray;
    font-size: 0.9rem;
}
</style>
""", unsafe_allow_html=True)


# --- Setup DB ---
try:
    conn = connect(
        st.secrets["TURSO_DB_URL"],
        auth_token=st.secrets["TURSO_DB_AUTH_TOKEN"]
    )
    c = conn.cursor()
    # ** NEW ** Added a 'file_url' column to store image/video links
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            text TEXT,
            timestamp TEXT,
            ip TEXT,
            file_url TEXT 
        )
    ''')
    conn.commit()
    st.sidebar.success("Connected to Cloud DB")
except Exception as e:
    st.error(f"Failed to connect to the database: {e}")
    st.stop()

# --- Functions & Session State ---
def get_current_ist_time():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def get_ip():
    try:
        return requests.get('https://api64.ipify.org', timeout=5).text
    except requests.exceptions.RequestException:
        return "127.0.0.1"

if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False
if "page" not in st.session_state:
    st.session_state.page = 0

# --- Streamlit Page ---
st.set_page_config(page_title="Chat for Jawali", page_icon="💬")
with st.sidebar:
    st.header("Admin Login")
    password = st.text_input("Enter admin password", type="password", key="admin_password")
    if st.button("Login"):
        if password == st.secrets.get("ADMIN_PASS"):
            st.session_state.admin_logged_in = True
            st.rerun()
        else:
            st.error("Wrong password")
    if st.session_state.admin_logged_in:
        if st.button("Logout"):
            st.session_state.admin_logged_in = False
            st.rerun()

# --- Main App Area ---
st.title("💬 Chat for Jawali")
st.write("") 

# --- User Info Form ---
with st.form("chat_form", clear_on_submit=True):
    name = st.text_input("Your Name", placeholder="Enter your name...")
    text = st.text_area("Message", placeholder="Type a message (optional)...")
    # ** NEW ** File uploader for images and videos
    uploaded_file = st.file_uploader("Upload a photo or video (optional)", type=['png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov'])
    submitted = st.form_submit_button("Send Message")

if submitted:
    # A message or a file is required, not both.
    if (not name.strip()) or (not text.strip() and not uploaded_file):
        st.warning("Please provide a name and either a message or a file.")
    else:
        file_url = None
        # ** NEW ** Logic to handle the file upload
        if uploaded_file is not None:
            try:
                # Determine resource type (image or video) based on file type
                resource_type = "image" if uploaded_file.type.startswith('image/') else "video"
                # Upload to Cloudinary
                upload_result = cloudinary.uploader.upload(uploaded_file, resource_type=resource_type)
                file_url = upload_result.get('secure_url')
                st.success("File uploaded successfully!")
            except Exception as e:
                st.error(f"Error uploading file: {e}")

        user_ip = get_ip()
        clean_name = bleach.clean(name.strip())
        clean_text = bleach.clean(text.strip())
        timestamp = get_current_ist_time().strftime('%Y-%m-%d %H:%M:%S')
        
        # ** NEW ** Insert the file_url into the database
        c.execute("INSERT INTO messages (name, text, timestamp, ip, file_url) VALUES (?, ?, ?, ?, ?)",
                      (clean_name, clean_text, timestamp, user_ip, file_url))
        conn.commit()
        st.rerun()

st.divider()

# --- Display Messages ---
st.markdown("### Chat History")
MESSAGES_PER_PAGE = 25
offset = st.session_state.page * MESSAGES_PER_PAGE
# ** NEW ** Select the new file_url column
messages = c.execute(
    "SELECT name, text, timestamp, file_url FROM messages ORDER BY id DESC LIMIT ? OFFSET ?",
    (MESSAGES_PER_PAGE, offset)
).fetchall()

if not messages and st.session_state.page == 0:
    st.info("No messages yet. Be the first to post!")
else:
    for name, text, timestamp, file_url in messages:
        name_for_avatar = urllib.parse.quote_plus(name)
        avatar_url = f"https://ui-avatars.com/api/?name={name_for_avatar}&background=random&color=fff&size=128"
        
        # ** NEW ** Conditionally display text, image, or video
        media_html = ""
        if file_url:
            if any(ext in file_url for ext in ['png', 'jpg', 'jpeg', 'gif']):
                media_html = f'<img src="{file_url}" style="max-width: 100%; border-radius: 10px;">'
            elif any(ext in file_url for ext in ['mp4', 'mov']):
                media_html = f'<video controls style="max-width: 100%; border-radius: 10px;"><source src="{file_url}" type="video/mp4"></video>'
        
        chat_html = f"""
        <div class="chat-row">
            <img src="{avatar_url}" class="chat-avatar">
            <div class="chat-bubble">
                <div class="chat-name">{name}</div>
                <div>{text}</div>
                {media_html}
                <div class="chat-timestamp">{timestamp}</div>
            </div>
        </div>
        """
        st.markdown(chat_html, unsafe_allow_html=True)

# --- Pagination & Footer ---
st.write("") 
# ... (The rest of the pagination and admin code remains the same) ...
# ... (I've omitted it here for brevity, but it's in the full code block above) ...
