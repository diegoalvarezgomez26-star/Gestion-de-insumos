import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import ssl
from datetime import datetime

# Desactivar la verificación estricta de certificados SSL (Para redes corporativas)
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# =========================================================================
# 1. CONEXIÓN A LA API (https://script.google.com/macros/s/AKfycbxHDNm8c3ybd0q83vLvxnJliCOQTrPGhOGnIfXSAGwafZ2AlARG9mWUZ1l_-UE-aFjvZQ/exec)
# =========================================================================
URL_API = "https://script.google.com/macros/s/AKfycbxHDNm8c3ybd0q83vLvxnJliCOQTrPGhOGnIfXSAGwafZ2AlARG9mWUZ1l_-UE-aFjvZQ/exec"

def request_api(payload):
    """Envía peticiones POST al backend (Apps Script)."""
    try:
        respuesta = requests.post(URL_API, json=payload, allow_redirects=True)
        return respuesta.json()
    except requests.exceptions.JSONDecodeError:
        return {"exito": False, "error": "JSONDecodeError: El servidor no devolvió JSON válido."}
    except Exception as e:
        return {"exito": False, "error": str(e)}

def fetch_sheet(pestaña):
    """Obtiene todos los registros de una pestaña mediante GET de forma limpia."""
    try:
        respuesta = requests.get(URL_API)
        if respuesta.status_code == 200:
            datos_globales = respuesta.json()
            if pestaña in datos_globales:
                datos_pestaña = datos_globales[pestaña]
                if isinstance(datos_pestaña, list) and len(datos_pestaña) > 0:
                    return pd.DataFrame(datos_pestaña)
    except Exception as e:
        pass
    return pd.DataFrame()

def verificar_credenciales_local(usuario_ingresado, contrasena_ingresada):
    """Descarga la pestaña Usuarios y valida las credenciales directamente en Python."""
    df_usuarios = fetch_sheet("Usuarios")
    if not df_usuarios.empty:
        df_usuarios.columns = df_usuarios.columns.str.strip()
        if "Usuario" in df_usuarios.columns and "Contraseña" in df_usuarios.columns:
            coincidencia = df_usuarios[
                (df_usuarios["Usuario"].astype(str).str.strip() == str(usuario_ingresado).strip()) & 
                (df_usuarios["Contraseña"].astype(str).str.strip() == str(contrasena_ingresada).strip())
            ]
            if not coincidencia.empty:
                return coincidencia.iloc[0].get("Rol", "Invitado")
    return None

# =========================================================================
# 2. SISTEMA VISUAL Y SEMÁFOROS 
# =========================================================================
def renderizar_tabla_consumibles():
    """Muestra la tabla de consumibles aplicando alertas de color si baja el stock."""
    st.subheader("📦 Inventario de Consumibles")
    df = fetch_sheet("Consumibles")
    if df.empty:
        st.info("No hay consumibles registrados.")
        return

    # Verificar existencias de columnas críticas para evitar caídas
    columnas_necesarias = ["Stock_Actual", "Stock_Minimo"]
    for col in columnas_necesarias:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Lógica de Alertas Visuales
    if "Stock_Actual" in df.columns and "Stock_Minimo" in df.columns:
        alertas = df[df["Stock_Actual"] <= df["Stock_Minimo"]]
        if not alertas.empty:
            st.error(f"🚨 ¡ATENCIÓN! Hay {len(alertas)} insumos con nivel de Stock Mínimo o Crítico.")
            
        # Resaltado de filas seguro a prueba de errores de lectura
        def destacar_bajo_stock(row):
            try:
                actual = pd.to_numeric(row['Stock_Actual'], errors='coerce')
                minimo = pd.to_numeric(row['Stock_Minimo'], errors='coerce')
                if actual <= minimo:
                    return ['background-color: #ffcccc; color: #cc0000; font-weight: bold'] * len(row)
            except:
                pass
            return [''] * len(row)
        
        st.dataframe(df.style.apply(destacar_bajo_stock, axis=1), use_container_width=True)
    else:
        st.dataframe(df, use_container_width=True)

# =========================================================================
# 3. COMPONENTES VISUALES Y FORMULARIOS (FASE 2)
# =========================================================================
def sidebar_login():
    """Maneja el inicio de sesión y persistencia del rol en la barra lateral."""
    if "rol" not in st.session_state:
        st.session_state["rol"] = None
        st.session_state["usuario"] = None

    if st.session_state["rol"] is None:
        st.sidebar.title("🔐 Acceso")
        with st.sidebar.form("form_login"):
            usuario = st.text_input("Usuario")
            contrasena = st.text_input("Contraseña", type="password")
            submit = st.form_submit_button("Ingresar")
            
            if submit:
                rol_detectado = verificar_credenciales_local(usuario, contrasena)
                if rol_detectado:
                    st.session_state["rol"] = rol_detectado
                    st.session_state["usuario"] = usuario
                    st.sidebar.success("¡Acceso concedido!")
                    st.rerun()
                else:
                    st.sidebar.error("Credenciales incorrectas")
        return False
    else:
        st.sidebar.success(f"Usuario: {st.session_state['usuario']} \n\nRol: {st.session_state['rol']}")
        if st.sidebar.button("Cerrar Sesión"):
            st.session_state["rol"] = None
            st.session_state["usuario"] = None
            st.rerun()
        return True

def mostrar_graficos():
    st.subheader("📊 Top 5 Insumos Más Utilizados")
    df_consumos = fetch_sheet("Historial_Consumos")
    if not df_consumos.empty and "Articulo" in df_consumos.columns and "Cantidad_Retirada" in df_consumos.columns:
        df_consumos["Cantidad_Retirada"] = pd.to_numeric(df_consumos["Cantidad_Retirada"], errors="coerce")
        df_top = df_consumos.groupby("Articulo")["Cantidad_Retirada"].sum().nlargest(5).reset_index()
        fig = px.bar(df_top, x="Articulo", y="Cantidad_Retirada", color="Cantidad_Retirada", color_continuous_scale="Blues")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay suficientes datos en el Historial para graficar.")

def form_ticket():
    st.subheader("🎫 Crear Ticket de Requisición")
    with st.form("form_nuevo_ticket"):
        id_ticket = st.text_input("ID del Ticket / Requisición (Manual)")
        articulo = st.text_input("Artículo Solicitado")
        cantidad = st.number_input("Cantidad", min_value=1)
        urgencia = st.selectbox("Urgencia", ["Normal", "Alta"])
        especificacion = st.text_area("Especificación")
        link = st.text_input("Link Cotización")
        submit = st.form_submit_button("Enviar Requisición")
        
        if submit:
            if articulo and id_ticket:
                payload = {
                    "pestana": "Tickets_Requisiciones",
                    "accion": "insertar_fila",
                    "valores": {
                        "ID_Ticket": id_ticket, # Ajustado exactamente a tu Google Sheets
                        "Solicitante": st.session_state["usuario"],
                        "Articulo": articulo,
                        "Cantidad": cantidad,
                        "Urgencia": urgencia,
                        "Especificacion": especificacion,
                        "Link_Cotizacion": link,
                        "Estatus": "Pendiente"
                    }
                }
                res = request_api(payload)
                if res.get("exito"):
                    st.success(f"¡Ticket {id_ticket} registrado con éxito!")
                else:
                    st.error(f"Error: {res.get('error')}")
            else:
                st.warning("El ID del Ticket y el nombre del Artículo son obligatorios.")

def panel_admin():
    st.subheader("🛠️ Panel de Gestión y Movimientos")
    
    # 1. MODIFICAR STOCK MANUAL
    with st.expander("🔻 Modificar Stock (Consumo Manual)", expanded=False):
        with st.form("form_consumo"):
            articulo = st.text_input("Artículo a consumir (Exactamente como está en la base)")
            cantidad = st.number_input("Cantidad a retirar", min_value=1.0, step=1.0)
            submit = st.form_submit_button("Aplicar Consumo")
            if submit:
                if articulo:
                    res = request_api({"pestana": "Consumibles", "accion": "actualizar_stock", "nombre": articulo, "nuevo_stock": cantidad, "usuario": st.session_state["usuario"]})
                    if res.get("exito"):
                        st.success("¡Stock descontado y registrado en el historial!")
                    else:
                        st.error(f"Error: {res.get('error')}")

    # 2. NUEVO CONSUMIBLE CON MÁS CAMPOS
    with st.expander("📦 Insertar Nuevo Consumible", expanded=False):
        with st.form("form_nuevo_consumible"):
            id_c = st.text_input("ID del Consumible (Manual)")
            nombre = st.text_input("Nombre")
            marca = st.text_input("Marca")
            modelo = st.text_input("Modelo")
            unidad = st.text_input("Unidad (ej. Piezas)")
            stock_actual = st.number_input("Stock Actual", min_value=0.0)
            stock_minimo = st.number_input("Stock Mínimo", min_value=0.0)
            categoria = st.text_input("Categoría")
            submit_cons = st.form_submit_button("Guardar Consumible")
            if submit_cons:
                if id_c and nombre:
                    payload = {"pestana": "Consumibles", "accion": "insertar_fila", "valores": {"ID": id_c, "Nombre": nombre, "Marca": marca, "Modelo": modelo, "Unidad": unidad, "Stock_Actual": stock_actual, "Stock_Minimo": stock_minimo, "Categoria": categoria}}
                    if request_api(payload).get("exito"): st.success("Consumible guardado con éxito.")
                else: st.warning("ID y Nombre son obligatorios.")

    # 3. NUEVO HERRAMENTAL CON MÁS CAMPOS
    with st.expander("🔧 Insertar Nuevo Herramental", expanded=False):
        with st.form("form_nuevo_herramental"):
            id_h = st.text_input("ID del Herramental (Manual)")
            nombre_herr = st.text_input("Nombre de la Herramienta")
            marca_herr = st.text_input("Marca")
            modelo_herr = st.text_input("Modelo")
            unidad_herr = st.text_input("Unidad")
            estado = st.selectbox("Estado", ["Disponible", "En Uso", "En Mantenimiento", "Baja"])
            ultimo_m = st.date_input("Último Mantenimiento")
            proximo_m = st.date_input("Próximo Mantenimiento")
            submit_herr = st.form_submit_button("Guardar Herramienta")
            if submit_herr:
                if id_h and nombre_herr:
                    payload = {"pestana": "Herramental", "accion": "insertar_fila", "valores": {"ID": id_h, "Nombre": nombre_herr, "Marca": marca_herr, "Modelo": modelo_herr, "Unidad": unidad_herr, "Estado": estado, "Ultimo_Mantenimiento": ultimo_m.strftime("%Y-%m-%d"), "Proximo_Mantenimiento": proximo_m.strftime("%Y-%m-%d")}}
                    if request_api(payload).get("exito"): st.success("Herramienta guardada.")
                else: st.warning("ID y Nombre son obligatorios.")

    # 4. GESTIÓN DE NAVAJAS CIRCULARES EN MM 
    with st.expander("⚙️ Gestión de Navajas Circulares (Servicio de Rectificado)", expanded=False):
        st.info("Registre las medidas correspondientes a los servicios de rectificado realizados en milímetros (mm).")
        with st.form("form_navajas_circulares"):
            id_navaja = st.text_input("ID de Operación / Registro")
            juego_navajas = st.text_input("Juego de Navajas Circulares (Nombre/Modelo)")
            medida_actual = st.number_input("Medida Actual (mm)", min_value=0.00, step=0.01, format="%.2f")
            cantidad_removida = st.number_input("Cantidad Removida (mm)", min_value=0.00, step=0.01, format="%.2f")
            filos_malos = st.number_input("Filos Malos (Cantidad)", min_value=0, step=1)
            submit_navajas = st.form_submit_button("Registrar Servicio de Rectificado")
            
            if submit_navajas:
                if id_navaja and juego_navajas:
                    payload = {
                        "pestana": "Gestion_Navajas_Circulares",
                        "accion": "insertar_fila",
                        "valores": {
                            "ID": id_navaja,
                            "Juego_Navajas_Circulares": juego_navajas,
                            "Medida_Actual": medida_actual,
                            "Cantidad_Removida": cantidad_removida,
                            "Filos_Malos": filos_malos,
                            "Fecha_Registro": datetime.now().strftime("%Y-%m-%d")
                        }
                    }
                    if request_api(payload).get("exito"):
                        st.success("¡Servicio de rectificado de navajas circulares registrado en la base de datos!")
                else:
                    st.warning("El ID y el nombre del Juego de Navajas son campos obligatorios.")

    # 5. GESTIÓN DE TICKETS INTERACTIVA (SANGRIAS E ID_TICKET CORREGIDOS)
    with st.expander("📋 Cambiar Estatus de Tickets (Gestión)", expanded=True):
        st.markdown("Presione el botón para marcar una requisición como **Completada** en la nube.")
        df_tickets = fetch_sheet("Tickets_Requisiciones")
        if not df_tickets.empty:
            df_pendientes = df_tickets[df_tickets["Estatus"].astype(str).str.lower() == "pendiente"]
            if df_pendientes.empty:
                st.success("No hay tickets pendientes por completar.")
            else:
                for idx, fila in df_pendientes.iterrows():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        # Mapeado exacto a 'ID_Ticket' como se encuentra en tu Sheets
                        t_id = fila.get('ID_Ticket', idx)
                        t_solicitante = fila.get('Solicitante', 'N/A')
                        t_articulo = fila.get('Articulo', 'N/A')
                        t_cantidad = fila.get('Cantidad', '1')
                        st.write(f"🆔 **ID:** {t_id} | 👤 {t_solicitante} solicita: **{t_articulo}** (Cant: {t_cantidad})")
                    with col2:
                        if st.button(f"Ticket Completado", key=f"btn_comp_{t_id}"):
                            res_t = request_api({"pestana": "Tickets_Requisiciones", "accion": "actualizar_estatus_ticket", "id_ticket": t_id})
                            if res_t.get("exito"):
                                st.success(f"¡Ticket {t_id} completado!")
                                st.rerun()
        else:
            st.info("No hay registros en la pestaña de Tickets.")

# =========================================================================
# 4. CONTROL DE POP-UPS PARA ROL SUPERIOR
# =========================================================================
def revisar_notificaciones_superior():
    """Lanza notificaciones emergentes si hay requisiciones completadas."""
    if st.session_state.get("rol") == "Superior":
        df_t = fetch_sheet("Tickets_Requisiciones")
        if not df_t.empty and "Solicitante" in df_t.columns and "Estatus" in df_t.columns:
            mis_completados = df_t[
                (df_t["Solicitante"].astype(str).str.strip().str.lower() == str(st.session_state["usuario"]).strip().str.lower()) & 
                (df_t["Estatus"].astype(str).str.strip().str.lower() == "completado")
            ]
            if not mis_completados.empty:
                for _, ticket in mis_completados.iterrows():
                    t_id_notif = ticket.get('ID_Ticket', 'Ticket')
                    st.toast(f"🎉 ¡Tu Requisición ID: {t_id_notif} de {ticket['Articulo']} ha sido COMPLETADA!", icon="🎫")

# =========================================================================
# 5. NÚCLEO PRINCIPAL (TABS POR ROL)
# =========================================================================
def main():
    st.set_page_config(page_title="Gestión Web de Insumos V2", layout="wide")
    
    if not sidebar_login():
        st.title("Gestión Central de Insumos")
        st.write("Bienvenido. Esperando autenticación en el menú izquierdo.")
        return

    rol = st.session_state["rol"]
    st.title(f"Panel Principal - Rol: {rol}")
    
    # Ejecutar escáner de pop-ups para el rol Superior
    revisar_notificaciones_superior()

    if rol == "Invitado":
        t1, t2 = st.tabs(["📦 Consumibles", "🔧 Herramental"])
        with t1: renderizar_tabla_consumibles()
        with t2: st.dataframe(fetch_sheet("Herramental"), use_container_width=True)

    elif rol == "Superior":
        t1, t2, t3, t4, t5 = st.tabs(["📦 Consumibles", "🔧 Herramental", "📈 Gráficos de Consumo", "📝 Nuevo Ticket", "⚙️ Navajas Circulares"])
        with t1: renderizar_tabla_consumibles()
        with t2: st.dataframe(fetch_sheet("Herramental"), use_container_width=True)
        with t3: mostrar_graficos()
        with t4: form_ticket()
        with t5: 
            st.subheader("📋 Historial de Rectificados - Navajas Circulares")
            st.dataframe(fetch_sheet("Gestion_Navajas_Circulares"), use_container_width=True)

    elif rol == "Admin":
        t1, t2, t3, t4, t5, t6 = st.tabs([
            "📦 Consumibles", "🔧 Herramental", "📈 Gráficos", "📋 Tickets", "⚙️ Navajas Circulares", "🛠️ Gestión / Stock"
        ])
        with t1: renderizar_tabla_consumibles()
        with t2: st.dataframe(fetch_sheet("Herramental"), use_container_width=True)
        with t3: mostrar_graficos()
        with t4: st.dataframe(fetch_sheet("Tickets_Requisiciones"), use_container_width=True)
        with t5: st.dataframe(fetch_sheet("Gestion_Navajas_Circulares"), use_container_width=True)
        with t6: panel_admin()

if __name__ == "__main__":
    main()
