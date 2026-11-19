import streamlit as st
import pandas as pd
import sqlite3
import requests
import qrcode
import io
from PIL import Image
from urllib.parse import quote

try:
    import zxingcpp
    SCANNER_AVAILABLE = True
except ImportError:
    SCANNER_AVAILABLE = False


# -------------------------------
# إعداد التطبيق
# -------------------------------

st.set_page_config(
    page_title="BioScan Intelligence",
    page_icon="🧬",
    layout="wide"
)

DB_NAME = "bioscan.db"


# -------------------------------
# قاعدة بيانات المركبات: 100 مركب
# -------------------------------

COMPOUNDS = {
    "Organic Chemistry": [
        "Methane", "Ethane", "Propane", "Butane",
        "Ethene", "Propene", "Ethyne", "Benzene",
        "Toluene", "Phenol", "Aniline", "Methanol",
        "Ethanol", "Propanol", "Acetone", "Formaldehyde",
        "Acetaldehyde", "Acetic acid", "Formic acid",
        "Benzoic acid", "Oxalic acid", "Citric acid",
        "Glucose", "Fructose", "Sucrose", "Lactose",
        "Starch", "Cellulose", "Urea", "Glycine",
        "Alanine", "Glycerol", "Ethyl acetate",
        "Chloroform", "Dichloromethane", "Naphthalene",
        "Cyclohexane", "Pyridine", "Aspirin", "Paracetamol"
    ],
    "Inorganic Chemistry": [
        "Water", "Sodium chloride", "Hydrochloric acid",
        "Sulfuric acid", "Nitric acid", "Phosphoric acid",
        "Sodium hydroxide", "Potassium hydroxide",
        "Calcium hydroxide", "Ammonia", "Sodium bicarbonate",
        "Sodium carbonate", "Calcium carbonate",
        "Magnesium sulfate", "Copper sulfate",
        "Iron(III) chloride", "Potassium permanganate",
        "Potassium dichromate", "Hydrogen peroxide",
        "Sodium nitrate", "Potassium nitrate",
        "Calcium chloride", "Silver nitrate",
        "Sodium phosphate", "Magnesium chloride",
        "Aluminum oxide", "Silicon dioxide",
        "Carbon dioxide", "Sulfur dioxide", "Oxygen"
    ],
    "Biochemistry": [
        "ATP", "ADP", "AMP", "DNA",
        "RNA", "Glycine", "Alanine", "Valine",
        "Leucine", "Lysine", "Glutamic acid",
        "Aspartic acid", "Serine", "Threonine",
        "Cysteine", "Methionine", "Tryptophan",
        "Tyrosine", "Phenylalanine", "Histidine",
        "Ribose", "Deoxyribose", "Cholesterol",
        "Palmitic acid", "Oleic acid", "Lactic acid",
        "Pyruvic acid", "Glycogen", "Maltose", "FAD"
    ]
}


# -------------------------------
# إنشاء الجداول
# -------------------------------

def connect_db():
    return sqlite3.connect(DB_NAME, check_same_thread=False)


def setup_database():
    conn = connect_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS compounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            category TEXT,
            formula TEXT,
            molecular_weight TEXT,
            smiles TEXT,
            cid TEXT,
            description TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sample_name TEXT,
            sample_code TEXT,
            notes TEXT
        )
    """)

    for category, names in COMPOUNDS.items():
        for name in names:
            cur.execute("""
                INSERT OR IGNORE INTO compounds
                (name, category)
                VALUES (?, ?)
            """, (name, category))

    conn.commit()
    conn.close()


setup_database()


# -------------------------------
# قراءة قاعدة البيانات
# -------------------------------

def get_compounds():
    conn = connect_db()
    df = pd.read_sql_query(
        "SELECT * FROM compounds ORDER BY category, name",
        conn
    )
    conn.close()
    return df


def get_compound(compound_id):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM compounds WHERE id = ?",
        (compound_id,)
    )
    result = cur.fetchone()
    conn.close()
    return result


# -------------------------------
# جلب بيانات PubChem
# -------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def get_pubchem_data(name):
    try:
        url = (
            "https://pubchem.ncbi.nlm.nih.gov/rest/pug/"
            f"compound/name/{quote(name)}/property/"
            "MolecularFormula,MolecularWeight,CanonicalSMILES,"
            "IUPACName/JSON"
        )

        response = requests.get(url, timeout=15)

        if response.status_code != 200:
            return None

        data = response.json()
        properties = data["PropertyTable"]["Properties"][0]

        cid = str(properties.get("CID", ""))

        return {
            "formula": properties.get("MolecularFormula", ""),
            "weight": str(properties.get("MolecularWeight", "")),
            "smiles": properties.get("ConnectivitySMILES", ""),
            "iupac": properties.get("IUPACName", ""),
            "cid": cid
        }

    except Exception:
        return None


def save_pubchem_data(compound_id, data):
    conn = connect_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE compounds
        SET formula = ?,
            molecular_weight = ?,
            smiles = ?,
            cid = ?,
            description = ?
        WHERE id = ?
    """, (
        data["formula"],
        data["weight"],
        data["smiles"],
        data["cid"],
        data["iupac"],
        compound_id
    ))

    conn.commit()
    conn.close()


# -------------------------------
# واجهة التطبيق
# -------------------------------

st.title("🧬 BioScan Intelligence")
st.caption("Educational Chemical & Biochemical Compound Platform")

st.divider()

page = st.radio(
    "القائمة الرئيسية",
    [
        "Dashboard",
        "Compound Database",
        "Compound Details",
        "Add Compound",
        "QR Generator",
        "QR / Barcode Scanner",
        "Import CSV",
        "Biological Samples"
    ],
    horizontal=False
)


# -------------------------------
# Dashboard
# -------------------------------

if page == "Dashboard":

    df = get_compounds()

    st.header("📊 Dashboard")

    col1, col2, col3 = st.columns(3)

    col1.metric("Total Compounds", len(df))
    col2.metric(
        "Organic",
        len(df[df["category"] == "Organic Chemistry"])
    )
    col3.metric(
        "Biochemistry",
        len(df[df["category"] == "Biochemistry"])
    )

    st.subheader("Compound Categories")

    category_counts = (
        df["category"].value_counts().reset_index()
    )
    category_counts.columns = ["Category", "Count"]

    st.bar_chart(
        category_counts.set_index("Category")
    )

    st.subheader("Recently Added Compounds")
    st.dataframe(
        df[["id", "name", "category", "formula"]].tail(10),
        use_container_width=True
    )


# -------------------------------
# قاعدة بيانات المركبات
# -------------------------------

elif page == "Compound Database":

    st.header("🧪 Chemical Compound Database")

    df = get_compounds()

    search = st.text_input(
        "ابحث باسم المركب أو الصيغة أو SMILES"
    )

    category = st.selectbox(
        "اختر القسم",
        [
            "All Categories",
            "Organic Chemistry",
            "Inorganic Chemistry",
            "Biochemistry"
        ]
    )

    if category != "All Categories":
        df = df[df["category"] == category]

    if search:
        mask = (
            df["name"].str.contains(search, case=False, na=False)
            | df["formula"].str.contains(search, case=False, na=False)
            | df["smiles"].str.contains(search, case=False, na=False)
        )
        df = df[mask]

    st.write(f"عدد النتائج: {len(df)}")

    st.dataframe(
        df[
            [
                "id", "name", "category",
                "formula", "molecular_weight"
            ]
        ],
        use_container_width=True,
        hide_index=True
    )


# -------------------------------
# تفاصيل المركب
# -------------------------------

elif page == "Compound Details":

    st.header("🔬 Compound Analysis")

    df = get_compounds()

    if len(df) == 0:
        st.warning("لا توجد مركبات.")
    else:
        selected = st.selectbox(
            "اختر المركب",
            df["id"].tolist(),
            format_func=lambda x: df.loc[
                df["id"] == x, "name"
            ].iloc[0]
        )

        compound = get_compound(selected)

        if compound:
            st.subheader(compound[1])
            st.write("**Category:**", compound[2])

            if st.button("جلب البيانات من PubChem"):
                with st.spinner("جاري البحث في PubChem..."):
                    data = get_pubchem_data(compound[1])

                if data:
                    save_pubchem_data(selected, data)
                    st.success("تم تحديث بيانات المركب.")
                    st.rerun()
                else:
                    st.error(
                        "لم يتم العثور على بيانات. "
                        "تحقق من الاتصال بالإنترنت أو اسم المركب."
                    )

            compound = get_compound(selected)

            st.divider()

            col1, col2 = st.columns(2)

            col1.metric(
                "Molecular Formula",
                compound[3] or "Not available"
            )

            col2.metric(
                "Molecular Weight",
                compound[4] or "Not available"
            )

            st.write("**SMILES:**")
            st.code(compound[5] or "Not available")

            st.write("**IUPAC Name:**")
            st.write(compound[7] or "Not available")

            if compound[6]:
                image_url = (
                    "https://pubchem.ncbi.nlm.nih.gov/rest/pug/"
                    f"compound/cid/{compound[6]}/PNG"
                )

                try:
                    image_response = requests.get(
                        image_url,
                        timeout=15
                    )

                    if image_response.status_code == 200:
                        st.image(
                            image_response.content,
                            caption="Chemical Structure",
                            width=300
                        )
                except Exception:
                    st.info("تعذر تحميل صورة التركيب الكيميائي.")


# -------------------------------
# إضافة مركب جديد
# -------------------------------

elif page == "Add Compound":

    st.header("➕ Add New Compound")

    with st.form("add_compound_form"):

        name = st.text_input("Compound Name")

        category = st.selectbox(
            "Category",
            [
                "Organic Chemistry",
                "Inorganic Chemistry",
                "Biochemistry"
            ]
        )

        formula = st.text_input("Molecular Formula")
        weight = st.text_input("Molecular Weight")
        smiles = st.text_input("SMILES")
        description = st.text_area("Description")

        submitted = st.form_submit_button("Save Compound")

        if submitted:
            if not name.strip():
                st.error("اكتب اسم المركب أولاً.")
            else:
                try:
                    conn = connect_db()
                    conn.execute("""
                        INSERT INTO compounds
                        (name, category, formula,
                         molecular_weight, smiles, description)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        name.strip(),
                        category,
                        formula,
                        weight,
                        smiles,
                        description
                    ))

                    conn.commit()
                    conn.close()

                    st.success("تمت إضافة المركب بنجاح.")
                    st.rerun()

                except sqlite3.IntegrityError:
                    st.error("هذا المركب موجود بالفعل.")


# -------------------------------
# QR Code Generator
# -------------------------------

elif page == "QR Generator":

    st.header("📱 Compound QR Generator")

    df = get_compounds()

    selected = st.selectbox(
        "اختر المركب",
        df["id"].tolist(),
        format_func=lambda x: df.loc[
            df["id"] == x, "name"
        ].iloc[0]
    )

    compound = get_compound(selected)

    if compound:
        qr_text = f"BIOSCAN:{compound[0]}"

        qr = qrcode.QRCode(
            version=1,
            box_size=10,
            border=4
        )

        qr.add_data(qr_text)
        qr.make(fit=True)

        qr_image = qr.make_image(
            fill_color="black",
            back_color="white"
        )

        buffer = io.BytesIO()
        qr_image.save(buffer, format="PNG")

        st.image(
            buffer.getvalue(),
            caption=compound[1],
            width=250
        )

        st.download_button(
            "Download QR Code",
            data=buffer.getvalue(),
            file_name=f"BioScan_{compound[0]}.png",
            mime="image/png"
        )


# -------------------------------
# QR / Barcode Scanner
# -------------------------------

elif page == "QR / Barcode Scanner":

    st.header("📷 QR / Barcode Scanner")

    uploaded = st.file_uploader(
        "ارفع صورة تحتوي على QR Code أو Barcode",
        type=["png", "jpg", "jpeg"]
    )

    if not SCANNER_AVAILABLE:
        st.warning(
            "مكتبة zxing-cpp غير متاحة حاليًا. "
            "يمكنك استخدام البحث اليدوي."
        )

    if uploaded and SCANNER_AVAILABLE:

        image = Image.open(uploaded).convert("RGB")
        st.image(image, caption="Uploaded Image", width=300)

        if st.button("Scan Code"):

            results = zxingcpp.read_barcodes(image)

            if not results:
                st.error("لم يتم العثور على رمز.")
            else:
                for result in results:
                    scanned_text = result.text

                    st.success(
                        f"تمت قراءة الرمز: {scanned_text}"
                    )

                    if scanned_text.startswith("BIOSCAN:"):
                        try:
                            compound_id = int(
                                scanned_text.split(":")[1]
                            )

                            compound = get_compound(compound_id)

                            if compound:
                                st.subheader(
                                    "المركب المرتبط بالرمز"
                                )
                                st.write("Name:", compound[1])
                                st.write("Category:", compound[2])
                                st.write(
                                    "Formula:",
                                    compound[3] or "Not available"
                                )
                            else:
                                st.warning(
                                    "هذا الرمز غير مسجل في قاعدة البيانات."
                                )

                        except ValueError:
                            st.error("صيغة الرمز غير صحيحة.")


# -------------------------------
# استيراد CSV
# -------------------------------

elif page == "Import CSV":

    st.header("📂 Import Compounds from CSV")

    st.write(
        "يجب أن يحتوي الملف على الأعمدة التالية: "
        "name, category, formula, molecular_weight, smiles"
    )

    uploaded_csv = st.file_uploader(
        "اختر ملف CSV",
        type=["csv"]
    )

    if uploaded_csv:

        try:
            csv_df = pd.read_csv(uploaded_csv)

            st.dataframe(
                csv_df.head(),
                use_container_width=True
            )

            if st.button("Import Data"):

                required = [
                    "name",
                    "category",
                    "formula",
                    "molecular_weight",
                    "smiles"
                ]

                if not all(
                    column in csv_df.columns
                    for column in required
                ):
                    st.error("الأعمدة المطلوبة غير مكتملة.")
                else:
                    conn = connect_db()

                    for _, row in csv_df.iterrows():
                        conn.execute("""
                            INSERT OR IGNORE INTO compounds
                            (name, category, formula,
                             molecular_weight, smiles)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            str(row["name"]),
                            str(row["category"]),
                            str(row["formula"]),
                            str(row["molecular_weight"]),
                            str(row["smiles"])
                        ))

                    conn.commit()
                    conn.close()

                    st.success("تم استيراد البيانات.")
                    st.rerun()

        except Exception as error:
            st.error(f"حدث خطأ في قراءة الملف: {error}")


# -------------------------------
# العينات البيولوجية
# -------------------------------

elif page == "Biological Samples":

    st.header("🦠 Biological Samples")

    with st.form("sample_form"):

        sample_name = st.text_input("Sample Name")
        sample_code = st.text_input("Sample Code")
        notes = st.text_area("Notes")

        save_sample = st.form_submit_button(
            "Register Sample"
        )

        if save_sample:

            if sample_name.strip() and sample_code.strip():

                conn = connect_db()

                conn.execute("""
                    INSERT INTO samples
                    (sample_name, sample_code, notes)
                    VALUES (?, ?, ?)
                """, (
                    sample_name,
                    sample_code,
                    notes
                ))

                conn.commit()
                conn.close()

                st.success("تم تسجيل العينة.")
                st.rerun()

            else:
                st.error("أدخل اسم العينة ورمزها.")

    conn = connect_db()

    samples_df = pd.read_sql_query(
        "SELECT * FROM samples ORDER BY id DESC",
        conn
    )

    conn.close()

    st.subheader("Registered Samples")
    st.dataframe(
        samples_df,
        use_container_width=True,
        hide_index=True
    )


# -------------------------------
# نهاية التطبيق
# -------------------------------

st.divider()

st.caption(
    "BioScan Intelligence | Educational Chemical Database"
    )
