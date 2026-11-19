
import streamlit as st
import sqlite3
import pandas as pd
import zxingcpp

from PIL import Image
from io import BytesIO
from datetime import datetime

hide_streamlit_style = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)
# =====================================
# 1. APPLICATION CONFIGURATION
# =====================================

st.set_page_config(
    page_title="BioScan Intelligence",
    page_icon="🧬",
    layout="wide"
)

DB = "bioscan.db"


# =====================================
# 2. DATABASE MANAGEMENT
# =====================================

def connect():
    return sqlite3.connect(DB)


def initialize_database():

    with connect() as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                category TEXT,
                source TEXT,
                description TEXT,
                created_at TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS scan_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT,
                format TEXT,
                scan_date TEXT
            )
        """)


def add_sample(code, name, category, source, description):

    if not code.strip() or not name.strip():
        raise ValueError("Sample code and name are required.")

    with connect() as conn:

        conn.execute("""
            INSERT INTO samples
            (code, name, category, source, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            code.strip(),
            name.strip(),
            category,
            source,
            description,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))


def find_sample(code):

    with connect() as conn:

        result = conn.execute(
            "SELECT * FROM samples WHERE code = ?",
            (code.strip(),)
        ).fetchone()

    return result


def get_samples(search=""):

    with connect() as conn:

        return pd.read_sql_query("""
            SELECT * FROM samples
            WHERE code LIKE ?
            OR name LIKE ?
            OR category LIKE ?
            ORDER BY id DESC
        """, conn, params=(f"%{search}%",) * 3)


def record_scan(code, barcode_format):

    with connect() as conn:

        conn.execute("""
            INSERT INTO scan_history
            (code, format, scan_date)
            VALUES (?, ?, ?)
        """, (
            code,
            barcode_format,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))


# =====================================
# 3. QR AND BARCODE READER
# =====================================

def read_barcode(image_data):

    image = Image.open(
        BytesIO(image_data)
    ).convert("RGB")

    results = zxingcpp.read_barcodes(image)

    decoded = []

    for result in results:

        if result.text.strip():

            decoded.append({
                "code": result.text.strip(),
                "format": str(result.format)
            })

    return decoded


# =====================================
# 4. INITIALIZE
# =====================================

initialize_database()


# =====================================
# 5. SIDEBAR
# =====================================

st.sidebar.title("🧬 BioScan")

page = st.sidebar.radio(
    "MAIN MENU",
    [
        "Dashboard",
        "QR / Barcode Scanner",
        "Register Sample",
        "Biological Database",
        "Scan History",
        "About Project"
    ]
)


# =====================================
# 6. DASHBOARD
# =====================================

st.title("🧬 BioScan Intelligence")

st.caption(
    "Smart Biological Sample Identification System"
)

if page == "Dashboard":

    st.header("Research Dashboard")

    with connect() as conn:

        total_samples = conn.execute(
            "SELECT COUNT(*) FROM samples"
        ).fetchone()[0]

        total_scans = conn.execute(
            "SELECT COUNT(*) FROM scan_history"
        ).fetchone()[0]

    col1, col2 = st.columns(2)

    col1.metric(
        "Registered Samples",
        total_samples
    )

    col2.metric(
        "Total Scans",
        total_scans
    )

    st.divider()

    st.info(
        "Use the scanner to identify registered sample codes "
        "or register a new biological sample."
    )


# =====================================
# 7. QR / BARCODE SCANNER
# =====================================

elif page == "QR / Barcode Scanner":

    st.header("📷 Biological Sample Scanner")

    uploaded = st.file_uploader(
        "Upload QR / Barcode Image",
        type=["png", "jpg", "jpeg", "bmp", "webp"]
    )

    camera = st.camera_input(
        "Capture barcode using camera"
    )

    image_file = camera if camera is not None else uploaded

    if image_file:

        st.image(
            image_file,
            use_container_width=True
        )

        if st.button("SCAN NOW", type="primary"):

            try:

                results = read_barcode(
                    image_file.getvalue()
                )

                if not results:

                    st.warning(
                        "No QR Code or Barcode detected."
                    )

                for item in results:

                    code = item["code"]
                    barcode_format = item["format"]

                    record_scan(code, barcode_format)

                    st.success("Code detected successfully!")

                    st.write("Format:", barcode_format)

                    st.code(code)

                    sample = find_sample(code)

                    if sample:

                        st.subheader("Sample Information")

                        st.write("Sample Name:", sample[2])
                        st.write("Category:", sample[3])
                        st.write("Source:", sample[4])
                        st.write("Description:", sample[5])
                        st.write("Registration Date:", sample[6])

                    else:

                        st.warning(
                            "This code is not registered."
                        )

                        st.session_state["new_code"] = code

            except Exception as error:

                st.error(f"Scanner error: {error}")


# =====================================
# 8. REGISTER BIOLOGICAL SAMPLE
# =====================================

elif page == "Register Sample":

    st.header("➕ Register Biological Sample")

    with st.form("sample_registration"):

        code = st.text_input(
            "Sample Code",
            value=st.session_state.get("new_code", "")
        )

        name = st.text_input("Sample Name")

        category = st.selectbox(
            "Biological Category",
            [
                "Blood",
                "Urine",
                "Saliva",
                "Tissue",
                "Bacteria",
                "Fungi",
                "Plant",
                "Other"
            ]
        )

        source = st.text_input("Sample Source")

        description = st.text_area(
            "Scientific Description"
        )

        submit = st.form_submit_button(
            "REGISTER SAMPLE"
        )

        if submit:

            try:

                add_sample(
                    code,
                    name,
                    category,
                    source,
                    description
                )

                st.success(
                    "Sample registered successfully!"
                )

                st.session_state.pop("new_code", None)

            except sqlite3.IntegrityError:

                st.error(
                    "This sample code already exists."
                )

            except ValueError as error:

                st.error(str(error))


# =====================================
# 9. BIOLOGICAL DATABASE
# =====================================

elif page == "Biological Database":

    st.header("🧫 Biological Sample Database")

    search = st.text_input(
        "Search by code, name or category"
    )

    data = get_samples(search)

    st.dataframe(
        data,
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        f"Total matching records: {len(data)}"
    )


# =====================================
# 10. SCAN HISTORY
# =====================================

elif page == "Scan History":

    st.header("🕘 Scanner History")

    with connect() as conn:

        history = pd.read_sql_query("""
            SELECT * FROM scan_history
            ORDER BY id DESC
        """, conn)

    st.dataframe(
        history,
        use_container_width=True,
        hide_index=True
    )


# =====================================
# 11. ABOUT PROJECT
# =====================================

elif page == "About Project":

    st.header("About BioScan Intelligence")

    st.write("""
    BioScan Intelligence is a research prototype
    for biological sample identification and management.

    Main Features:

    1. QR Code Recognition
    2. Barcode Recognition
    3. Biological Sample Registration
    4. Sample Database
    5. Scan History
    6. Sample Information Retrieval

    Scientific Limitation:

    The scanner reads encoded identification data.
    It does not perform laboratory analysis,
    microorganism detection or medical diagnosis.
    """)

    st.info(
        "Developed using Python, Streamlit and Python libraries."
    )


# =====================================
# 12. FOOTER
# =====================================

st.divider()

st.caption(
    "BioScan Intelligence | Research Project | Version 1.0"
)
