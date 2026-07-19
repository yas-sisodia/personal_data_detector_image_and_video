



import base64
import html
import io
import json
import queue
import threading
import time
import traceback

import requests
import streamlit as st
import websocket
from PIL import Image

# ==============================================================================
# Configuration & Endpoints
# ==============================================================================

# BASE_HTTP_URL = "http://localhost:8000"
# BASE_WS_URL = "ws://localhost:8000"


BASE_HTTP_URL = "https://yas.tail538282.ts.net"
BASE_WS_URL = "wss://yas.tail538282.ts.net"

BACKEND_UPLOAD = f"{BASE_HTTP_URL}/upload"
WS_URL = f"{BASE_WS_URL}/ws/analyze"

# ==============================================================================
# Helper Functions
# ==============================================================================

def init_session_state():
    """Initialize all required Streamlit session state variables."""
    defaults = {
        "uploaded_file": None,
        "file_type": None,
        "result": {},
        "show_results": False,
        "last_file_name": None,
        "is_analyzing": False,
        "trigger_analysis": False,
        "analysis_started": False,
        "ws_queue": None,
        "ws_thread": None,
        "progress_percent": 0,
        "progress_step": "",
        "enable_caption": True,
        "start_time": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def reset_for_new_upload():
    """Reset processing variables for a new file upload."""
    st.session_state.result = {}
    st.session_state.show_results = False
    st.session_state.progress_percent = 0
    st.session_state.progress_step = ""
    st.session_state.analysis_started = False
    st.session_state.trigger_analysis = False
    st.session_state.is_analyzing = False
    st.session_state.ws_queue = None
    st.session_state.ws_thread = None
    st.session_state.start_time = None

def highlight_text(text, segments):
    """Highlight sensitive segments within a block of text."""
    if not text:
        return ""
    
    # Filter out invalid segments
    valid_segments = [
        seg for seg in (segments or [])
        if seg.get("start") is not None
        and seg.get("end") is not None
        and isinstance(seg.get("start"), int)
        and isinstance(seg.get("end"), int)
    ]

    # If no valid segments, escape the entire text safely
    if not valid_segments:
        return html.escape(text)

    COLOR = "#e53935"
    valid_segments = sorted(valid_segments, key=lambda x: x["start"])

    result = []
    last = 0

    for seg in valid_segments:
        start, end = seg["start"], seg["end"]
        label = seg.get("type", "SENSITIVE")
        score = seg.get("score", 0.0)

        # Skip overlapping segments
        if start < last:
            continue

        # Append preceding text and the highlighted segment, escaping everything
        result.append(html.escape(text[last:start]))
        result.append(
            f'<span style="background-color:{COLOR};'
            f'padding:2px 4px;border-radius:4px;font-weight:600;" '
            f'title="{html.escape(label)} ({score:.2f})">'
            f'{html.escape(text[start:end])}</span>'
        )
        last = end

    # Append any remaining text safely
    result.append(html.escape(text[last:]))
    return "".join(result)

def websocket_listener(file_id, file_type, message_queue, enable_caption):
    """Background thread function to listen to WebSocket updates."""
    ws = websocket.WebSocket()
    try:
        ws.connect(WS_URL, timeout=3000)

        ws.send(json.dumps({
            "file_id": file_id,
            "file_type": file_type,
            "enable_caption": enable_caption
        }))

        while True:
            msg = ws.recv()
            if not msg:
                break

            data = json.loads(msg)
            message_queue.put(data)

            if data.get("type") in ["result", "error"]:
                break

    except Exception as e:
        message_queue.put({"type": "error", "message": str(e)})
    finally:
        if ws.connected:
            ws.close()

# ==============================================================================
# Page Setup & State Initialization
# ==============================================================================

st.set_page_config(page_title="Live PII Detection", layout="wide")

# ==============================================================================

# hide header 

st.markdown("""
<style>
/* Hide the entire Streamlit header */
header[data-testid="stHeader"] {
    display: none;
}

/* Hide the toolbar (three dots) */
[data-testid="stToolbar"] {
    display: none;
}

/* Hide the decoration line at the top */
[data-testid="stDecoration"] {
    display: none;
}

/* Remove extra top padding */
.block-container {
    padding-top: 0rem;
}

/* Move the app to the very top */
.stApp {
    margin-top: 0;
}
</style>
""", unsafe_allow_html=True)

# ==============================================================================



init_session_state()


st.title("🔴 Live Personal Data Detection Framework (Image & Video)")

st.toggle(
    "📝 Enable Image Captioning",
    key="enable_caption"
)

# # ==============================================================================
# # File Upload Handler
# # ==============================================================================

# uploaded = st.file_uploader(
#     "Upload image or video",
#     type=["jpg", "jpeg", "png", "mp4", "mov", "avi"],
#     disabled=st.session_state.is_analyzing
# )

# # 1. Handle file cleared out by the user
# if uploaded is None and st.session_state.uploaded_file is not None:
#     reset_for_new_upload()
#     st.session_state.uploaded_file = None
#     st.rerun()

# # 2. Handle a new file uploaded (uses unique file_id rather than object match)
# if uploaded is not None:
#     current_file_id = getattr(st.session_state.uploaded_file, 'file_id', None)
#     if uploaded.file_id != current_file_id:
#         reset_for_new_upload()
#         st.session_state.uploaded_file = uploaded
#         st.session_state.last_file_name = uploaded.name
#         st.session_state.file_type = "video" if uploaded.type.startswith("video") else "image"
        
#         st.session_state.is_analyzing = True
#         st.session_state.trigger_analysis = True
#         st.rerun()

# # ==============================================================================


# ==============================================================================
# UI Layout Definition
# ==============================================================================

left_col, right_col = st.columns([1, 3], gap="large")

with left_col:
    


    # ==============================================================================
    # File Upload Handler
    # ==============================================================================

    uploaded = st.file_uploader(
        "Upload image or video",
        type=["jpg", "jpeg", "png", "mp4", "mov", "avi"],
        disabled=st.session_state.is_analyzing
    )

    # 1. Handle file cleared out by the user
    if uploaded is None and st.session_state.uploaded_file is not None:
        reset_for_new_upload()
        st.session_state.uploaded_file = None
        st.rerun()

    # 2. Handle a new file uploaded (uses unique file_id rather than object match)
    if uploaded is not None:
        current_file_id = getattr(st.session_state.uploaded_file, 'file_id', None)
        if uploaded.file_id != current_file_id:
            reset_for_new_upload()
            st.session_state.uploaded_file = uploaded
            st.session_state.last_file_name = uploaded.name
            st.session_state.file_type = "video" if uploaded.type.startswith("video") else "image"
            
            st.session_state.is_analyzing = True
            st.session_state.trigger_analysis = True
            st.rerun()

    # ==============================================================================

    if st.session_state.uploaded_file:
        if st.session_state.file_type == "image":
            st.image(st.session_state.uploaded_file, use_container_width=True)
        else:
            st.video(st.session_state.uploaded_file)

    # Empty containers allow us to completely erase UI elements when done
    progress_placeholder = st.empty()
    status_placeholder = st.empty()
    time_placeholder = st.empty()


    if st.session_state.is_analyzing:
        progress_placeholder.progress(max(0, min(st.session_state.progress_percent / 100, 1.0)))
        status_placeholder.markdown(f"**{st.session_state.progress_step}**")
        time_placeholder.empty() # Keep time hidden while processing
    
    # Cleanly remove progress bars and swap to total elapsed time
    elif st.session_state.start_time is not None and not st.session_state.is_analyzing:
        progress_placeholder.empty()
        status_placeholder.empty()
        elapsed_time = time.time() - st.session_state.start_time
        elapsed_time_str = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
        time_placeholder.success(f"⏱️ Total Processing Time: {elapsed_time_str}")
    
    if not st.session_state.uploaded_file:
        st.info("Select an image or video to begin")

# ==============================================================================
# Trigger API & WebSocket
# ==============================================================================

if st.session_state.trigger_analysis and not st.session_state.analysis_started:
    st.session_state.start_time = time.time()
    st.session_state.analysis_started = True
    st.session_state.trigger_analysis = False

    try:
        st.session_state.uploaded_file.seek(0)
        files = {
            "file": (
                st.session_state.uploaded_file.name,
                st.session_state.uploaded_file.getvalue(),
                st.session_state.uploaded_file.type
            )
        }
        
        response = requests.post(BACKEND_UPLOAD, files=files)

        if response.status_code == 200:
            file_id = response.json().get("file_name")
            msg_queue = queue.Queue()
            st.session_state.ws_queue = msg_queue

            # Start background thread
            thread = threading.Thread(
                target=websocket_listener,
                args=(
                    file_id,
                    st.session_state.file_type,
                    msg_queue,
                    st.session_state.enable_caption
                ),
                daemon=True
            )
            thread.start()
            st.session_state.ws_thread = thread

        else:
            st.error(f"Upload failed ({response.status_code})")
            st.session_state.is_analyzing = False

    except Exception:
        traceback.print_exc()
        st.error("Connection failed")
        st.session_state.is_analyzing = False

# ==============================================================================
# Process WebSocket Queue Updates
# ==============================================================================

if st.session_state.ws_queue:
    while not st.session_state.ws_queue.empty():
        data = st.session_state.ws_queue.get()
        msg_type = data.get("type")
        
        if msg_type == "progress":
            st.session_state.show_results = True
            st.session_state.progress_percent = data.get("percent", 0)
            st.session_state.progress_step = data.get("step", "")

            incoming = data.get("other_data", {})
            for k, v in incoming.items():
                if v is not None:
                    st.session_state.result[k] = v

        elif msg_type == "result":
            st.session_state.result = data.get("data", {})
            st.session_state.progress_percent = 100
            st.session_state.progress_step = "Completed"
            st.session_state.show_results = True

            # Cleanup processing state
            st.session_state.is_analyzing = False
            st.session_state.analysis_started = False
            st.session_state.trigger_analysis = False
            st.session_state.ws_thread = None
            st.session_state.ws_queue = None
            
            st.rerun()  # Force UI refresh to finalize layout

        elif msg_type == "error":
            st.error(data.get("message", "Unknown error occurred"))
            st.session_state.is_analyzing = False

# ==============================================================================
# Render Results Column
# ==============================================================================

with right_col:
    if st.session_state.show_results and st.session_state.result:
        st.subheader("📊 Sensitivity Analysis Results")
        
        res_col_left, res_col_right = st.columns(2, gap="large")

        # --- LEFT SIDE: Extracted Content ---
        with res_col_left:
            st.markdown("### 📄 Extracted Text")
            st.text_area(
                "Detected Content",
                value=st.session_state.result.get("sequence", ""),
                height=200,
                label_visibility="collapsed"
            )
            


            if "objects" in st.session_state.result and st.session_state.result["objects"]:
                st.markdown("### 🧠 Detected Objects")
                st.write(", ".join(set(st.session_state.result["objects"])))

            if "caption" in st.session_state.result:
                st.markdown("### 📝 Scene / Context Caption")
                st.write(st.session_state.result["caption"])

            

            if "textSeg" in st.session_state.result:
                st.markdown("### 🖍️ Highlighted Sensitive Text")

                highlighted_html = highlight_text(
                    st.session_state.result.get("text", ""),
                    st.session_state.result.get("textSeg", [])
                )

                st.markdown(
                    f"""<div style="
                    line-height:1.8;
                    font-size:16px;
                    padding:14px;
                    border:1px solid #333;
                    border-radius:8px;
                    background-color:#0e1117;
                    color:#ffffff;
                    white-space:pre-wrap;
                    word-wrap:break-word;
                    ">
                    {highlighted_html}
                    </div>""",
                    unsafe_allow_html=True
                )

        # --- RIGHT SIDE: Sensitivity Classification ---
        with res_col_right:
            st.markdown("### 🔐 Sensitivity Classification")

            labels = st.session_state.result.get("labels", [])
            scores = st.session_state.result.get("scores", [])
            
            # Rendering only when available prevents Streamlit component ghosting
            if labels and scores:
                for label, score in sorted(zip(labels, scores), key=lambda x: x[1], reverse=True):
                    c1, c2 = st.columns([4, 1])
                    with c1:
                        st.write(f"**{label}**")
                        safe_score = max(0.0, min(1.0, float(score)))
                        st.progress(safe_score)
                    with c2:
                        st.write(f"**{round(safe_score * 100, 2)}%**")

            if "caption_image" in st.session_state.result:
                try:
                    img_bytes = base64.b64decode(st.session_state.result["caption_image"])
                    img = Image.open(io.BytesIO(img_bytes))
                    st.markdown("### 🖼️ Video Context Image")
                    st.image(img, use_container_width=True)
                except Exception as e:
                    st.error(f"Could not load context image: {e}")

# ==============================================================================
# Polling Loop Update
# ==============================================================================

if st.session_state.is_analyzing:
    # Set to 0.25 to hit the sweet spot between snappy updates and avoiding UI flickering
    time.sleep(0.25)
    st.rerun()

# ==============================================================================



# import base64
# import io
# import json
# import queue
# import threading
# import time
# import traceback

# import requests
# import streamlit as st
# import websocket
# from PIL import Image

# # ==============================================================================
# # Configuration & Endpoints
# # ==============================================================================

# BASE_HTTP_URL = "https://yas.tail538282.ts.net"
# BASE_WS_URL = "wss://yas.tail538282.ts.net"

# BACKEND_UPLOAD = f"{BASE_HTTP_URL}/upload"
# WS_URL = f"{BASE_WS_URL}/ws/analyze"

# # ==============================================================================
# # Helper Functions
# # ==============================================================================

# def init_session_state():
#     """Initialize all required Streamlit session state variables."""
#     defaults = {
#         "uploaded_file": None,
#         "file_type": None,
#         "result": None,
#         "show_results": False,
#         "last_file_name": None,
#         "is_analyzing": False,
#         "trigger_analysis": False,
#         "analysis_started": False,
#         "ws_queue": None,
#         "ws_thread": None,
#         "progress_percent": 0,
#         "progress_step": "",
#         "enable_caption": True,
#         "start_time": None,
#     }
#     for key, value in defaults.items():
#         if key not in st.session_state:
#             st.session_state[key] = value

# def reset_for_new_upload():
#     """Reset processing variables for a new file upload."""
#     st.session_state.result = None
#     st.session_state.show_results = False
#     st.session_state.progress_percent = 0
#     st.session_state.progress_step = ""
#     st.session_state.analysis_started = False
#     st.session_state.trigger_analysis = False
#     st.session_state.is_analyzing = False
#     st.session_state.ws_queue = None
#     st.session_state.ws_thread = None
#     st.session_state.start_time = None

# def highlight_text(text, segments):
#     """Highlight sensitive segments within a block of text."""
#     if not text or not segments:
#         return text

#     COLOR = "#e53935"

#     # Filter out invalid segments
#     valid_segments = [
#         seg for seg in segments
#         if seg.get("start") is not None
#         and seg.get("end") is not None
#         and isinstance(seg.get("start"), int)
#         and isinstance(seg.get("end"), int)
#     ]

#     if not valid_segments:
#         return text

#     valid_segments = sorted(valid_segments, key=lambda x: x["start"])

#     result = []
#     last = 0

#     for seg in valid_segments:
#         start, end = seg["start"], seg["end"]
#         label = seg.get("type", "SENSITIVE")
#         score = seg.get("score", 0.0)

#         # Skip overlapping segments
#         if start < last:
#             continue

#         # Append preceding text and the highlighted segment
#         result.append(text[last:start])
#         result.append(
#             f'<span style="background-color:{COLOR};'
#             f'padding:2px 4px;border-radius:4px;font-weight:600;" '
#             f'title="{label} ({score:.2f})">'
#             f'{text[start:end]}</span>'
#         )
#         last = end

#     # Append any remaining text
#     result.append(text[last:])
#     return "".join(result)

# def websocket_listener(file_id, file_type, message_queue, enable_caption):
#     """Background thread function to listen to WebSocket updates."""
#     ws = websocket.WebSocket()
#     try:
#         ws.connect(WS_URL, timeout=3000)

#         ws.send(json.dumps({
#             "file_id": file_id,
#             "file_type": file_type,
#             "enable_caption": enable_caption
#         }))

#         while True:
#             msg = ws.recv()
#             if not msg:
#                 break

#             data = json.loads(msg)
#             message_queue.put(data)

#             if data.get("type") in ["result", "error"]:
#                 break

#     except Exception as e:
#         message_queue.put({"type": "error", "message": str(e)})
#     finally:
#         # Ensured connection closes even if an exception occurs
#         if ws.connected:
#             ws.close()

# # ==============================================================================
# # Page Setup & State Initialization
# # ==============================================================================

# st.set_page_config(page_title="Live PII Detection", layout="wide")
# init_session_state()

# st.title("🔴 Live Personal Data Detection Framework (Image & Video)")

# st.toggle(
#     "📝 Enable Image Captioning",
#     key="enable_caption"
# )

# # ==============================================================================
# # File Upload Handler
# # ==============================================================================

# uploaded = st.file_uploader(
#     "Upload image or video",
#     type=["jpg", "jpeg", "png", "mp4", "mov", "avi"],
#     disabled=st.session_state.is_analyzing
# )

# if uploaded and uploaded != st.session_state.uploaded_file:
#     reset_for_new_upload()
#     st.session_state.uploaded_file = uploaded
#     st.session_state.last_file_name = uploaded.name
#     st.session_state.file_type = "video" if uploaded.type.startswith("video") else "image"
    
#     st.session_state.is_analyzing = True
#     st.session_state.trigger_analysis = True
#     st.rerun()

# # ==============================================================================
# # UI Layout Definition
# # ==============================================================================

# left_col, right_col = st.columns([1, 3], gap="large")

# with left_col:
#     if st.session_state.uploaded_file:
#         if st.session_state.file_type == "image":
#             st.image(st.session_state.uploaded_file, use_container_width=True)
#         else:
#             st.video(st.session_state.uploaded_file)

#     progress_placeholder = st.empty()
#     status_placeholder = st.empty()

#     if st.session_state.is_analyzing:
#         progress_placeholder.progress(max(0, min(st.session_state.progress_percent / 100, 1.0)))
#         status_placeholder.markdown(f"**{st.session_state.progress_step}**")
    
#     # Display elapsed processing time after completion
#     elif st.session_state.start_time is not None and not st.session_state.is_analyzing:
#         elapsed_time = time.time() - st.session_state.start_time
#         elapsed_time_str = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))
#         st.success(f"⏱️ Total Processing Time: {elapsed_time_str}")
    
#     if not st.session_state.uploaded_file:
#         st.info("Select an image or video to begin")

# # ==============================================================================
# # Trigger API & WebSocket
# # ==============================================================================

# if st.session_state.trigger_analysis and not st.session_state.analysis_started:
#     st.session_state.start_time = time.time()
#     st.session_state.analysis_started = True
#     st.session_state.trigger_analysis = False

#     try:
#         st.session_state.uploaded_file.seek(0)
#         files = {
#             "file": (
#                 st.session_state.uploaded_file.name,
#                 st.session_state.uploaded_file.getvalue(),
#                 st.session_state.uploaded_file.type
#             )
#         }
        
#         response = requests.post(BACKEND_UPLOAD, files=files)

#         if response.status_code == 200:
#             file_id = response.json().get("file_name")
#             msg_queue = queue.Queue()
#             st.session_state.ws_queue = msg_queue

#             # Start background thread
#             thread = threading.Thread(
#                 target=websocket_listener,
#                 args=(
#                     file_id,
#                     st.session_state.file_type,
#                     msg_queue,
#                     st.session_state.enable_caption
#                 ),
#                 daemon=True
#             )
#             thread.start()
#             st.session_state.ws_thread = thread

#         else:
#             st.error(f"Upload failed ({response.status_code})")
#             st.session_state.is_analyzing = False

#     except Exception:
#         traceback.print_exc()
#         st.error("Connection failed")
#         st.session_state.is_analyzing = False

# # ==============================================================================
# # Process WebSocket Queue Updates
# # ==============================================================================

# if st.session_state.ws_queue:
#     while not st.session_state.ws_queue.empty():
#         data = st.session_state.ws_queue.get()
#         msg_type = data.get("type")
        
#         if msg_type == "progress":
#             st.session_state.show_results = True
#             st.session_state.progress_percent = data.get("percent", 0)
#             st.session_state.progress_step = data.get("step", "")

#             if st.session_state.result is None:
#                 st.session_state.result = {}

#             incoming = data.get("other_data", {})
#             for k, v in incoming.items():
#                 if v is not None:
#                     st.session_state.result[k] = v

#         elif msg_type == "result":
#             st.session_state.result = data.get("data", {})
#             st.session_state.progress_percent = 100
#             st.session_state.progress_step = "Completed"
#             st.session_state.show_results = True

#             # Cleanup processing state
#             st.session_state.is_analyzing = False
#             st.session_state.analysis_started = False
#             st.session_state.trigger_analysis = False
#             st.session_state.ws_thread = None
#             st.session_state.ws_queue = None
            
#             st.rerun()  # Force UI refresh to finalize layout

#         elif msg_type == "error":
#             st.error(data.get("message", "Unknown error occurred"))
#             st.session_state.is_analyzing = False

# # ==============================================================================
# # Render Results Column
# # ==============================================================================

# with right_col:
#     if st.session_state.show_results and st.session_state.result:
#         st.subheader("📊 Sensitivity Analysis Results")
        
#         # Create two nested columns to put Text and Classification side by side
#         res_col_left, res_col_right = st.columns(2, gap="large")

#         # --- LEFT SIDE: Extracted Content ---
#         with res_col_left:
#             st.markdown("### 📄 Extracted Text")
#             st.text_area(
#                 "Detected Content",
#                 value=st.session_state.result.get("sequence", ""),
#                 height=200,
#                 label_visibility="collapsed" # Hides the small "Detected Content" label to keep it clean
#             )
            
            
#             if "objects" in st.session_state.result and st.session_state.result["objects"]:
#                 st.markdown("### 🧠 Detected Objects")
#                 st.write(", ".join(set(st.session_state.result["objects"])))

#             if "caption" in st.session_state.result:
#                 st.markdown("### 📝 Scene / Context Caption")
#                 st.write(st.session_state.result["caption"])

#             if "textSeg" in st.session_state.result:
#                 st.markdown("### 🖍️ Highlighted Sensitive Text")

#                 highlighted_html = highlight_text(
#                     st.session_state.result.get("text", ""),
#                     st.session_state.result.get("textSeg", [])
#                 )

#                 st.markdown(
#                     f"""<div style="
#                     line-height:1.8;
#                     font-size:16px;
#                     padding:14px;
#                     border:1px solid #333;
#                     border-radius:8px;
#                     background-color:#0e1117;
#                     color:#ffffff;
#                     white-space:pre-wrap;
#                     word-wrap:break-word;
#                     ">
#                     {highlighted_html}
#                     </div>""",
#                     unsafe_allow_html=True
#                 )

#         # --- RIGHT SIDE: Sensitivity Classification ---
#         with res_col_right:
#             st.markdown("### 🔐 Sensitivity Classification")

#             labels = st.session_state.result.get("labels", [])
#             scores = st.session_state.result.get("scores", [])
            
#             if labels and scores:
#                 for label, score in sorted(zip(labels, scores), key=lambda x: x[1], reverse=True):
#                     c1, c2 = st.columns([4, 1])
#                     with c1:
#                         st.write(f"**{label}**")
#                         safe_score = max(0.0, min(1.0, float(score)))
#                         st.progress(safe_score)
#                     with c2:
#                         st.write(f"**{round(safe_score * 100, 2)}%**")
#             else:
#                 st.info("No classification data available.")

#             if "caption_image" in st.session_state.result:
#                 try:
#                     img_bytes = base64.b64decode(st.session_state.result["caption_image"])
#                     img = Image.open(io.BytesIO(img_bytes))
#                     st.markdown("### 🖼️ Video Context Image")
#                     st.image(img, use_container_width=True)
#                 except Exception as e:
#                     st.error(f"Could not load context image: {e}")

# # ==============================================================================
# # Polling Loop Update
# # ==============================================================================

# if st.session_state.is_analyzing:
#     time.sleep(0.5)
#     st.rerun()

# # =============================================================================


# from xml.etree.ElementTree import tostring

# import streamlit as st
# import websocket
# import json
# import requests
# import traceback
# import base64
# from PIL import Image
# import time
# import io
# import threading
# import queue

# # ==============================================================================
# # Backend endpoints


# # BACKEND_UPLOAD = "http://localhost:8000/upload"
# # WS_URL = "ws://localhost:8000/ws/analyze"


# BASE_HTTP_URL = "https://yas.tail538282.ts.net"
# BASE_WS_URL = "wss://yas.tail538282.ts.net"

# BACKEND_UPLOAD = f"{BASE_HTTP_URL}/upload"
# WS_URL = f"{BASE_WS_URL}/ws/analyze"


# # ==============================================================================
# # Page config
# st.set_page_config(page_title="Live PII Detection", layout="wide")
# st.title("🔴 Live Personal Data Detection Framework (Image & Video)")



# # ==============================================================================
# # Session state defaults
# defaults = {
#     "uploaded_file": None,
#     "file_type": None,
#     "result": None,
#     "show_results": False,
#     "last_file_name": None,
#     "is_analyzing": False,
#     "trigger_analysis": False,
#     "analysis_started": False,
#     "ws_queue": None,
#     "ws_thread": None,
#     "progress_percent": 0,
#     "progress_step": "",
#     "enable_caption": True,
#     "start_time": None, 
# }

# for k, v in defaults.items():
#     if k not in st.session_state:
#         st.session_state[k] = v



# # Ensure key exists
# if "enable_caption" not in st.session_state:
#     st.session_state.enable_caption = True

# # Use the toggle widget and link to session state
# st.toggle(
#     "📝 Enable Image Captioning",
#     value=st.session_state.enable_caption,
#     key="enable_caption"  # <-- use the same key as session state
# )

# # You can now safely use st.session_state.enable_caption anywhere
# st.write("Captioning enabled:", st.session_state.enable_caption)

# print(f"Image caption Toggle: {st.session_state.enable_caption}")
# # enable_caption = st.toggle("📝 Enable Image Captioning", value=True)
# # st.session_state.enable_caption = enable_caption




# # ==============================================================================
# # WebSocket listener (runs in background thread)

# def websocket_listener(file_id, file_type, message_queue, enable_caption):
#     try:
#         ws = websocket.WebSocket()
#         ws.connect(WS_URL, timeout=3000)

#         ws.send(json.dumps({
#             "file_id": file_id,
#             "file_type": file_type,
#             "enable_caption": enable_caption
#         }))

#         while True:
#             msg = ws.recv()
#             if not msg:
#                 break

#             data = json.loads(msg)
#             message_queue.put(data)

#             if data["type"] in ["result", "error"]:
#                 break

#         ws.close()

#     except Exception as e:
#         message_queue.put({"type": "error", "message": str(e)})

# # ==============================================================================


# def reset_for_new_upload():
#     st.session_state.result = None
#     st.session_state.show_results = False

#     st.session_state.progress_percent = 0
#     st.session_state.progress_step = ""

#     st.session_state.analysis_started = False
#     st.session_state.trigger_analysis = False
#     st.session_state.is_analyzing = False

#     st.session_state.ws_queue = None
#     st.session_state.ws_thread = None

# # ==============================================================================


# def highlight_text(text, segments):
#     if not text or not segments:
#         return text

#     COLOR = "#e53935"

#     # Filter out invalid segments
#     valid_segments = [
#         seg for seg in segments
#         if seg.get("start") is not None
#         and seg.get("end") is not None
#         and isinstance(seg.get("start"), int)
#         and isinstance(seg.get("end"), int)
#     ]

#     if not valid_segments:
#         return text

#     valid_segments = sorted(valid_segments, key=lambda x: x["start"])

#     result = []
#     last = 0

#     for seg in valid_segments:
#         print(f"Processing segment: {seg}")
#         start, end = seg["start"], seg["end"]
#         label = seg.get("type") or "SENSITIVE"
#         score = seg.get("score") or 0

#         if start < last:
#             continue

#         result.append(text[last:start])
#         result.append(
#             f'<span style="background-color:{COLOR};'
#             f'padding:2px 4px;border-radius:4px;font-weight:600;" '
#             f'title="{label} ({score:.2f})">'
#             f'{text[start:end]}</span>'
#         )
#         last = end

#     result.append(text[last:])
#     return "".join(result)

# # ==============================================================================
# # File upload

# uploaded = st.file_uploader(
#     "Upload image or video",
#     type=["jpg", "jpeg", "png", "mp4", "mov", "avi"],
#     disabled=st.session_state.is_analyzing
# )

# # ==============================================================================


# if uploaded and uploaded.name != st.session_state.last_file_name:
#     reset_for_new_upload()

#     st.session_state.uploaded_file = uploaded
#     st.session_state.last_file_name = uploaded.name
#     st.session_state.file_type = (
#         "video" if uploaded.type.startswith("video") else "image"
#     )

#     st.session_state.is_analyzing = True
#     st.session_state.trigger_analysis = True

#     st.rerun()


# # ==============================================================================
# # Layout

# left_col, right_col = st.columns([1, 3], gap="large")

            

# with left_col:
#     if st.session_state.uploaded_file:

#         if st.session_state.file_type == "image":
#             st.image(st.session_state.uploaded_file, use_container_width=True)
#         else:
#             st.video(st.session_state.uploaded_file)


#     progress_placeholder = st.empty()
#     status_placeholder = st.empty()

#     if st.session_state.is_analyzing:
#         progress_placeholder.progress(
#             st.session_state.progress_percent / 100
#         )
#         status_placeholder.markdown(
#             f"**{st.session_state.progress_step}**"
#         )
#     elif "start_time" in st.session_state and st.session_state.start_time is not None and st.session_state.is_analyzing is not True and st.session_state.is_analyzing is not 1:
#             elapsed_time = time.time() - st.session_state.start_time
#             elapsed_time_str = time.strftime("%H:%M:%S", time.gmtime(elapsed_time))  # Format as HH:MM:SS
#             st.markdown(f" ⏱️ Total Processing Time: {elapsed_time_str}")
#     else:
#         st.info("Select an image or video to begin")
    

# # ==============================================================================
# # Start analysis (only once)

# if st.session_state.trigger_analysis and not st.session_state.analysis_started:
#      # Start time for the analysis
#     st.session_state.start_time = time.time()

#     st.session_state.analysis_started = True
#     st.session_state.trigger_analysis = False
#     progress_bar = progress_placeholder.progress(0.0)
#     status_text = status_placeholder.empty()





#     try:
#         files = {"file": st.session_state.uploaded_file}
#         response = requests.post(BACKEND_UPLOAD, files=files)

#         if response.status_code == 200:

#             file_id = response.json()["file_name"]

#             msg_queue = queue.Queue()
#             st.session_state.ws_queue = msg_queue

#             thread = threading.Thread(
#            target=websocket_listener,
#              args=(
#               file_id,
#               st.session_state.file_type,
#               msg_queue,
#               st.session_state.enable_caption   # ✅ pass value
#     ),
#     daemon=True
# )
#             thread.start()

#             st.session_state.ws_thread = thread

#         else:
#             st.error(f"Upload failed ({response.status_code})")
#             st.session_state.is_analyzing = False

#     except Exception:
#         traceback.print_exc()
#         st.error("Connection failed")
#         st.session_state.is_analyzing = False

# # ==============================================================================
# # Process queue (runs every rerun)

# if st.session_state.ws_queue:

#     while not st.session_state.ws_queue.empty():
#         data = st.session_state.ws_queue.get()
        
#         if data["type"] == "progress":

#             st.session_state.show_results = True
#             st.session_state.progress_percent = data["percent"]
#             st.session_state.progress_step = data.get("step", "")

#             # progress_bar.progress(data["percent"] / 100)
#             # status_text.markdown(f"**{data.get('step','')}**")



#             if st.session_state.result is None:
#                 st.session_state.result = {}

#             incoming = data.get("other_data", {})

#             for k, v in incoming.items():
#                 if v is not None:
#                     st.session_state.result[k] = v

#         # elif data["type"] == "result":

#         #     st.session_state.result = data["data"]
#         #     st.session_state.progress_percent = 100
#         #     st.session_state.progress_step = "Completed"            
#         #     st.session_state.is_analyzing = False
#         #     st.session_state.show_results = True
#         elif data["type"] == "result":

#             st.session_state.result = data["data"]
#             st.session_state.progress_percent = 100
#             st.session_state.progress_step = "Completed"
#             st.session_state.show_results = True

#             st.session_state.is_analyzing = False
#             st.session_state.analysis_started = False
#             st.session_state.trigger_analysis = False
#             st.session_state.ws_thread = None
#             st.session_state.ws_queue = None

#             # ====
#                 # Calculate and display the total time spent on processing



#             st.rerun()   # 🔥 force UI refresh


#         elif data["type"] == "error":

#             st.error(data["message"])
#             st.session_state.is_analyzing = False

# # ==============================================================================
# # Results UI

# with right_col:
#     if st.session_state.show_results and st.session_state.result:

#         st.subheader("📊 Sensitivity Analysis Results")




# # ========

#         st.markdown("### 📄 Extracted Text")
#         st.text_area(
#             "Detected Content",
#             value=st.session_state.result.get("sequence", ""),
#             height=200
#         )

#         if "objects" in st.session_state.result:
#             st.markdown("### 🧠 Detected Objects")
#             st.write(", ".join(set(st.session_state.result["objects"])))

#         if "caption" in st.session_state.result:
#             st.markdown("### 📝 Scene / Context Caption")
#             st.write(st.session_state.result["caption"])

#         st.divider()
#         st.markdown("### 🔐 Sensitivity Classification")

#         for label, score in sorted(
#             zip(
#                 st.session_state.result.get("labels", []),
#                 st.session_state.result.get("scores", [])
#             ),
#             key=lambda x: x[1],
#             reverse=True
#         ):
#             c1, c2 = st.columns([5, 1])
#             with c1:
#                 st.write(f"**{label}**")
#                 st.progress(score)
#             with c2:
#                 st.write(f"**{round(score * 100, 2)}%**")

#         if "caption_image" in st.session_state.result:
#             img_bytes = base64.b64decode(
#                 st.session_state.result["caption_image"]
#             )
#             img = Image.open(io.BytesIO(img_bytes))
#             st.markdown("### 🖼️ Video Context Image")
#             st.image(img, use_container_width=True)

#         if "textSeg" in st.session_state.result:
#             st.markdown("### 🖍️ Highlighted Sensitive Text")

#             highlighted_html = highlight_text(
#                 st.session_state.result.get("text", ""),
#                 st.session_state.result.get("textSeg", [])
#             )

#             st.markdown(
# f"""<div style="
# line-height:1.8;
# font-size:18px;
# padding:14px;
# border:1px solid #333;
# border-radius:8px;
# background-color:#000000;
# color:#ffffff;
# white-space:pre-wrap;
# word-wrap:break-word;
# ">
# {highlighted_html}
# </div>""",
#                 unsafe_allow_html=True
#             )



# # ==============================================================================
# # Controlled polling loop

# if st.session_state.is_analyzing:
#     time.sleep(0.1)
#     st.rerun()