import streamlit as st
import os
import requests
import bleach
from datetime import datetime, timedelta
from libsql_experimental import connect
import urllib.parse

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
.chat-bubble { background-color: #ffffff; border-radius: 15px; padding: 12px 18px; max-width: 80%; align-self: flex-start; word-wrap: break-word; box-shadow: 0 2px 4px rgba(0,0,0,0.08); border: 1px solid #e9e9e9; }
.chat-avatar { width: 45px; height: 45px; border-radius: 50%; margin-right: 12px; border: 2px solid #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.2); }
.chat-row { display: flex; align-items: flex-start; margin-bottom: 15px; }
.chat-name { font-weight: bold; font-size: 1rem; margin-bottom: 4px; color: #0d6efd; }
.chat-timestamp { font-size: 0.75rem; color: #6c757d; text-align: right; margin-top: 8px; }
.footer { text-align: center; padding-top: 2rem; color: gray; font-size: 0.9rem; }
</style>
""", unsafe_allow_html=True)


# --- Setup DB ---
try:
    conn = connect(
        st.secrets["TURSO_DB_URL"],
        auth_token=st.secrets["TURSO_DB_AUTH_TOKEN"]
    )
    c = conn.cursor()
    # Check if 'file_url' column exists and add it if it doesn't
    c.execute("PRAGMA table_info(messages)")
    columns = [info[1] for info in c.fetchall()]
    if 'file_url' not in columns:
        c.execute("ALTER TABLE messages ADD COLUMN file_url TEXT")
        conn.commit()
    # Create table if it doesn't exist
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

# --- Streamlit Page & Admin Sidebar ---
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
    uploaded_file = st.file_uploader("Upload a photo or video (Max 30 MB)", type=['png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'avi'])
    submitted = st.form_submit_button("Send Message")

if submitted:
    if (not name.strip()) or (not text.strip() and not uploaded_file):
        st.warning("Please provide a name and either a message or a file.")
    else:
        file_url = None
        proceed_with_upload = True
        
        if uploaded_file is not None:
            # ** NEW ** Check the file size before uploading
            MAX_FILE_SIZE_MB = 30
            if uploaded_file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
                st.error(f"File is too large. Maximum size is {MAX_FILE_SIZE_MB} MB.")
                proceed_with_upload = False # Prevent the upload
            
            if proceed_with_upload:
                try:
                    import cloudinary
                    import cloudinary.uploader
                    cloudinary.config(
                        cloud_name=st.secrets["CLOUDINARY_CLOUD_NAME"],
                        api_key=st.secrets["CLOUDINARY_API_KEY"],
                        api_secret=st.secrets["CLOUDINARY_API_SECRET"],
                        secure=True
                    )
                    resource_type = "image" if uploaded_file.type.startswith('image/') else "video"
                    upload_result = cloudinary.uploader.upload(uploaded_file, resource_type=resource_type)
                    file_url = upload_result.get('secure_url')
                except Exception as e:
                    st.error(f"Error uploading file: {e}")
                    proceed_with_upload = False

        if proceed_with_upload:
            user_ip = get_ip()
            clean_name = bleach.clean(name.strip())
            clean_text = bleach.clean(text.strip())
            timestamp = get_current_ist_time().strftime('%Y-%m-%d %H:%M:%S')
            
            c.execute("INSERT INTO messages (name, text, timestamp, ip, file_url) VALUES (?, ?, ?, ?, ?)",
                          (clean_name, clean_text, timestamp, user_ip, file_url))
            conn.commit()
            st.rerun()

st.divider()

# --- Display Messages ---
st.markdown("### Chat History")
MESSAGES_PER_PAGE = 25
offset = st.session_state.page * MESSAGES_PER_PAGE
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
        
        message_content = ""
        if text:
            message_content += f"<div>{text}</div>"
        
        if file_url:
            media_style = "margin-top: 10px;" if text else ""
            if any(ext in file_url for ext in ['png', 'jpg', 'jpeg', 'gif']):
                message_content += f'<div style="{media_style}"><img src="{file_url}" style="max-width: 100%; border-radius: 10px;"></div>'
            elif any(ext in file_url for ext in ['mp4', 'mov', 'avi']):
                message_content += f'<div style="{media_style}"><video controls style="max-width: 100%; border-radius: 10px;"><source src="{file_url}"></video></div>'

        chat_html = f"""
        <div class="chat-row">
            <img src="{avatar_url}" class="chat-avatar">
            <div class="chat-bubble">
                <div class="chat-name">{name}</div>
                {message_content}
                <div class="chat-timestamp">{timestamp}</div>
            </div>
        </div>
        """
        st.markdown(chat_html, unsafe_allow_html=True)

# --- Pagination & Footer ---
st.write("") 
col1, col2 = st.columns(2)
with col1:
    if st.session_state.page > 0:
        if st.button("⬅️ Previous Page"):
            st.session_state.page -= 1
            st.rerun()
with col2:
    c.execute("SELECT COUNT(id) FROM messages")
    count_result = c.fetchone()
    total_messages = count_result[0] if count_result else 0
    if total_messages > (st.session_state.page + 1) * MESSAGES_PER_PAGE:
        if st.button("Next Page ➡️"):
            st.session_state.page += 1
            st.rerun()

st.divider()
st.markdown("<div class='footer'>CODEMONK BY STAYMONK</div>", unsafe_allow_html=True)


# --- Admin Tools ---
if st.session_state.admin_logged_in:
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 👮 Admin Tools")
        st.subheader("Delete Individual Messages")
        admin_messages = c.execute(
            "SELECT id, name, text, timestamp, ip, file_url FROM messages ORDER BY id DESC LIMIT ? OFFSET ?",
            (MESSAGES_PER_PAGE, offset)
        ).fetchall()
        for msg_id, name, text, timestamp, ip, file_url in admin_messages:
            with st.expander(f"ID: {msg_id} | User: {name} | IP: {ip}"):
                st.write(f"_{timestamp}_")
                st.text(text)
                if file_url:
                    st.write("Attachment:", file_url)
                if st.button(f"Delete Message ID {msg_id}", key=f"delete_{msg_id}"):
                    c.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
                    conn.commit()
                    st.success(f"Deleted message ID {msg_id}")
                    st.rerun()
        st.subheader("🚨 Danger Zone")
        if st.button("Delete ALL Messages"):
            c.execute("DELETE FROM messages")
            conn.commit()
            st.success("All messages have been deleted.")
            st.rerun()
