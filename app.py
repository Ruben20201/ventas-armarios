import os
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import cloudinary
import cloudinary.uploader
import cloudinary.api
from sqlalchemy import func

# ==========================================
# 1. INICIALIZACIÓN Y CONFIGURACIÓN DE LA APP
# ==========================================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'clave_secreta_super_segura')

# Configuración de base de datos (Render PostgreSQL o SQLite local)
db_url = os.environ.get('DATABASE_URL', 'sqlite:///armarios.db')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuración de subida de imágenes (Respaldo local y Cloudinary)
UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

cloudinary.config(
    cloud_name = 'ljsxuy3b',
    api_key = '572777632729745',
    api_secret = 'HW8Wklq-2FgJrZsqsNlQPhIw5vk'
)

# Inicialización única de SQLAlchemy y LoginManager
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'  # type: ignore

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))


# ==========================================
# 2. MODELOS DE LA BASE DE DATOS
# ==========================================
class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(20), nullable=False)  # 'fabrica' o 'vendedor'
    nombre_local = db.Column(db.String(100), nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Mueble(db.Model):
    __tablename__ = 'mueble'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    precio = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)
    imagen = db.Column(db.String(255), nullable=True)
    ubicacion = db.Column(db.String(50), default='Fábrica')


class Venta(db.Model):
    __tablename__ = 'ventas'
    id = db.Column(db.Integer, primary_key=True)
    numero_factura = db.Column(db.String(20), unique=True, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relación con el vendedor
    vendedor_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    vendedor = db.relationship('Usuario', backref='ventas')

    # Relación con el mueble
    mueble_id = db.Column(db.Integer, db.ForeignKey('mueble.id'), nullable=False)
    mueble = db.relationship('Mueble', backref='ventas')

    cantidad = db.Column(db.Integer, nullable=False)
    precio_unitario = db.Column(db.Float, nullable=False)
    total = db.Column(db.Float, nullable=False)
    
    # Columnas de los datos del cliente
    cliente_nombre = db.Column(db.String(100), nullable=True)
    cliente_telefono = db.Column(db.String(50), nullable=True)
    cliente_direccion = db.Column(db.String(200), nullable=True)
    localidad_bogota = db.Column(db.String(50), nullable=True)
    cliente_piso = db.Column(db.String(50), nullable=True)
    comentario_venta = db.Column(db.Text, nullable=True)


# ==========================================
# 3. CONTEXTO DE INICIO Y MIGRACIÓN AUTOMÁTICA
# ==========================================
with app.app_context():
    db.create_all()
    
    # Actualización automática de columnas en Render (PostgreSQL) o local
    try:
        db.session.execute(db.text("ALTER TABLE ventas ADD COLUMN IF NOT EXISTS cliente_nombre VARCHAR(100);"))
        db.session.execute(db.text("ALTER TABLE ventas ADD COLUMN IF NOT EXISTS cliente_telefono VARCHAR(50);"))
        db.session.execute(db.text("ALTER TABLE ventas ADD COLUMN IF NOT EXISTS cliente_direccion VARCHAR(200);"))
        db.session.execute(db.text("ALTER TABLE ventas ADD COLUMN IF NOT EXISTS localidad_bogota VARCHAR(50);"))
        db.session.execute(db.text("ALTER TABLE ventas ADD COLUMN IF NOT EXISTS cliente_piso VARCHAR(50);"))
        db.session.execute(db.text("ALTER TABLE ventas ADD COLUMN IF NOT EXISTS comentario_venta TEXT;"))
        db.session.execute(db.text("ALTER TABLE ventas DROP COLUMN IF EXISTS cliente_documento;"))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print("Nota sobre la actualización de columnas:", e)

    # Creación de usuarios por defecto si no existen
    if not Usuario.query.filter_by(username='fabrica').first():
        fabrica = Usuario(username='fabrica', rol='fabrica', nombre_local='Fábrica Central Armarios')  # type: ignore
        fabrica.set_password('admin123')
        db.session.add(fabrica)

    if not Usuario.query.filter_by(username='vendedor1').first():
        vendedor = Usuario(username='vendedor1', rol='vendedor', nombre_local='Local Centro')  # type: ignore
        vendedor.set_password('vendedor123')
        db.session.add(vendedor)
        
    db.session.commit()


# ==========================================
# 4. IMÁGENES PRESELECCIONADAS DE CLOUDINARY
# ==========================================
IMAGENES_PRESELECCIONADAS = [
    {"nombre": "Armario Clásico Marrón", "url": "https://res.cloudinary.com/ljsxuy3b/image/upload/v1/armarios_inventario/armario1.jpg"},
    {"nombre": "Armario Moderno Blanco", "url": "https://res.cloudinary.com/ljsxuy3b/image/upload/v1/armarios_inventario/armario2.jpg"},
    {"nombre": "Armario Juvenil con Espejo", "url": "https://res.cloudinary.com/ljsxuy3b/image/upload/v1/armarios_inventario/armario3.jpg"}
]


# ==========================================
# 5. RUTAS DEL SISTEMA
# =================================