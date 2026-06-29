import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import ssl
import os

# Desactivar la verificación estricta de certificados SSL (Para redes corporativas)
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# 1. Conexión a la API (URL de la implementación de Apps Script)
URL_API = "https://script.google.com/macros/s/AKfycbz3YZStuc9vFCBm2JuAm38a5gsxNi7qv7d9xoOUJvw83CTLAxcyFk6afm4mWRBzx9T6bQ/exec"

def request_api(payload):
    """Envía peticiones POST al backend (Apps Script)."""
    try:
        # allow_redirects=True es vital para Apps Script ya que Google redirecciona las peticiones POST
        respuesta = requests.post(URL_API, json=payload, allow_redirects=True)
        return respuesta.json()
    except requests.exceptions.JSONDecodeError:
        return {"exito": False, "error": "JSONDecodeError: El servidor no devolvió JSON."}
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
        # Forzar que los nombres de columnas no tengan espacios raros
        df_usuarios.columns = df_usuarios.columns.str.strip()
        
        # Validar si existen las columnas necesarias
        if "Usuario" in df_usuarios.columns and "Contraseña" in df_usuarios.columns:
            # Buscamos la fila que coincida de forma exacta
            coincidencia = df_usuarios[
                (df_usuarios["Usuario"].astype(str).str.strip() == str(usuario_ingresado).strip()) & 
                (df_usuarios["Contraseña"].astype(str).str.strip() == str(contrasena_ingresada).strip())
            ]
            if not coincidencia.empty:
                # Retornamos el Rol asignado (si no existe la columna Rol, por defecto es Invitado)
                return coincidencia.iloc[0].get("Rol", "Invitado")
    return None

# 2. Login por Roles
def sidebar_login():
    """Maneja el inicio de sesión utilizando el validador local de Sheets."""
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
                # Llamamos a nuestra validación directa contra el Google Sheets
                rol_detectado = verificar_credenciales_local(usuario, contrasena)
                if rol_detectado:
                    st.session_state["rol"] = rol_detectado
                    st.session_state["usuario"] = usuario
                    st.sidebar.success("¡Acceso concedido!")
                    st.rerun()
                else:
                    st.sidebar.error("Credenciales incorrectas o columnas desalineadas en Sheets")
        return False
    else:
        st.sidebar.success(f"Usuario: {st.session_state['usuario']} \n\nRol: {st.session_state['rol']}")
        if st.sidebar.button("Cerrar Sesión"):
            st.session_state["rol"] = None
            st.session_state["usuario"] = None
            st.rerun()
        return True

# 4. Gráficos de Consumo
def mostrar_graficos():
    st.subheader("📊 Top 5 Insumos Más Utilizados")
    df_consumos = fetch_sheet("Historial_Consumos")
    
    if not df_consumos.empty and "Articulo" in df_consumos.columns and "Cantidad_Retirada" in df_consumos.columns:
        df_consumos["Cantidad_Retirada"] = pd.to_numeric(df_consumos["Cantidad_Retirada"], errors="coerce")
        df_top = df_consumos.groupby("Articulo")["Cantidad_Retirada"].sum().nlargest(5).reset_index()
        
        fig = px.bar(
            df_top, 
            x="Articulo", 
            y="Cantidad_Retirada", 
            color="Cantidad_Retirada",
            title="Histórico de Salidas por Artículo",
            labels={"Cantidad_Retirada": "Cantidad Total", "Articulo": "Insumo"},
            color_continuous_scale="Blues"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay suficientes datos en el Historial de Consumos para graficar.")

def form_ticket():
    st.subheader("🎫 Crear Ticket de Requisición")
    with st.form("form_nuevo_ticket"):
        articulo = st.text_input("Artículo")
        cantidad = st.number_input("Cantidad", min_value=1)
        urgencia = st.selectbox("Urgencia", ["Normal", "Alta"])
        especificacion = st.text_area("Especificación")
        link = st.text_input("Link Cotización")
        
        submit = st.form_submit_button("Enviar Requisición")
        if submit:
            if articulo:
                payload = {
                    "pestana": "Tickets_Requisiciones",
                    "accion": "insertar_fila",
                    "valores": {
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
                    st.success("¡Ticket de requisición registrado correctamente en Google Sheets!")
                else:
                    st.error(f"Error al registrar: {res.get('error', 'Error desconocido')}")
            else:
                st.warning("Por favor, introduce el nombre del artículo.")

def panel_admin():
    st.subheader("🛠️ Panel de Gestión y Movimientos")
    
    with st.expander("🔻 Modificar Stock (Consumo Manual)", expanded=False):
        st.markdown("Descuenta existencias del inventario actual y registra la salida en el Historial.")
        with st.form("form_consumo"):
            articulo = st.text_input("Artículo a consumir (Exactamente como está en la base)")
            cantidad = st.number_input("Cantidad a retirar", min_value=1.0, step=1.0)
            
            submit = st.form_submit_button("Aplicar Consumo")
            if submit:
                if articulo:
                    payload = {
                        "pestana": "Consumibles",
                        "accion": "actualizar_stock",
                        "nombre": articulo,
                        "nuevo_stock": cantidad
                    }
                    res = request_api(payload)
                    if res.get("exito"):
                        st.success("¡Stock modificado con éxito en el sistema!")
                    else:
                        st.error(f"Fallo al procesar: {res.get('error', 'No se encontró el artículo')}")
                else:
                    st.warning("Por favor, introduce el nombre del artículo.")

    with st.expander("📦 Insertar Nuevo Consumible", expanded=False):
        with st.form("form_nuevo_consumible"):
            nombre = st.text_input("Nombre del Consumible")
            unidad = st.text_input("Unidad (ej. Piezas, Cajas, Litros)")
            stock_actual = st.number_input("Stock Actual", min_value=0.0, step=1.0)
            stock_minimo = st.number_input("Stock Mínimo", min_value=0.0, step=1.0)
            categoria = st.text_input("Categoría")

            submit_cons = st.form_submit_button("Guardar Consumible")
            if submit_cons:
                if nombre:
                    payload = {
                        "pestana": "Consumibles",
                        "accion": "insertar_fila",
                        "valores": {
                            "Nombre": nombre,
                            "Unidad": unidad,
                            "Stock_Actual": stock_actual,
                            "Stock_Minimo": stock_minimo,
                            "Categoria": categoria
                        }
                    }
                    res = request_api(payload)
                    if res.get("exito"):
                        st.success("¡Consumible registrado con éxito!")
                    else:
                        st.error(f"Error al registrar: {res.get('error', 'Error desconocido')}")
                else:
                    st.warning("El nombre del consumible es obligatorio.")

    with st.expander("🔧 Insertar Nuevo Herramental", expanded=False):
        with st.form("form_nuevo_herramental"):
            nombre_herr = st.text_input("Nombre de la Herramienta")
            unidad_herr = st.text_input("Unidad (ej. Pieza, Equipo)")
            estado = st.selectbox("Estado", ["Disponible", "En Uso", "En Mantenimiento", "Baja"])
            ultimo_mantenimiento = st.date_input("Último Mantenimiento")
            proximo_mantenimiento = st.date_input("Próximo Mantenimiento")

            submit_herr = st.form_submit_button("Guardar Herramienta")
            if submit_herr:
                if nombre_herr:
                    payload = {
                        "pestana": "Herramental",
                        "accion": "insertar_fila",
                        "valores": {
                            "Nombre": nombre_herr,
                            "Unidad": unidad_herr,
                            "Estado": estado,
                            "Ultimo_Mantenimiento": ultimo_mantenimiento.strftime("%Y-%m-%d"),
                            "Proximo_Mantenimiento": proximo_mantenimiento.strftime("%Y-%m-%d")
                        }
                    }
                    res = request_api(payload)
                    if res.get("exito"):
                        st.success("¡Herramienta registrada con éxito!")
                    else:
                        st.error(f"Error al registrar: {res.get('error', 'Error desconocido')}")
                else:
                    st.warning("El nombre de la herramienta es obligatorio.")
                
    st.divider()
    st.caption("Nota: El sistema ahora permite insertar datos dinámicos en todas las pestañas desde los formularios superiores de manera segura.")

# 3. Sistema de Pestañas (Tabs) según el Rol
def main():
    st.set_page_config(page_title="Gestión Web de Insumos", layout="wide")
    
    if not sidebar_login():
        st.title("Gestión Central de Insumos")
        st.write("Bienvenido. Esperando autenticación en el menú izquierdo.")
        return

    rol = st.session_state["rol"]
    st.title(f"Panel Principal - Rol: {rol}")

    if rol == "Invitado":
        t1, t2 = st.tabs(["📦 Consumibles", "🔧 Herramental"])
        with t1: st.dataframe(fetch_sheet("Consumibles"), use_container_width=True)
        with t2: st.dataframe(fetch_sheet("Herramental"), use_container_width=True)

    elif rol == "Superior":
        t1, t2, t3, t4 = st.tabs(["📦 Consumibles", "🔧 Herramental", "📈 Gráficos de Consumo", "📝 Nuevo Ticket"])
        with t1: st.dataframe(fetch_sheet("Consumibles"), use_container_width=True)
        with t2: st.dataframe(fetch_sheet("Herramental"), use_container_width=True)
        with t3: mostrar_graficos()
        with t4: form_ticket()

    elif rol == "Admin":
        t1, t2, t3, t4, t5 = st.tabs([
            "📦 Consumibles", "🔧 Herramental", "📈 Gráficos", "📋 Tickets", "⚙️ Gestión / Stock"
        ])
        with t1: st.dataframe(fetch_sheet("Consumibles"), use_container_width=True)
        with t2: st.dataframe(fetch_sheet("Herramental"), use_container_width=True)
        with t3: mostrar_graficos()
        with t4: st.dataframe(fetch_sheet("Tickets_Requisiciones"), use_container_width=True)
        with t5: panel_admin()

if __name__ == "__main__":
    main()