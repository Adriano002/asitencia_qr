import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
import hashlib
import qrcode
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import numpy as np

# ===== CONFIGURACIÓN DE PÁGINA =====
st.set_page_config(
    page_title="Sistema de Asistencia",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===== CSS =====
st.markdown("""
<style>
    .stApp { background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); }
    div[data-testid="metric-container"] { background-color: white; padding: 15px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); transition: transform 0.3s; }
    div[data-testid="metric-container"]:hover { transform: translateY(-5px); }
    .stButton > button { background: linear-gradient(135deg, #f7971e 0%, #ffd200 100%); color: #333; border-radius: 12px; font-weight: 600; padding: 12px 24px; border: none; transition: all 0.3s; box-shadow: 0 4px 15px rgba(247, 151, 30, 0.4); }
    .stButton > button:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(247, 151, 30, 0.6); }
    .stButton > button[kind="primary"] { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); box-shadow: 0 4px 15px rgba(17, 153, 142, 0.4); color: white; }
    .stButton > button[kind="primary"]:hover { box-shadow: 0 6px 20px rgba(17, 153, 142, 0.6); }
    .css-1d391kg { background: linear-gradient(180deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%); }
    .css-1d391kg .css-1p05t8e { color: white; }
    .css-1d391kg .stRadio label { color: white !important; }
    h1 { font-weight: 700 !important; background: linear-gradient(135deg, #f7971e 0%, #ffd200 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; font-size: 2.5rem !important; }
    h2, h3 { font-weight: 700 !important; color: #1a1a2e !important; }
    .stDataFrame { border-radius: 15px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
    .streamlit-expanderHeader { background: linear-gradient(135deg, #f7971e 0%, #ffd200 100%); color: #333 !important; border-radius: 12px !important; font-weight: 600; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { border-radius: 12px 12px 0 0; padding: 12px 24px; background-color: #e8ecf1; font-weight: 600; transition: all 0.3s; }
    .stTabs [aria-selected="true"] { background: linear-gradient(135deg, #f7971e 0%, #ffd200 100%); color: #333 !important; }
    .stTextInput input, .stSelectbox div[data-baseweb="select"] { border-radius: 12px !important; border: 2px solid #e0e0e0 !important; transition: all 0.3s; }
    .stTextInput input:focus, .stSelectbox div[data-baseweb="select"]:focus { border-color: #f7971e !important; box-shadow: 0 0 0 3px rgba(247, 151, 30, 0.2) !important; }
    .stAlert { border-radius: 12px !important; border-left: 5px solid !important; }
    @media (max-width: 768px) { h1 { font-size: 1.8rem !important; } .stButton > button { width: 100% !important; } }
</style>
""", unsafe_allow_html=True)

# ============================================================
# AJUSTE DE HORA PARA PERÚ (UTC-5)
# ============================================================

def hora_peru():
    """Retorna la hora actual en Perú (UTC-5)"""
    from datetime import timezone
    utc_now = datetime.now(timezone.utc)
    peru_time = utc_now - timedelta(hours=5)
    return peru_time

def hoy_peru():
    """Retorna la fecha actual en Perú formato YYYY-MM-DD"""
    return hora_peru().strftime("%Y-%m-%d")

def hora_peru_str():
    """Retorna la hora actual en Perú formato HH:MM:SS"""
    return hora_peru().strftime("%H:%M:%S")

def es_dia_laboral_peru(fecha=None):
    """Verifica si hoy es día laboral en Perú (UTC-5)"""
    if fecha is None:
        fecha = hora_peru()
    return fecha.weekday() < 5

# ============================================================
# BASE DE DATOS
# ============================================================

def get_db():
    conn = sqlite3.connect("asistencia.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    c.execute("""CREATE TABLE IF NOT EXISTS turnos (
        id INTEGER PRIMARY KEY, nombre TEXT UNIQUE)""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS grados (
        id INTEGER PRIMARY KEY, nombre TEXT)""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS secciones (
        id INTEGER PRIMARY KEY, nombre TEXT, grado_id INTEGER, turno_id INTEGER,
        FOREIGN KEY (grado_id) REFERENCES grados(id),
        FOREIGN KEY (turno_id) REFERENCES turnos(id))""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS alumnos (
        id INTEGER PRIMARY KEY, dni TEXT UNIQUE, nombres TEXT,
        apellido_paterno TEXT, apellido_materno TEXT, seccion_id INTEGER,
        FOREIGN KEY (seccion_id) REFERENCES secciones(id))""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS asistencias (
        id INTEGER PRIMARY KEY, alumno_id INTEGER, fecha TEXT,
        hora TEXT, estado TEXT,
        FOREIGN KEY (alumno_id) REFERENCES alumnos(id),
        UNIQUE(alumno_id, fecha))""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS dias_especiales (
        id INTEGER PRIMARY KEY, fecha TEXT UNIQUE, descripcion TEXT,
        hora_entrada TEXT, activo INTEGER DEFAULT 1)""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY, usuario TEXT UNIQUE, password TEXT,
        rol TEXT, nombres TEXT, turno_asignado TEXT)""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS auditoria (
        id INTEGER PRIMARY KEY, usuario TEXT, accion TEXT, fecha TEXT)""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS config_horarios (
        id INTEGER PRIMARY KEY, turno_id INTEGER, hora_entrada TEXT,
        hora_limite TEXT, FOREIGN KEY (turno_id) REFERENCES turnos(id))""")
    
    c.execute("PRAGMA table_info(usuarios)")
    columnas = [col['name'] for col in c.fetchall()]
    if 'turno_asignado' not in columnas:
        c.execute("ALTER TABLE usuarios ADD COLUMN turno_asignado TEXT")
    
    if c.execute("SELECT COUNT(*) as c FROM turnos").fetchone()['c'] == 0:
        c.execute("INSERT INTO turnos (nombre) VALUES ('Mañana')")
        c.execute("INSERT INTO turnos (nombre) VALUES ('Tarde')")
        c.execute("INSERT INTO config_horarios (turno_id, hora_entrada, hora_limite) VALUES (1, '08:00', '08:15')")
        c.execute("INSERT INTO config_horarios (turno_id, hora_entrada, hora_limite) VALUES (2, '13:30', '13:45')")
    
    if c.execute("SELECT COUNT(*) as c FROM usuarios").fetchone()['c'] == 0:
        admin_hash = hashlib.sha256("admin2026".encode()).hexdigest()
        c.execute("INSERT INTO usuarios (usuario, password, rol, nombres, turno_asignado) VALUES ('admin', ?, 'Admin', 'Administrador', '')", (admin_hash,))
        puerta_hash = hashlib.sha256("puerta2026".encode()).hexdigest()
        c.execute("INSERT INTO usuarios (usuario, password, rol, nombres, turno_asignado) VALUES ('puerta', ?, 'Auxiliar', 'Auxiliar Puerta', 'Mañana')", (puerta_hash,))
    
    conn.commit()
    conn.close()

init_db()

# ============================================================
# FUNCIONES DE UTILIDAD
# ============================================================

def registrar_auditoria(usuario, accion):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO auditoria (usuario, accion, fecha) VALUES (?, ?, ?)",
                  (usuario, accion, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
    except:
        pass

def obtener_config_horario(turno_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT hora_entrada, hora_limite FROM config_horarios WHERE turno_id = ?", (turno_id,))
    r = c.fetchone()
    conn.close()
    if r:
        return {'entrada': r['hora_entrada'], 'limite': r['hora_limite']}
    return {'entrada': '08:00', 'limite': '08:15'}

def es_dia_especial(fecha=None):
    if fecha is None:
        fecha = hora_peru().strftime("%Y-%m-%d")
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM dias_especiales WHERE fecha = ? AND activo = 1", (fecha,))
    existe = c.fetchone()
    conn.close()
    return existe is not None

def se_toma_asistencia(fecha=None):
    if fecha is None:
        fecha = hora_peru()
    if es_dia_especial(fecha.strftime("%Y-%m-%d")):
        return True
    return es_dia_laboral_peru(fecha)

def obtener_config_con_dia_especial(turno_id):
    hoy = hora_peru().strftime("%Y-%m-%d")
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT hora_entrada FROM dias_especiales WHERE fecha = ? AND activo = 1", (hoy,))
    especial = c.fetchone()
    if especial:
        conn.close()
        hora_entrada = especial['hora_entrada']
        hora_limite = (datetime.strptime(hora_entrada, "%H:%M") + timedelta(minutes=15)).strftime("%H:%M")
        return {'entrada': hora_entrada, 'limite': hora_limite}
    return obtener_config_horario(turno_id)

# ============================================================
# FUNCIONES DE NEGOCIO
# ============================================================

def importar_alumnos_excel(df, mapeo):
    conn = get_db()
    c = conn.cursor()
    exitos = 0
    errores = []
    secciones_creadas = []
    
    turnos = {row['nombre']: row['id'] for row in c.execute("SELECT id, nombre FROM turnos").fetchall()}
    
    for index, row in df.iterrows():
        try:
            dni = str(row[mapeo['dni']]).strip()
            nombres = str(row[mapeo['nombres']]).strip()
            apellido_paterno = str(row[mapeo['apellido_paterno']]).strip()
            apellido_materno = str(row.get(mapeo.get('apellido_materno', ''), '')).strip() if 'apellido_materno' in mapeo else ""
            grado_nombre = str(row[mapeo['grado']]).strip()
            seccion_nombre = str(row[mapeo['seccion']]).strip()
            
            if 'turno' not in mapeo or not mapeo['turno']:
                errores.append(f"Fila {index + 2}: No se seleccionó columna de Turno")
                continue
            
            turno_valor = str(row[mapeo['turno']]).lower().strip()
            if turno_valor in ['tarde', 't', 'tm']:
                turno = 'Tarde'
            elif turno_valor in ['mañana', 'manana', 'm', 'am']:
                turno = 'Mañana'
            else:
                errores.append(f"Fila {index + 2}: Turno '{turno_valor}' no válido (use Mañana o Tarde)")
                continue
            
            grado = c.execute("SELECT id FROM grados WHERE nombre = ?", (grado_nombre,)).fetchone()
            if not grado:
                c.execute("INSERT INTO grados (nombre) VALUES (?)", (grado_nombre,))
                grado_id = c.lastrowid
            else:
                grado_id = grado['id']
            
            turno_id = turnos.get(turno)
            if not turno_id:
                errores.append(f"Fila {index + 2}: Turno '{turno}' no encontrado en la base de datos")
                continue
            
            seccion = c.execute("SELECT id FROM secciones WHERE nombre = ? AND grado_id = ? AND turno_id = ?",
                               (seccion_nombre, grado_id, turno_id)).fetchone()
            if not seccion:
                c.execute("INSERT INTO secciones (nombre, grado_id, turno_id) VALUES (?, ?, ?)",
                         (seccion_nombre, grado_id, turno_id))
                seccion_id = c.lastrowid
                secciones_creadas.append(f"{grado_nombre}{seccion_nombre}")
            else:
                seccion_id = seccion['id']
            
            c.execute("INSERT OR IGNORE INTO alumnos (dni, nombres, apellido_paterno, apellido_materno, seccion_id) VALUES (?, ?, ?, ?, ?)",
                     (dni, nombres, apellido_paterno, apellido_materno, seccion_id))
            if c.rowcount > 0:
                exitos += 1
        except Exception as e:
            errores.append(f"Fila {index + 2}: {str(e)}")
    
    conn.commit()
    conn.close()
    return exitos, errores, secciones_creadas

def generar_qr_para_alumno(dni):
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(dni)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white")

def generar_pdf_carnets(seccion_id):
    conn = get_db()
    c = conn.cursor()
    alumnos = c.execute("""
        SELECT a.*, s.nombre as seccion, g.nombre as grado, t.nombre as turno
        FROM alumnos a JOIN secciones s ON a.seccion_id = s.id
        JOIN grados g ON s.grado_id = g.id JOIN turnos t ON s.turno_id = t.id
        WHERE a.seccion_id = ?
        ORDER BY a.apellido_paterno
    """, (seccion_id,)).fetchall()
    conn.close()
    if not alumnos: return None
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=15, leftMargin=15, topMargin=15, bottomMargin=15)
    elementos = []
    estilos = getSampleStyleSheet()
    elementos.append(Paragraph(f"Carnets - {alumnos[0]['grado']}{alumnos[0]['seccion']} - {alumnos[0]['turno']}", estilos['Heading1']))
    elementos.append(Spacer(1, 20))
    
    for i in range(0, len(alumnos), 6):
        lote = alumnos[i:i+6]
        tabla_data = []
        for j in range(0, len(lote), 3):
            fila = lote[j:j+3]
            fila_actual = []
            for alumno in fila:
                qr_img = generar_qr_para_alumno(alumno['dni'])
                img_bytes = BytesIO()
                qr_img.save(img_bytes, format='PNG')
                img_bytes.seek(0)
                from reportlab.platypus import Image as RLImage
                fila_actual.append([
                    Paragraph(f"<b>{alumno['apellido_paterno']} {alumno['apellido_materno']}</b>", estilos['Normal']),
                    Paragraph(alumno['nombres'], estilos['Normal']),
                    Paragraph(f"DNI: {alumno['dni']}", estilos['Normal']),
                    Paragraph(f"{alumno['grado']}{alumno['seccion']} - {alumno['turno']}", estilos['Normal']),
                    RLImage(img_bytes, width=60, height=60)
                ])
            while len(fila_actual) < 3:
                fila_actual.append([])
            tabla_data.append(fila_actual)
        
        if tabla_data:
            tabla = Table(tabla_data, colWidths=[180, 180, 180], rowHeights=[150]*len(tabla_data))
            tabla.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BOX', (0,0), (-1,-1), 1, colors.black),
                ('INNERGRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('TOPPADDING', (0,0), (-1,-1), 10),
                ('BOTTOMPADDING', (0,0), (-1,-1), 10),
            ]))
            elementos.append(tabla)
            if i + 6 < len(alumnos):
                elementos.append(PageBreak())
    
    doc.build(elementos)
    buffer.seek(0)
    return buffer.getvalue()

def registrar_asistencia_rapida(dni, usuario=None):
    if not dni or len(dni) != 8 or not dni.isdigit():
        return False, "❌ DNI inválido (8 dígitos)"
    
    hoy_dt = hora_peru()
    hoy = hoy_dt.strftime("%Y-%m-%d")
    
    if not se_toma_asistencia(hoy_dt):
        if es_dia_especial(hoy_dt.strftime("%Y-%m-%d")):
            return False, "❌ Hoy es día especial pero no está configurado correctamente"
        else:
            return False, "❌ Hoy no es día laboral (solo se toma asistencia de lunes a viernes)"
    
    conn = get_db()
    c = conn.cursor()
    
    alumno = c.execute("""
        SELECT a.id, a.nombres, a.apellido_paterno, a.apellido_materno,
               s.nombre as seccion, g.nombre as grado, t.nombre as turno, t.id as turno_id
        FROM alumnos a 
        JOIN secciones s ON a.seccion_id = s.id
        JOIN grados g ON s.grado_id = g.id
        JOIN turnos t ON s.turno_id = t.id
        WHERE a.dni = ?
    """, (dni,)).fetchone()
    
    if not alumno:
        conn.close()
        return False, "❌ DNI no encontrado"
    
    if usuario:
        user = c.execute("SELECT turno_asignado FROM usuarios WHERE usuario = ?", (usuario,)).fetchone()
        if user and user['turno_asignado']:
            if alumno['turno'] != user['turno_asignado']:
                conn.close()
                return False, f"❌ Este alumno es del turno {alumno['turno']}, tu turno es {user['turno_asignado']}"
    
    hora = hora_peru_str()
    
    if c.execute("SELECT id FROM asistencias WHERE alumno_id = ? AND fecha = ?", (alumno['id'], hoy)).fetchone():
        conn.close()
        return False, f"⚠️ Ya registró: {alumno['apellido_paterno']} {alumno['nombres']}"
    
    config = obtener_config_con_dia_especial(alumno['turno_id'])
    estado = "Puntual" if hora <= config['limite'] else "Tardanza"
    
    c.execute("INSERT INTO asistencias (alumno_id, fecha, hora, estado) VALUES (?, ?, ?, ?)",
             (alumno['id'], hoy, hora, estado))
    conn.commit()
    conn.close()
    
    registrar_auditoria(st.session_state.get('usuario', 'sistema'), f"Registro DNI {dni} - {estado}")
    nombre = f"{alumno['apellido_paterno']} {alumno['apellido_materno']}, {alumno['nombres']}"
    return True, f"✅ {nombre} | {alumno['grado']}{alumno['seccion']} | {estado} | {hora}"

def marcar_faltas_automaticas():
    hoy_dt = hora_peru()
    if not se_toma_asistencia(hoy_dt):
        return
    
    conn = get_db()
    c = conn.cursor()
    hoy = hoy_dt.strftime("%Y-%m-%d")
    hora = hoy_dt.strftime("%H:%M:%S")
    
    for turno in c.execute("SELECT id FROM turnos").fetchall():
        config = obtener_config_con_dia_especial(turno['id'])
        if hora > config['entrada']:
            c.execute("""
                INSERT OR IGNORE INTO asistencias (alumno_id, fecha, hora, estado)
                SELECT a.id, ?, ?, 'Falta' FROM alumnos a
                JOIN secciones s ON a.seccion_id = s.id
                WHERE s.turno_id = ? 
                AND a.id NOT IN (SELECT alumno_id FROM asistencias WHERE fecha = ?)
            """, (hoy, hora, turno['id'], hoy))
    conn.commit()
    conn.close()

def generar_pdf_reporte(df, titulo):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elementos = []
    estilos = getSampleStyleSheet()
    
    elementos.append(Paragraph(titulo, estilos['Heading1']))
    elementos.append(Spacer(1, 20))
    
    if not df.empty:
        data = [df.columns.tolist()] + df.values.tolist()
        tabla = Table(data)
        tabla.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('FONTSIZE', (0, 1), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elementos.append(tabla)
    
    doc.build(elementos)
    buffer.seek(0)
    return buffer.getvalue()

def color_estado(val):
    if val == 'Puntual':
        return 'background-color: #d4edda; color: #155724; font-weight: bold;'
    elif val == 'Tardanza':
        return 'background-color: #fff3cd; color: #856404; font-weight: bold;'
    elif val == 'Falta':
        return 'background-color: #f8d7da; color: #721c24; font-weight: bold;'
    return ''

# ============================================================
# FUNCIÓN PARA LEER QR CON QREADER
# ============================================================

def leer_qr_con_qreader(img):
    """Lee un código QR desde una imagen usando qreader"""
    try:
        from qreader import QReader
        import cv2
        import numpy as np
        
        # Convertir PIL a numpy array
        if hasattr(img, 'convert'):
            img_array = np.array(img)
        else:
            img_array = img
        
        # qreader acepta imágenes en formato BGR o RGB
        # Si la imagen tiene 3 canales (RGB), convertir a BGR para cv2
        if len(img_array.shape) == 3 and img_array.shape[2] == 3:
            img_cv2 = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        else:
            img_cv2 = img_array
        
        qreader = QReader()
        decoded_text = qreader.detect_and_decode(image=img_cv2)
        
        if decoded_text and len(decoded_text) > 0:
            return decoded_text[0].strip()
        return None
    except Exception as e:
        st.error(f"❌ Error en qreader: {str(e)}")
        return None

# ============================================================
# VISTAS
# ============================================================

def login():
    st.title("📚 Sistema de Asistencia")
    st.markdown("---")
    with st.form("login"):
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.image("https://img.icons8.com/color/96/000000/student-center.png", width=100)
            usuario = st.text_input("👤 Usuario", placeholder="Ingrese su usuario")
            password = st.text_input("🔒 Contraseña", type="password", placeholder="Ingrese su contraseña")
            if st.form_submit_button("🚪 Ingresar", type="primary", use_container_width=True):
                conn = get_db()
                c = conn.cursor()
                password_hash = hashlib.sha256(password.encode()).hexdigest()
                user = c.execute("SELECT * FROM usuarios WHERE usuario = ? AND password = ?", (usuario, password_hash)).fetchone()
                conn.close()
                if user:
                    st.session_state.autenticado = True
                    st.session_state.usuario = user['usuario']
                    st.session_state.rol = user['rol']
                    st.session_state.nombres = user['nombres']
                    st.session_state.turno_asignado = user['turno_asignado'] if user['turno_asignado'] else None
                    st.session_state.login_time = datetime.now().isoformat()
                    registrar_auditoria(usuario, "Inicio de sesión")
                    st.rerun()
                else:
                    st.error("❌ Credenciales incorrectas")

def menu():
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/000000/student-center.png", width=80)
        st.write(f"**👤 {st.session_state.nombres}**")
        st.write(f"**Rol:** {st.session_state.rol}")
        if st.session_state.turno_asignado:
            st.write(f"**Turno:** {st.session_state.turno_asignado}")
        st.markdown("---")
        
        if st.session_state.rol == "Admin":
            opciones = ["🚪 Puerta de Entrada", "📥 Importar Excel", "👥 Gestionar Alumnos", 
                       "📚 Gestionar Secciones", "📊 Reportes", "🪪 Carnets", "📅 Días Especiales",
                       "👤 Usuarios", "📋 Auditoría", "⏰ Horarios"]
        elif st.session_state.rol == "Coordinador":
            opciones = ["🚪 Puerta de Entrada", "📊 Reportes", "🪪 Carnets", "📅 Días Especiales", "⏰ Horarios"]
        else:
            opciones = ["🚪 Puerta de Entrada", "📊 Reportes"]
        
        opcion = st.radio("📋 Menú", opciones)
        st.markdown("---")
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            registrar_auditoria(st.session_state.usuario, "Cierre de sesión")
            st.session_state.autenticado = False
            st.rerun()
    return opcion

# ============================================================
# VISTA PUERTA (CON QR MEJORADO)
# ============================================================

def vista_puerta():
    st.title("🚪 Control de Puerta")
    
    hoy = hora_peru().strftime("%Y-%m-%d")
    hoy_dt = hora_peru()
    dia_semana = hoy_dt.weekday()
    
    conn = get_db()
    c = conn.cursor()
    hoy_especial = c.execute("SELECT * FROM dias_especiales WHERE fecha = ? AND activo = 1", (hoy,)).fetchone()
    conn.close()
    
    es_dia_laboral = dia_semana < 5
    toma_asistencia = es_dia_laboral or hoy_especial is not None
    
    if hoy_especial:
        st.success(f"🎉 **HOY ES DÍA ESPECIAL!** {hoy_especial['descripcion']} (Entrada: {hoy_especial['hora_entrada']})")
    elif es_dia_laboral:
        st.info("📅 **DÍA LABORAL** - Se toma asistencia")
    else:
        st.warning("⛔ **FIN DE SEMANA** - No se toma asistencia")
        st.caption("Los sábados y domingos no se registra asistencia")
        return
    
    marcar_faltas_automaticas()
    
    conn = get_db()
    c = conn.cursor()
    total = c.execute("SELECT COUNT(*) as t FROM alumnos").fetchone()['t']
    puntuales = c.execute("SELECT COUNT(*) as t FROM asistencias WHERE fecha=? AND estado='Puntual'", (hoy,)).fetchone()['t']
    tardanzas = c.execute("SELECT COUNT(*) as t FROM asistencias WHERE fecha=? AND estado='Tardanza'", (hoy,)).fetchone()['t']
    faltas = c.execute("SELECT COUNT(*) as t FROM asistencias WHERE fecha=? AND estado='Falta'", (hoy,)).fetchone()['t']
    conn.close()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #f7971e 0%, #ffd200 100%); 
                    padding: 20px; border-radius: 15px; text-align: center;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
            <h2 style="font-size: 32px; margin: 0; color: #1a1a2e;">{total}</h2>
            <p style="margin: 0; color: #1a1a2e;">📚 Total Alumnos</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); 
                    padding: 20px; border-radius: 15px; text-align: center;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
            <h2 style="font-size: 32px; margin: 0; color: #1a1a2e;">{puntuales}</h2>
            <p style="margin: 0; color: #1a1a2e;">✅ Puntuales</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #f7971e 0%, #ffd200 100%); 
                    padding: 20px; border-radius: 15px; text-align: center;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
            <h2 style="font-size: 32px; margin: 0; color: #1a1a2e;">{tardanzas}</h2>
            <p style="margin: 0; color: #1a1a2e;">🟡 Tardanzas</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%); 
                    padding: 20px; border-radius: 15px; text-align: center;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
            <h2 style="font-size: 32px; margin: 0; color: #FFFFFF;">{faltas}</h2>
            <p style="margin: 0; color: #FFFFFF;">🔴 Faltas</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    metodo = st.radio("Método:", ["📷 Escanear QR", "👥 Seleccionar Estudiante"], horizontal=True)
    
    if metodo == "📷 Escanear QR":
        st.info("📷 El estudiante muestra su QR - Registro instantáneo")
        
        img_file = st.camera_input("Escanear QR", key="camara_qr", label_visibility="collapsed")
        
        if img_file:
            try:
                from PIL import Image as PILImage
                
                img = PILImage.open(BytesIO(img_file.getvalue()))
                
                # ===== INTENTAR LEER QR =====
                dni = leer_qr_con_qreader(img)
                
                if dni:
                    st.write(f"📌 DNI detectado: **{dni}**")
                    
                    exito, msg = registrar_asistencia_rapida(dni, st.session_state.usuario)
                    if exito:
                        st.success(msg)
                        st.balloons()
                    else:
                        st.error(msg)
                else:
                    st.error("❌ QR NO DETECTADO")
                    st.warning("📌 Consejos:")
                    st.write("- Asegúrate de que el QR esté bien enfocado")
                    st.write("- Prueba con mejor iluminación")
                    st.write("- El QR debe contener solo el DNI (8 dígitos)")
                    st.image(img, caption="Imagen capturada", width=200)
                    
                    # ===== OPCIÓN MANUAL =====
                    st.markdown("---")
                    st.subheader("📝 Ingresar DNI manual")
                    dni_manual = st.text_input("DNI (8 dígitos)", max_chars=8, placeholder="12345678")
                    if st.button("✅ Registrar manual", type="primary", use_container_width=True):
                        if dni_manual and len(dni_manual) == 8 and dni_manual.isdigit():
                            exito, msg = registrar_asistencia_rapida(dni_manual.strip(), st.session_state.usuario)
                            if exito:
                                st.success(msg)
                                st.balloons()
                            else:
                                st.error(msg)
                        else:
                            st.warning("❌ Ingresa un DNI válido de 8 dígitos")
                            
            except Exception as e:
                st.error(f"❌ Error al procesar la imagen: {str(e)}")
    
    else:
        st.info("👥 Seleccione grado y sección")
        
        col1, col2 = st.columns(2)
        with col1:
            conn = get_db()
            if st.session_state.rol == "Auxiliar" and st.session_state.turno_asignado:
                grados = pd.read_sql("""SELECT DISTINCT g.nombre FROM grados g
                    JOIN secciones s ON s.grado_id = g.id
                    JOIN turnos t ON s.turno_id = t.id
                    WHERE t.nombre = ? ORDER BY g.nombre""", conn, params=[st.session_state.turno_asignado])
            else:
                grados = pd.read_sql("SELECT DISTINCT nombre FROM grados ORDER BY nombre", conn)
            conn.close()
            grado_sel = st.selectbox("Grado:", grados['nombre'].tolist())
        
        with col2:
            conn = get_db()
            if st.session_state.rol == "Auxiliar" and st.session_state.turno_asignado:
                secciones = pd.read_sql("""SELECT DISTINCT s.nombre FROM secciones s
                    JOIN grados g ON s.grado_id = g.id
                    JOIN turnos t ON s.turno_id = t.id
                    WHERE g.nombre = ? AND t.nombre = ? ORDER BY s.nombre""", conn, params=[grado_sel, st.session_state.turno_asignado])
            else:
                secciones = pd.read_sql("""SELECT DISTINCT s.nombre FROM secciones s
                    JOIN grados g ON s.grado_id = g.id
                    WHERE g.nombre = ? ORDER BY s.nombre""", conn, params=[grado_sel])
            conn.close()
            seccion_sel = st.selectbox("Sección:", secciones['nombre'].tolist())
        
        conn = get_db()
        alumnos = pd.read_sql("""
            SELECT a.dni, a.nombres, a.apellido_paterno, a.apellido_materno,
                   ast.estado as estado_reg
            FROM alumnos a
            JOIN secciones s ON a.seccion_id = s.id
            JOIN grados g ON s.grado_id = g.id
            LEFT JOIN asistencias ast ON a.id = ast.alumno_id AND ast.fecha = ?
            WHERE g.nombre = ? AND s.nombre = ?
            ORDER BY a.apellido_paterno
        """, conn, params=[hoy, grado_sel, seccion_sel])
        conn.close()
        
        st.write(f"**{len(alumnos)} estudiantes**")
        
        for i in range(0, len(alumnos), 2):
            col1, col2 = st.columns(2)
            
            if i < len(alumnos):
                alumno = alumnos.iloc[i]
                with col1:
                    estado = alumno['estado_reg'] if alumno['estado_reg'] else "⚪ Sin registrar"
                    if alumno['estado_reg'] == 'Puntual':
                        st.markdown(f"🟢 **{alumno['apellido_paterno']} {alumno['apellido_materno']}, {alumno['nombres']}**")
                        st.markdown(f"<span style='color:green;font-weight:bold;'>✅ {estado}</span>", unsafe_allow_html=True)
                    elif alumno['estado_reg'] == 'Tardanza':
                        st.markdown(f"🟡 **{alumno['apellido_paterno']} {alumno['apellido_materno']}, {alumno['nombres']}**")
                        st.markdown(f"<span style='color:#f7971e;font-weight:bold;'>🟡 {estado}</span>", unsafe_allow_html=True)
                    elif alumno['estado_reg'] == 'Falta':
                        st.markdown(f"🔴 **{alumno['apellido_paterno']} {alumno['apellido_materno']}, {alumno['nombres']}**")
                        st.markdown(f"<span style='color:red;font-weight:bold;'>🔴 {estado}</span>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"**{alumno['apellido_paterno']} {alumno['apellido_materno']}, {alumno['nombres']}**")
                        st.write(estado)
                    
                    if not alumno['estado_reg']:
                        if st.button("✅ Marcar", key=f"btn_{alumno['dni']}", use_container_width=True):
                            exito, msg = registrar_asistencia_rapida(alumno['dni'], st.session_state.usuario)
                            if exito:
                                st.success(msg)
                            else:
                                st.error(msg)
            
            if i + 1 < len(alumnos):
                alumno2 = alumnos.iloc[i + 1]
                with col2:
                    estado2 = alumno2['estado_reg'] if alumno2['estado_reg'] else "⚪ Sin registrar"
                    if alumno2['estado_reg'] == 'Puntual':
                        st.markdown(f"🟢 **{alumno2['apellido_paterno']} {alumno2['apellido_materno']}, {alumno2['nombres']}**")
                        st.markdown(f"<span style='color:green;font-weight:bold;'>✅ {estado2}</span>", unsafe_allow_html=True)
                    elif alumno2['estado_reg'] == 'Tardanza':
                        st.markdown(f"🟡 **{alumno2['apellido_paterno']} {alumno2['apellido_materno']}, {alumno2['nombres']}**")
                        st.markdown(f"<span style='color:#f7971e;font-weight:bold;'>🟡 {estado2}</span>", unsafe_allow_html=True)
                    elif alumno2['estado_reg'] == 'Falta':
                        st.markdown(f"🔴 **{alumno2['apellido_paterno']} {alumno2['apellido_materno']}, {alumno2['nombres']}**")
                        st.markdown(f"<span style='color:red;font-weight:bold;'>🔴 {estado2}</span>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"**{alumno2['apellido_paterno']} {alumno2['apellido_materno']}, {alumno2['nombres']}**")
                        st.write(estado2)
                    
                    if not alumno2['estado_reg']:
                        if st.button("✅ Marcar", key=f"btn_{alumno2['dni']}", use_container_width=True):
                            exito, msg = registrar_asistencia_rapida(alumno2['dni'], st.session_state.usuario)
                            if exito:
                                st.success(msg)
                            else:
                                st.error(msg)
    
    st.markdown("---")
    st.subheader("📋 Últimos 10 registros")
    conn = get_db()
    df = pd.read_sql("""
        SELECT a.apellido_paterno, a.apellido_materno, a.nombres,
               g.nombre as grado, s.nombre as seccion, ast.hora, ast.estado
        FROM asistencias ast JOIN alumnos a ON ast.alumno_id = a.id
        JOIN secciones s ON a.seccion_id = s.id JOIN grados g ON s.grado_id = g.id
        WHERE ast.fecha = ? ORDER BY ast.hora DESC LIMIT 10
    """, conn, params=[hoy])
    conn.close()
    
    if not df.empty:
        st.dataframe(df.style.map(color_estado, subset=['estado']), use_container_width=True)
    else:
        st.info("No hay registros hoy")

# ============================================================
# VISTA IMPORTAR
# ============================================================

def vista_importar():
    if st.session_state.rol != "Admin":
        st.error("❌ No tienes permiso para importar alumnos")
        return
    
    st.title("📥 Importar Alumnos desde Excel")
    st.info("⚠️ El archivo Excel DEBE tener una columna con el Turno (Mañana o Tarde)")
    
    archivo = st.file_uploader("Subir Excel", type=['xlsx', 'xls'])
    
    if archivo:
        df = pd.read_excel(archivo)
        st.write(f"📊 Alumnos encontrados: {len(df)}")
        st.dataframe(df.head(5), use_container_width=True)
        
        st.markdown("---")
        st.subheader("📋 Mapeo de Columnas")
        
        col1, col2 = st.columns(2)
        with col1:
            mapeo = {}
            mapeo['dni'] = st.selectbox("DNI *", df.columns)
            mapeo['nombres'] = st.selectbox("Nombres *", df.columns)
            mapeo['apellido_paterno'] = st.selectbox("Apellido Paterno *", df.columns)
        with col2:
            mapeo['apellido_materno'] = st.selectbox("Apellido Materno", [''] + list(df.columns))
            mapeo['grado'] = st.selectbox("Grado *", df.columns)
            mapeo['seccion'] = st.selectbox("Sección *", df.columns)
            mapeo['turno'] = st.selectbox("Turno * (Mañana/Tarde)", df.columns)
        
        if st.button("🚀 Importar Alumnos", type="primary", use_container_width=True):
            campos_requeridos = ['dni', 'nombres', 'apellido_paterno', 'grado', 'seccion', 'turno']
            faltantes = [campo for campo in campos_requeridos if not mapeo.get(campo)]
            
            if faltantes:
                st.error(f"❌ Faltan seleccionar: {', '.join(faltantes)}")
            else:
                with st.spinner("Importando..."):
                    exitos, errores, secciones = importar_alumnos_excel(df, mapeo)
                    st.success(f"✅ Importados: {exitos}")
                    if secciones:
                        st.info(f"📚 Secciones creadas: {', '.join(secciones[:20])}")
                    if errores:
                        with st.expander(f"⚠️ Errores ({len(errores)})"):
                            for e in errores[:50]:
                                st.write(f"• {e}")

# ============================================================
# VISTA GESTIONAR ALUMNOS
# ============================================================

def vista_gestion_alumnos():
    if st.session_state.rol != "Admin":
        st.error("❌ No tienes permiso para gestionar alumnos")
        return
    
    st.title("👥 Gestionar Alumnos")
    tab1, tab2, tab3 = st.tabs(["📋 Listar Alumnos", "➕ Crear", "✏️ Editar"])
    
    with tab1:
        st.subheader("📋 Lista de Alumnos")
        col1, col2, col3 = st.columns(3)
        with col1:
            conn = get_db()
            grados = pd.read_sql("SELECT DISTINCT nombre FROM grados ORDER BY nombre", conn)
            conn.close()
            grado_filtro = st.selectbox("Grado:", ["Todos"] + grados['nombre'].tolist())
        with col2:
            conn = get_db()
            if grado_filtro != "Todos":
                secciones = pd.read_sql("""SELECT DISTINCT s.nombre FROM secciones s
                    JOIN grados g ON s.grado_id = g.id
                    WHERE g.nombre = ? ORDER BY s.nombre""", conn, params=[grado_filtro])
            else:
                secciones = pd.read_sql("SELECT DISTINCT nombre FROM secciones ORDER BY nombre", conn)
            conn.close()
            seccion_filtro = st.selectbox("Sección:", ["Todas"] + secciones['nombre'].tolist())
        with col3:
            nombre_buscar = st.text_input("Buscar por nombre o DNI:")
        
        query = """
            SELECT a.dni, a.nombres, a.apellido_paterno, a.apellido_materno,
                   g.nombre as grado, s.nombre as seccion, t.nombre as turno
            FROM alumnos a
            JOIN secciones s ON a.seccion_id = s.id
            JOIN grados g ON s.grado_id = g.id
            JOIN turnos t ON s.turno_id = t.id
            WHERE 1=1
        """
        params = []
        if grado_filtro != "Todos":
            query += " AND g.nombre = ?"
            params.append(grado_filtro)
        if seccion_filtro != "Todas":
            query += " AND s.nombre = ?"
            params.append(seccion_filtro)
        if nombre_buscar:
            query += " AND (a.apellido_paterno LIKE ? OR a.apellido_materno LIKE ? OR a.nombres LIKE ? OR a.dni LIKE ?)"
            params.extend([f"%{nombre_buscar}%"] * 4)
        query += " ORDER BY g.nombre, s.nombre, a.apellido_paterno LIMIT 2000"
        
        conn = get_db()
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        st.write(f"**{len(df)} alumnos encontrados**")
        st.dataframe(df[['dni', 'apellido_paterno', 'apellido_materno', 'nombres', 'grado', 'seccion', 'turno']], use_container_width=True)
    
    with tab2:
        st.subheader("➕ Crear Alumno")
        conn = get_db()
        secciones = pd.read_sql("""
            SELECT s.id, g.nombre as grado, s.nombre as seccion, t.nombre as turno
            FROM secciones s JOIN grados g ON s.grado_id = g.id
            JOIN turnos t ON s.turno_id = t.id ORDER BY t.nombre, g.nombre, s.nombre
        """, conn)
        conn.close()
        
        if secciones.empty:
            st.warning("No hay secciones. Importe alumnos primero.")
        else:
            with st.form("crear_alumno"):
                col1, col2 = st.columns(2)
                with col1:
                    dni = st.text_input("DNI (8 dígitos)")
                    nombres = st.text_input("Nombres")
                with col2:
                    ap_paterno = st.text_input("Apellido Paterno")
                    ap_materno = st.text_input("Apellido Materno")
                seccion_sel = st.selectbox("Sección:", secciones['id'].tolist(),
                    format_func=lambda x: f"{secciones[secciones['id']==x]['grado'].iloc[0]}{secciones[secciones['id']==x]['seccion'].iloc[0]} - {secciones[secciones['id']==x]['turno'].iloc[0]}")
                
                if st.form_submit_button("Crear Alumno", type="primary"):
                    if dni and nombres and ap_paterno:
                        conn = get_db()
                        c = conn.cursor()
                        try:
                            c.execute("""INSERT INTO alumnos (dni, nombres, apellido_paterno, apellido_materno, seccion_id) 
                                VALUES (?, ?, ?, ?, ?)""", (dni.strip(), nombres.strip(), ap_paterno.strip(), ap_materno.strip(), seccion_sel))
                            conn.commit()
                            registrar_auditoria(st.session_state.usuario, f"Creó alumno DNI {dni}")
                            st.success("✅ Alumno creado correctamente")
                        except sqlite3.IntegrityError:
                            st.error("❌ El DNI ya existe")
                        conn.close()
    
    with tab3:
        st.subheader("✏️ Editar Alumno")
        dni_buscar = st.text_input("Ingrese DNI del alumno a editar:", key="editar_dni")
        
        if dni_buscar:
            conn = get_db()
            alumno = pd.read_sql("""SELECT a.*, g.nombre as grado, s.nombre as seccion, t.nombre as turno
                FROM alumnos a JOIN secciones s ON a.seccion_id = s.id
                JOIN grados g ON s.grado_id = g.id JOIN turnos t ON s.turno_id = t.id
                WHERE a.dni = ?""", conn, params=[dni_buscar.strip()])
            conn.close()
            
            if not alumno.empty:
                al = alumno.iloc[0]
                st.write(f"**Alumno:** {al['apellido_paterno']} {al['apellido_materno']}, {al['nombres']}")
                st.write(f"**Actualmente:** {al['grado']}{al['seccion']} - Turno {al['turno']}")
                st.markdown("---")
                
                with st.form("editar_alumno_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        nombres = st.text_input("Nombres", value=al['nombres'])
                        ap_paterno = st.text_input("Apellido Paterno", value=al['apellido_paterno'])
                    with col2:
                        ap_materno = st.text_input("Apellido Materno", value=al['apellido_materno'])
                        st.text_input("DNI", value=al['dni'], disabled=True)
                    
                    conn = get_db()
                    secciones = pd.read_sql("""SELECT s.id, g.nombre as grado, s.nombre as seccion, t.nombre as turno
                        FROM secciones s JOIN grados g ON s.grado_id = g.id
                        JOIN turnos t ON s.turno_id = t.id ORDER BY t.nombre, g.nombre, s.nombre""", conn)
                    conn.close()
                    
                    seccion_actual = al['seccion_id']
                    if seccion_actual in secciones['id'].tolist():
                        idx = secciones['id'].tolist().index(seccion_actual)
                    else:
                        idx = 0
                    seccion_nueva = st.selectbox("Mover a sección:", secciones['id'].tolist(),
                        index=idx, format_func=lambda x: f"{secciones[secciones['id']==x]['grado'].iloc[0]}{secciones[secciones['id']==x]['seccion'].iloc[0]} - {secciones[secciones['id']==x]['turno'].iloc[0]}")
                    
                    if st.form_submit_button("💾 Actualizar Alumno", type="primary", use_container_width=True):
                        conn = get_db()
                        c = conn.cursor()
                        c.execute("""UPDATE alumnos SET nombres=?, apellido_paterno=?, apellido_materno=?, seccion_id=? WHERE id=?""",
                                 (nombres.strip(), ap_paterno.strip(), ap_materno.strip(), seccion_nueva, al['id']))
                        conn.commit()
                        registrar_auditoria(st.session_state.usuario, f"Editó alumno DNI {al['dni']}")
                        conn.close()
                        st.success(f"✅ Alumno actualizado correctamente")
            else:
                st.warning("No se encontró alumno con ese DNI")
        else:
            st.info("Ingrese el DNI del alumno para editarlo")

# ============================================================
# VISTA GESTIONAR SECCIONES
# ============================================================

def vista_gestion_secciones():
    if st.session_state.rol != "Admin":
        st.error("❌ No tienes permiso para gestionar secciones")
        return
    
    st.title("📚 Gestionar Secciones")
    tab1, tab2, tab3 = st.tabs(["📋 Ver", "➕ Crear", "🔄 Cambiar Turno"])
    
    with tab1:
        conn = get_db()
        df = pd.read_sql("""SELECT s.id, g.nombre as grado, s.nombre as seccion, t.nombre as turno,
                   COUNT(a.id) as total_alumnos
            FROM secciones s JOIN grados g ON s.grado_id = g.id
            JOIN turnos t ON s.turno_id = t.id
            LEFT JOIN alumnos a ON a.seccion_id = s.id
            GROUP BY s.id ORDER BY t.nombre, g.nombre, s.nombre""", conn)
        conn.close()
        st.dataframe(df, use_container_width=True)
    
    with tab2:
        st.subheader("Crear Sección")
        with st.form("crear_seccion"):
            col1, col2, col3 = st.columns(3)
            with col1:
                grado = st.text_input("Grado (1-5)")
            with col2:
                seccion = st.text_input("Sección (A, B, C)")
            with col3:
                turno = st.selectbox("Turno", ["Mañana", "Tarde"])
            
            if st.form_submit_button("Crear Sección", type="primary"):
                if grado and seccion:
                    conn = get_db()
                    c = conn.cursor()
                    c.execute("SELECT id FROM turnos WHERE nombre=?", (turno,))
                    turno_id = c.fetchone()['id']
                    grado_id = c.execute("SELECT id FROM grados WHERE nombre=?", (grado,)).fetchone()
                    if not grado_id:
                        c.execute("INSERT INTO grados (nombre) VALUES (?)", (grado,))
                        grado_id = c.lastrowid
                    else:
                        grado_id = grado_id['id']
                    try:
                        c.execute("INSERT INTO secciones (nombre, grado_id, turno_id) VALUES (?, ?, ?)",
                                 (seccion, grado_id, turno_id))
                        conn.commit()
                        registrar_auditoria(st.session_state.usuario, f"Creó sección {grado}{seccion}")
                        st.success(f"✅ Sección {grado}{seccion} creada")
                    except:
                        st.error("La sección ya existe")
                    conn.close()
    
    with tab3:
        st.subheader("Cambiar Turno de Sección")
        conn = get_db()
        df = pd.read_sql("""SELECT s.id, g.nombre as grado, s.nombre as seccion, t.nombre as turno
            FROM secciones s JOIN grados g ON s.grado_id = g.id
            JOIN turnos t ON s.turno_id = t.id ORDER BY t.nombre, g.nombre, s.nombre""", conn)
        conn.close()
        
        if df.empty:
            st.warning("No hay secciones")
        else:
            seccion_sel = st.selectbox("Seleccionar sección:", df['id'].tolist(),
                format_func=lambda x: f"{df[df['id']==x]['grado'].iloc[0]}{df[df['id']==x]['seccion'].iloc[0]} - Turno actual: {df[df['id']==x]['turno'].iloc[0]}")
            nuevo_turno = st.radio("Nuevo turno:", ["Mañana", "Tarde"], horizontal=True)
            
            if st.button("Cambiar Turno", type="primary"):
                conn = get_db()
                c = conn.cursor()
                c.execute("SELECT id FROM turnos WHERE nombre=?", (nuevo_turno,))
                turno_id = c.fetchone()['id']
                c.execute("UPDATE secciones SET turno_id=? WHERE id=?", (turno_id, seccion_sel))
                conn.commit()
                registrar_auditoria(st.session_state.usuario, f"Cambió turno de sección ID {seccion_sel}")
                conn.close()
                st.success("✅ Turno actualizado")

# ============================================================
# VISTA REPORTES
# ============================================================

def vista_reportes():
    st.title("📊 Reportes")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        periodo = st.selectbox("Período:", ["Diario", "Semanal", "Mensual", "Bimestral", "Trimestral", "Semestral", "Anual"])
    with col2:
        turno_filtro = st.selectbox("Turno:", ["Todos", "Mañana", "Tarde"])
    with col3:
        conn = get_db()
        if st.session_state.rol == "Auxiliar" and st.session_state.turno_asignado:
            secciones_df = pd.read_sql("""SELECT DISTINCT g.nombre as grado, s.nombre as seccion, 
                       g.nombre || s.nombre as salon
                FROM secciones s JOIN grados g ON s.grado_id = g.id
                JOIN turnos t ON s.turno_id = t.id
                WHERE t.nombre = ? ORDER BY g.nombre, s.nombre""", conn, params=[st.session_state.turno_asignado])
        else:
            secciones_df = pd.read_sql("""SELECT DISTINCT g.nombre as grado, s.nombre as seccion, 
                       g.nombre || s.nombre as salon
                FROM secciones s JOIN grados g ON s.grado_id = g.id
                ORDER BY g.nombre, s.nombre""", conn)
        conn.close()
        salon_filtro = st.selectbox("Salón:", ["Todos"] + secciones_df['salon'].tolist())
    
    hoy = datetime.now().date()
    if periodo == "Diario":
        inicio = hoy; fin = hoy
    elif periodo == "Semanal":
        inicio = hoy - timedelta(days=7); fin = hoy
    elif periodo == "Mensual":
        inicio = hoy - timedelta(days=30); fin = hoy
    elif periodo == "Bimestral":
        inicio = hoy - timedelta(days=60); fin = hoy
    elif periodo == "Trimestral":
        inicio = hoy - timedelta(days=90); fin = hoy
    elif periodo == "Semestral":
        inicio = hoy - timedelta(days=180); fin = hoy
    else:
        inicio = hoy - timedelta(days=365); fin = hoy
    
    st.info(f"Período: {inicio} al {fin}")
    
    dias_laborales = []
    fecha_actual = inicio
    while fecha_actual <= fin:
        fecha_str = fecha_actual.strftime("%Y-%m-%d")
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id FROM dias_especiales WHERE fecha = ? AND activo = 1", (fecha_str,))
        es_especial = c.fetchone() is not None
        conn.close()
        if fecha_actual.weekday() < 5 or es_especial:
            dias_laborales.append(fecha_str)
        fecha_actual += timedelta(days=1)
    
    if not dias_laborales:
        st.warning("No hay días laborales en el período seleccionado")
        return
    
    query = """SELECT a.dni, a.apellido_paterno, a.apellido_materno, a.nombres,
               g.nombre as grado, s.nombre as seccion, t.nombre as turno,
               ast.fecha, ast.hora, ast.estado
        FROM alumnos a JOIN secciones s ON a.seccion_id = s.id
        JOIN grados g ON s.grado_id = g.id JOIN turnos t ON s.turno_id = t.id
        LEFT JOIN asistencias ast ON a.id = ast.alumno_id AND ast.fecha IN ({})"""
    query = query.format(','.join(['?'] * len(dias_laborales)))
    
    params = dias_laborales.copy()
    if turno_filtro != "Todos":
        query += " AND t.nombre = ?"
        params.append(turno_filtro)
    if salon_filtro != "Todos":
        query += " AND g.nombre || s.nombre = ?"
        params.append(salon_filtro)
    query += " ORDER BY t.nombre, g.nombre, s.nombre, a.apellido_paterno"
    
    conn = get_db()
    df = pd.read_sql(query, conn, params=params)
    conn.close()
    
    if df.empty:
        st.warning("No hay datos para los filtros seleccionados")
        return
    
    total_registros = len(df[df['estado'].notna()])
    puntuales = len(df[df['estado'] == 'Puntual'])
    tardanzas = len(df[df['estado'] == 'Tardanza'])
    faltas = len(df[df['estado'] == 'Falta'])
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""<div style="background: linear-gradient(135deg, #f7971e 0%, #ffd200 100%); 
                    padding: 15px; border-radius: 15px; text-align: center;">
            <h2 style="font-size: 28px; margin: 0; color: #FFFFFF;">{total_registros}</h2>
            <p style="margin: 0; color: #FFFFFF;">📊 Total Registros</p>
        </div>""", unsafe_allow_html=True)
    with col2:
        st.markdown(f"""<div style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); 
                    padding: 15px; border-radius: 15px; text-align: center;">
            <h2 style="font-size: 28px; margin: 0; color: #FFFFFF;">{puntuales}</h2>
            <p style="margin: 0; color: #FFFFFF;">✅ Puntuales</p>
        </div>""", unsafe_allow_html=True)
    with col3:
        st.markdown(f"""<div style="background: linear-gradient(135deg, #f7971e 0%, #ffd200 100%); 
                    padding: 15px; border-radius: 15px; text-align: center;">
            <h2 style="font-size: 28px; margin: 0; color: #FFFFFF;">{tardanzas}</h2>
            <p style="margin: 0; color: #FFFFFF;">🟡 Tardanzas</p>
        </div>""", unsafe_allow_html=True)
    with col4:
        st.markdown(f"""<div style="background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%); 
                    padding: 15px; border-radius: 15px; text-align: center;">
            <h2 style="font-size: 28px; margin: 0; color: #FFFFFF;">{faltas}</h2>
            <p style="margin: 0; color: #FFFFFF;">🔴 Faltas</p>
        </div>""", unsafe_allow_html=True)
    
    st.markdown("---")
    
    if salon_filtro == "Todos":
        st.subheader("Resumen por Salón")
        df_resumen = df[df['estado'].notna()].groupby(['grado', 'seccion', 'turno']).agg(
            total=('estado', 'count'),
            puntuales=('estado', lambda x: (x == 'Puntual').sum()),
            tardanzas=('estado', lambda x: (x == 'Tardanza').sum()),
            faltas=('estado', lambda x: (x == 'Falta').sum())
        ).reset_index()
        df_resumen['salon'] = df_resumen['grado'] + df_resumen['seccion']
        st.dataframe(df_resumen, use_container_width=True)
        
        st.markdown("---")
        st.subheader("Detalle de Asistencias")
        st.dataframe(df.style.map(color_estado, subset=['estado']), use_container_width=True)
        
        col1, col2 = st.columns(2)
        with col1:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Detalle')
            st.download_button("⬇️ Excel Completo", output.getvalue(), f"reporte_{periodo}.xlsx")
        with col2:
            pdf = generar_pdf_reporte(df, f"Reporte {periodo}")

            st.download_button("⬇️ PDF Completo", pdf, f"reporte_{periodo}.pdf", "application/pdf")
    else:
        st.subheader(f"Asistencias del Salón {salon_filtro}")
        st.dataframe(df.style.map(color_estado, subset=['estado']), use_container_width=True)
        
        col1, col2 = st.columns(2)
        with col1:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name=f'Salon_{salon_filtro}')
            st.download_button(f"⬇️ Excel {salon_filtro}", output.getvalue(), f"reporte_{salon_filtro}_{periodo}.xlsx")
        with col2:
            pdf = generar_pdf_reporte(df, f"Reporte {salon_filtro} - {periodo}")
            st.download_button(f"⬇️ PDF {salon_filtro}", pdf, f"reporte_{salon_filtro}_{periodo}.pdf", "application/pdf")

# ============================================================
# VISTA CARNETS
# ============================================================

def vista_carnets():
    if st.session_state.rol == "Auxiliar":
        st.error("❌ No tienes permiso para generar carnets")
        return
    
    st.title("🪪 Generar Carnets")
    
    conn = get_db()
    df = pd.read_sql("""SELECT s.id, g.nombre as grado, s.nombre as seccion, t.nombre as turno, COUNT(a.id) as total
        FROM secciones s JOIN grados g ON s.grado_id = g.id
        JOIN turnos t ON s.turno_id = t.id
        LEFT JOIN alumnos a ON a.seccion_id = s.id
        GROUP BY s.id ORDER BY t.nombre, g.nombre, s.nombre""", conn)
    conn.close()
    
    if df.empty:
        st.warning("No hay secciones")
        return
    
    seccion_sel = st.selectbox("Sección:", df['id'].tolist(),
        format_func=lambda x: f"{df[df['id']==x]['grado'].iloc[0]}{df[df['id']==x]['seccion'].iloc[0]} - {df[df['id']==x]['turno'].iloc[0]} ({df[df['id']==x]['total'].iloc[0]})")
    
    if st.button("Generar PDF", type="primary"):
        pdf = generar_pdf_carnets(seccion_sel)
        if pdf:
            st.download_button("Descargar PDF", pdf, f"carnets_{seccion_sel}.pdf", "application/pdf")

# ============================================================
# VISTA DÍAS ESPECIALES
# ============================================================

def vista_dias_especiales():
    if st.session_state.rol == "Auxiliar":
        st.error("❌ No tienes permiso para gestionar días especiales")
        return
    
    st.title("📅 Días Especiales")
    
    hoy = hora_peru().strftime("%Y-%m-%d")
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM dias_especiales WHERE fecha = ? AND activo = 1", (hoy,))
    hoy_especial = c.fetchone()
    conn.close()
    
    if hoy_especial:
        st.success(f"🎉 **HOY ES DÍA ESPECIAL!** {hoy_especial['descripcion']}")
        st.info(f"⏰ Entrada: **{hoy_especial['hora_entrada']}**")
    else:
        dia_semana = hora_peru().weekday()
        if dia_semana >= 5:
            st.warning("⛔ **FIN DE SEMANA** - No se toma asistencia")
        else:
            st.info("📅 Día laboral normal")
    
    st.markdown("---")
    
    with st.form("crear_dia"):
        col1, col2 = st.columns(2)
        with col1:
            fecha = st.date_input("📅 Fecha", min_value=datetime.now().date())
            descripcion = st.text_input("📝 Descripción", placeholder="Ej: Día del Maestro, Feriado, etc.")
        with col2:
            hora_entrada = st.time_input("⏰ Hora de entrada", value=datetime.strptime("08:00", "%H:%M").time())
        
        hora_limite = (datetime.combine(datetime.today(), hora_entrada) + timedelta(minutes=15)).time()
        st.caption(f"⏱️ Límite para puntualidad: **{hora_limite.strftime('%H:%M')}** (entrada + 15 min)")
        
        dia_semana = fecha.weekday()
        if dia_semana >= 5:
            st.info("📌 Esta fecha cae en **fin de semana**. Al ser día especial, se tomará asistencia.")
        else:
            st.caption("📌 Esta fecha es día laboral. Se tomará asistencia con horario especial.")
        
        if st.form_submit_button("✅ Crear Día Especial", type="primary", use_container_width=True):
            if fecha and descripcion:
                conn = get_db()
                c = conn.cursor()
                try:
                    c.execute("""INSERT OR REPLACE INTO dias_especiales (fecha, descripcion, hora_entrada, activo)
                        VALUES (?, ?, ?, 1)""", (fecha.strftime("%Y-%m-%d"), descripcion, hora_entrada.strftime("%H:%M")))
                    conn.commit()
                    registrar_auditoria(st.session_state.get('usuario', 'sistema'), f"Creó/actualizó día especial {fecha}")
                    conn.close()
                    st.success(f"✅ Día especial creado para {fecha.strftime('%d/%m/%Y')}")
                except Exception as e:
                    st.error(f"Error: {str(e)}")
                    conn.close()
            else:
                st.warning("Completa todos los campos")
    
    st.markdown("---")
    st.subheader("📋 Días Especiales Programados")
    
    conn = get_db()
    df = pd.read_sql("""SELECT id, fecha, descripcion, hora_entrada, activo
        FROM dias_especiales WHERE fecha >= date('now') ORDER BY fecha""", conn)
    conn.close()
    
    if df.empty:
        st.info("No hay días especiales programados")
    else:
        df['día'] = pd.to_datetime(df['fecha']).dt.day_name()
        df['estado'] = df['activo'].map({1: '✅ Activo', 0: '❌ Inactivo'})
        df['hora_limite'] = pd.to_datetime(df['hora_entrada'] + ':00') + timedelta(minutes=15)
        df['hora_limite'] = df['hora_limite'].dt.strftime('%H:%M')
        df['fecha'] = pd.to_datetime(df['fecha']).dt.strftime('%d/%m/%Y')
        
        st.dataframe(df[['id', 'fecha', 'día', 'descripcion', 'hora_entrada', 'hora_limite', 'estado']], 
                    use_container_width=True)
        
        st.markdown("---")
        st.subheader("🗑️ Eliminar Día Especial")
        
        dias_opciones = {f"{row['fecha']} - {row['descripcion']}": row['id'] for _, row in df.iterrows()}
        dia_eliminar = st.selectbox("Seleccionar día a eliminar:", list(dias_opciones.keys()))
        
        if st.button("🗑️ Eliminar Día Especial", type="primary", use_container_width=True):
            dia_id = dias_opciones[dia_eliminar]
            conn = get_db()
            c = conn.cursor()
            c.execute("DELETE FROM dias_especiales WHERE id = ?", (dia_id,))
            conn.commit()
            registrar_auditoria(st.session_state.get('usuario', 'sistema'), f"Eliminó día especial ID {dia_id}")
            conn.close()
            st.success("✅ Día especial eliminado")

# ============================================================
# VISTA USUARIOS
# ============================================================

def vista_usuarios():
    if st.session_state.rol != "Admin":
        st.error("❌ No tienes permiso para gestionar usuarios")
        return
    
    st.title("👤 Gestionar Usuarios")
    tab1, tab2 = st.tabs(["📋 Listar Usuarios", "➕ Crear/Editar Usuario"])
    
    with tab1:
        conn = get_db()
        df = pd.read_sql("SELECT id, usuario, rol, nombres, turno_asignado FROM usuarios ORDER BY usuario", conn)
        conn.close()
        st.dataframe(df, use_container_width=True)
    
    with tab2:
        st.subheader("Crear Nuevo Usuario")
        conn = get_db()
        usuarios_existentes = pd.read_sql("SELECT usuario FROM usuarios", conn)
        usuarios_lista = usuarios_existentes['usuario'].tolist()
        conn.close()
        
        opcion_usuario = st.radio("Acción:", ["Crear nuevo", "Editar existente"], horizontal=True)
        
        if opcion_usuario == "Crear nuevo":
            col1, col2 = st.columns(2)
            with col1:
                usuario = st.text_input("Usuario*", placeholder="Ej: juan_perez", key="usuario_input")
                password = st.text_input("Password*", type="password", placeholder="Mínimo 6 caracteres", key="password_input")
                nombres = st.text_input("Nombres*", placeholder="Juan Pérez", key="nombres_input")
            with col2:
                rol = st.selectbox("Rol", ["Admin", "Coordinador", "Auxiliar"], key="rol_input")
                if rol == "Auxiliar":
                    turno_asignado = st.selectbox("Turno asignado", ["Mañana", "Tarde"], key="turno_input")
                else:
                    turno_asignado = ""
                    st.info("ℹ️ El turno solo se asigna a usuarios con rol 'Auxiliar'")
            
            if usuario and usuario in usuarios_lista:
                st.error(f"❌ El usuario '{usuario}' ya existe. Elige otro nombre.")
            
            if st.button("✅ Crear Usuario", type="primary", use_container_width=True):
                errores = []
                if not usuario:
                    errores.append("❌ El usuario es obligatorio")
                elif usuario in usuarios_lista:
                    errores.append(f"❌ El usuario '{usuario}' ya existe. Elige otro nombre.")
                if not password:
                    errores.append("❌ La contraseña es obligatoria")
                elif len(password) < 6:
                    errores.append("❌ La contraseña debe tener al menos 6 caracteres")
                if not nombres:
                    errores.append("❌ Los nombres son obligatorios")
                
                if errores:
                    for error in errores:
                        st.error(error)
                else:
                    try:
                        conn = get_db()
                        c = conn.cursor()
                        password_hash = hashlib.sha256(password.encode()).hexdigest()
                        if rol != "Auxiliar":
                            turno_asignado = ""
                        c.execute("""INSERT INTO usuarios (usuario, password, rol, nombres, turno_asignado)
                            VALUES (?, ?, ?, ?, ?)""", (usuario, password_hash, rol, nombres, turno_asignado))
                        conn.commit()
                        registrar_auditoria(st.session_state.usuario, f"Creó usuario {usuario}")
                        conn.close()
                        st.success(f"✅ Usuario '{usuario}' creado correctamente")
                        st.balloons()
                    except sqlite3.IntegrityError as e:
                        if "UNIQUE constraint failed" in str(e):
                            st.error(f"❌ El usuario '{usuario}' ya existe. Elige otro nombre.")
                        else:
                            st.error(f"❌ Error al crear usuario: {str(e)}")
                    except Exception as e:
                        st.error(f"❌ Error inesperado: {str(e)}")
        
        else:
            conn = get_db()
            usuarios = pd.read_sql("SELECT id, usuario, rol, nombres, turno_asignado FROM usuarios WHERE usuario != 'admin' ORDER BY usuario", conn)
            conn.close()
            
            if usuarios.empty:
                st.info("No hay usuarios para editar (además del admin)")
            else:
                usuario_sel = st.selectbox("Seleccionar usuario:", usuarios['id'].tolist(),
                    format_func=lambda x: f"{usuarios[usuarios['id']==x]['usuario'].iloc[0]} - {usuarios[usuarios['id']==x]['rol'].iloc[0]}")
                
                if usuario_sel:
                    usuario_data = usuarios[usuarios['id'] == usuario_sel].iloc[0]
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        nuevo_usuario = st.text_input("Usuario", value=usuario_data['usuario'], key="edit_usuario")
                        nueva_password = st.text_input("Nueva Password (dejar vacío para no cambiar)", type="password", key="edit_password")
                        nuevos_nombres = st.text_input("Nombres", value=usuario_data['nombres'], key="edit_nombres")
                    with col2:
                        nuevo_rol = st.selectbox("Rol", ["Admin", "Coordinador", "Auxiliar"], 
                                                index=["Admin", "Coordinador", "Auxiliar"].index(usuario_data['rol']),
                                                key="edit_rol")
                        if nuevo_rol == "Auxiliar":
                            turno_actual = usuario_data['turno_asignado'] if usuario_data['turno_asignado'] else "Mañana"
                            nuevo_turno = st.selectbox("Turno asignado", ["Mañana", "Tarde"],
                                                      index=0 if turno_actual == "Mañana" else 1,
                                                      key="edit_turno")
                        else:
                            nuevo_turno = ""
                            st.info("ℹ️ El turno solo se asigna a usuarios con rol 'Auxiliar'")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        submit_edit = st.button("✏️ Actualizar", type="primary", use_container_width=True)
                    with col2:
                        submit_delete = st.button("🗑️ Eliminar", use_container_width=True)
                    
                    if submit_edit:
                        if nuevo_usuario != usuario_data['usuario'] and nuevo_usuario in usuarios_lista:
                            st.error(f"❌ El usuario '{nuevo_usuario}' ya existe. Elige otro nombre.")
                        else:
                            try:
                                conn = get_db()
                                c = conn.cursor()
                                if nuevo_rol != "Auxiliar":
                                    nuevo_turno = ""
                                if nueva_password:
                                    password_hash = hashlib.sha256(nueva_password.encode()).hexdigest()
                                    c.execute("""UPDATE usuarios SET usuario=?, password=?, rol=?, nombres=?, turno_asignado=?
                                        WHERE id=?""", (nuevo_usuario, password_hash, nuevo_rol, nuevos_nombres, nuevo_turno, usuario_sel))
                                else:
                                    c.execute("""UPDATE usuarios SET usuario=?, rol=?, nombres=?, turno_asignado=?
                                        WHERE id=?""", (nuevo_usuario, nuevo_rol, nuevos_nombres, nuevo_turno, usuario_sel))
                                conn.commit()
                                if nuevo_usuario == st.session_state.usuario:
                                    st.session_state.rol = nuevo_rol
                                    st.session_state.nombres = nuevos_nombres
                                    st.session_state.turno_asignado = nuevo_turno if nuevo_rol == "Auxiliar" else None
                                registrar_auditoria(st.session_state.usuario, f"Editó usuario {nuevo_usuario}")
                                conn.close()
                                st.success("✅ Usuario actualizado correctamente")
                            except sqlite3.IntegrityError as e:
                                if "UNIQUE constraint failed" in str(e):
                                    st.error(f"❌ El usuario '{nuevo_usuario}' ya existe. Elige otro nombre.")
                                else:
                                    st.error(f"❌ Error: {str(e)}")
                            except Exception as e:
                                st.error(f"❌ Error inesperado: {str(e)}")
                    
                    if submit_delete:
                        if usuario_data['usuario'] != 'admin':
                            try:
                                conn = get_db()
                                c = conn.cursor()
                                c.execute("DELETE FROM usuarios WHERE id = ?", (usuario_sel,))
                                conn.commit()
                                if usuario_data['usuario'] == st.session_state.usuario:
                                    st.session_state.autenticado = False
                                    st.warning("⚠️ Tu usuario ha sido eliminado. Inicia sesión nuevamente.")
                                else:
                                    registrar_auditoria(st.session_state.usuario, f"Eliminó usuario {usuario_data['usuario']}")
                                    conn.close()
                                    st.success(f"✅ Usuario '{usuario_data['usuario']}' eliminado")
                            except Exception as e:
                                st.error(f"❌ Error al eliminar: {str(e)}")
                        else:
                            st.warning("⚠️ No se puede eliminar el usuario admin")

# ============================================================
# VISTA AUDITORÍA
# ============================================================

def vista_auditoria():
    if st.session_state.rol != "Admin":
        st.error("❌ No tienes permiso para ver auditoría")
        return
    
    st.title("📋 Auditoría")
    if st.button("🔄 Actualizar", use_container_width=True):
        st.rerun()
    
    conn = get_db()
    c = conn.cursor()
    total = c.execute("SELECT COUNT(*) as total FROM auditoria").fetchone()['total']
    conn.close()
    st.info(f"Total de registros: {total}")
    
    conn = get_db()
    df = pd.read_sql("SELECT id, usuario, accion, fecha FROM auditoria ORDER BY id DESC LIMIT 100", conn)
    conn.close()
    
    if df.empty:
        st.warning("No hay registros de auditoría aún")
    else:
        st.dataframe(df, use_container_width=True)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        st.download_button("Descargar Excel", output.getvalue(), "auditoria.xlsx")

# ============================================================
# VISTA HORARIOS
# ============================================================

def vista_horarios():
    if st.session_state.rol not in ["Admin", "Coordinador"]:
        st.error("❌ No tienes permiso para configurar horarios")
        return
    
    st.title("⏰ Configurar Horarios")
    
    conn = get_db()
    c = conn.cursor()
    turnos = c.execute("SELECT * FROM turnos").fetchall()
    
    for turno in turnos:
        st.subheader(f"🕐 Turno {turno['nombre']}")
        config = obtener_config_horario(turno['id'])
        
        with st.form(key=f"horario_{turno['id']}"):
            col1, col2 = st.columns(2)
            
            with col1:
                hora_actual = datetime.strptime(config['entrada'], "%H:%M")
                st.write(f"📌 Entrada actual: **{hora_actual.strftime('%I:%M %p')}**")
                horas = [f"{h:02d}:{m:02d} {'AM' if h < 12 else 'PM'}" for h in range(24) for m in [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]]
                hora_actual_12h = f"{hora_actual.strftime('%H:%M')} {'AM' if hora_actual.hour < 12 else 'PM'}"
                idx = horas.index(hora_actual_12h) if hora_actual_12h in horas else 0
                entrada_seleccionada = st.selectbox(f"Hora de entrada", horas, index=idx)
                hora_entrada_str = datetime.strptime(entrada_seleccionada.replace(' AM', '').replace(' PM', ''), "%H:%M").strftime("%H:%M")
            
            with col2:
                hora_limite_actual = datetime.strptime(config['limite'], "%H:%M")
                st.write(f"⏰ Límite actual: **{hora_limite_actual.strftime('%I:%M %p')}**")
                hora_limite_12h = f"{hora_limite_actual.strftime('%H:%M')} {'AM' if hora_limite_actual.hour < 12 else 'PM'}"
                idx2 = horas.index(hora_limite_12h) if hora_limite_12h in horas else 0
                limite_seleccionada = st.selectbox(f"Hora límite (puntualidad)", horas, index=idx2)
                hora_limite_str = datetime.strptime(limite_seleccionada.replace(' AM', '').replace(' PM', ''), "%H:%M").strftime("%H:%M")
            
            entrada_min = datetime.strptime(hora_entrada_str, "%H:%M")
            limite_min = datetime.strptime(hora_limite_str, "%H:%M")
            diff = int((limite_min - entrada_min).total_seconds() / 60)
            st.caption(f"⏱️ Tolerancia: **{diff} minutos**")
            
            if st.form_submit_button(f"💾 Guardar horario {turno['nombre']}", type="primary"):
                c.execute("UPDATE config_horarios SET hora_entrada=?, hora_limite=? WHERE turno_id=?",
                         (hora_entrada_str, hora_limite_str, turno['id']))
                conn.commit()
                registrar_auditoria(st.session_state.usuario, f"Actualizó horario {turno['nombre']}")
                st.success(f"✅ Horario de {turno['nombre']} actualizado")
    
    conn.close()

# ============================================================
# MAIN
# ============================================================

def main():
    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False
    
    if not st.session_state.autenticado:
        login()
    else:
        opcion = menu()
        
        if opcion == "🚪 Puerta de Entrada":
            vista_puerta()
        elif opcion == "📥 Importar Excel":
            vista_importar()
        elif opcion == "👥 Gestionar Alumnos":
            vista_gestion_alumnos()
        elif opcion == "📚 Gestionar Secciones":
            vista_gestion_secciones()
        elif opcion == "📊 Reportes":
            vista_reportes()
        elif opcion == "🪪 Carnets":
            vista_carnets()
        elif opcion == "📅 Días Especiales":
            vista_dias_especiales()
        elif opcion == "👤 Usuarios":
            vista_usuarios()
        elif opcion == "📋 Auditoría":
            vista_auditoria()
        elif opcion == "⏰ Horarios":
            vista_horarios()

if __name__ == "__main__":
    main()
