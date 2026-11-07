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

# 1. Inicialización de la App Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'clave_secreta_super_segura')

# Configuración de base de datos (Render PostgreSQL o SQLite local)
db_url = os.environ.get('DATABASE_URL', 'sqlite:///armarios.db')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuración de subida de imágenes locales (respaldo)
UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)

# Configuración de Cloudinary
cloudinary.config(
    cloud_name = 'ljsxuy3b',
    api_key = '572777632729745',
    api_secret = 'HW8Wklq-2FgJrZsqsNlQPhIw5vk'
)

login_manager = LoginManager(app)
login_manager.login_view = 'login'  # type: ignore


# --- 2. MODELOS DE LA BASE DE DATOS ---

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(20), nullable=False) # 'fabrica' o 'vendedor'
    nombre_local = db.Column(db.String(100), nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Mueble(db.Model):
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
    
    vendedor_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    vendedor = db.relationship('Usuario', backref='ventas')
    
    mueble_id = db.Column(db.Integer, db.ForeignKey('mueble.id'), nullable=False)
    mueble = db.relationship('Mueble', backref=db.backref('ventas_asociadas', cascade='all, delete-orphan', lazy=True))
    
    cantidad = db.Column(db.Integer, nullable=False)
    precio_unitario = db.Column(db.Float, nullable=False)
    total = db.Column(db.Float, nullable=False)
    
    cliente_nombre = db.Column(db.String(100), nullable=False)
    cliente_documento = db.Column(db.String(50), nullable=False)
    cliente_telefono = db.Column(db.String(50), nullable=True)
    cliente_direccion = db.Column(db.String(200), nullable=True)

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))


# --- 3. CREACIÓN DE TABLAS Y USUARIOS GLOBAL (Para Render y Local) ---
with app.app_context():
    db.create_all()
    
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


# --- 4. LISTA DE IMÁGENES PRESELECCIONADAS ---
IMAGENES_PRESELECCIONADAS = [
    {"nombre": "Armario Clásico Marrón", "url": "https://res.cloudinary.com/ljsxuy3b/image/upload/v1/armarios_inventario/armario1.jpg"},
    {"nombre": "Armario Moderno Blanco", "url": "https://res.cloudinary.com/ljsxuy3b/image/upload/v1/armarios_inventario/armario2.jpg"},
    {"nombre": "Armario Juvenil con Espejo", "url": "https://res.cloudinary.com/ljsxuy3b/image/upload/v1/armarios_inventario/armario3.jpg"}
]


# --- 5. RUTAS DE AUTENTICACIÓN Y DEL SISTEMA ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        usuario = Usuario.query.filter_by(username=username).first()

        if usuario and usuario.check_password(password):
            login_user(usuario)
            return redirect(url_for('catalogo'))
        else:
            flash('Usuario o contraseña incorrectos.', 'danger')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def catalogo():
    muebles = Mueble.query.all()
    return render_template('catalogo.html', muebles=muebles)

@app.route('/mueble/<int:id>/eliminar', methods=['POST'])
@login_required
def eliminar_mueble(id):
    if current_user.rol != 'fabrica':
        flash('Acceso denegado: Solo el administrador puede eliminar muebles.', 'danger')
        return redirect(url_for('catalogo'))

    mueble = Mueble.query.get_or_404(id)
    db.session.delete(mueble)
    db.session.commit()
    
    flash(f'El mueble "{mueble.nombre}" ha sido eliminado correctamente.', 'success')
    return redirect(url_for('gestionar_muebles'))

@app.route('/muebles/gestionar', methods=['GET', 'POST'])
@login_required
def gestionar_muebles():
    if current_user.rol != 'fabrica':
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('catalogo'))

    if request.method == 'POST':
        nombre = request.form.get('nombre')
        descripcion = request.form.get('descripcion')
        precio = float(request.form.get('precio') or 0)
        stock = int(request.form.get('stock') or 0)
        ubicacion_form = request.form.get('ubicacion', 'Fábrica')

        imagen_elegida = request.form.get('imagen_catalogo')
        file = request.files.get('imagen_archivo')

        filename = 'default.jpg'

        if file and file.filename != '':
            upload_result = cloudinary.uploader.upload(file, folder="armarios_inventario")
            filename = upload_result.get('secure_url')
        elif imagen_elegida:
            filename = imagen_elegida

        nuevo_mueble = Mueble(
            nombre=nombre,  # type: ignore
            descripcion=descripcion,  # type: ignore
            precio=precio,  # type: ignore
            stock=stock,  # type: ignore
            imagen=filename,  # type: ignore
            ubicacion=ubicacion_form,  # type: ignore
        )
        db.session.add(nuevo_mueble)
        db.session.commit()
        flash('Mueble agregado con éxito.', 'success')
        return redirect(url_for('gestionar_muebles'))

    muebles = Mueble.query.all()
    return render_template('gestionar_muebles.html', muebles=muebles, imagenes_stock=IMAGENES_PRESELECCIONADAS)

@app.route('/mueble/<int:id>/cambiar-ubicacion', methods=['POST'])
@login_required
def cambiar_ubicacion(id):
    if current_user.rol != 'fabrica':
        flash('Acceso denegado: Solo el administrador puede cambiar la ubicación.', 'danger')
        return redirect(url_for('catalogo'))

    mueble = Mueble.query.get_or_404(id)
    if mueble.ubicacion == 'Fábrica':
        mueble.ubicacion = 'Local'
    else:
        mueble.ubicacion = 'Fábrica'

    db.session.commit()
    flash(f'La ubicación de {mueble.nombre} ha sido actualizada con éxito.', 'success')
    return redirect(url_for('catalogo'))

@app.route('/muebles/actualizar_stock/<int:id>', methods=['POST'])
@login_required
def actualizar_stock(id):
    if current_user.rol != 'fabrica':
        flash('Acceso restringido.', 'danger')
        return redirect(url_for('catalogo'))
    
    mueble = Mueble.query.get_or_404(id)
    nuevo_stock = int(request.form.get('stock') or 0)
    mueble.stock = nuevo_stock
    db.session.commit()
    flash(f'Stock actualizado para {mueble.nombre}.', 'success')
    return redirect(url_for('gestionar_muebles'))

@app.route('/venta/nueva/<int:mueble_id>', methods=['GET', 'POST'])
@login_required
def nueva_venta(mueble_id):
    mueble = Mueble.query.get_or_404(mueble_id)

    if request.method == 'POST':
        cantidad = int(request.form.get('cantidad') or 1)
        
        if cantidad > mueble.stock:
            flash(f'No hay suficiente stock. Disponible: {mueble.stock}', 'danger')
            return redirect(url_for('nueva_venta', mueble_id=mueble.id))

        mueble.stock -= cantidad

        total_ventas = Venta.query.count() + 1
        num_factura = f"FAC-{datetime.now().strftime('%Y%m%d')}-{total_ventas:03d}"

        precio_unitario = mueble.precio
        total = cantidad * precio_unitario

        venta = Venta(
            numero_factura=num_factura,  # type: ignore
            vendedor_id=current_user.id,  # type: ignore
            mueble_id=mueble.id,  # type: ignore
            cantidad=cantidad,  # type: ignore
            precio_unitario=precio_unitario,  # type: ignore
            total=total,  # type: ignore
            cliente_nombre=request.form.get('cliente_nombre'),  # type: ignore
            cliente_documento=request.form.get('cliente_documento'),  # type: ignore
            cliente_telefono=request.form.get('cliente_telefono'),  # type: ignore
            cliente_direccion=request.form.get('cliente_direccion')  # type: ignore
        )

        db.session.add(venta)
        db.session.commit()

        flash('Venta registrada con éxito. Generando factura...', 'success')
        return redirect(url_for('ver_factura', venta_id=venta.id))

    return render_template('nueva_venta.html', mueble=mueble)

@app.route('/factura/<int:venta_id>')
@login_required
def ver_factura(venta_id):
    venta = Venta.query.get_or_404(venta_id)
    return render_template('factura.html', venta=venta)

@app.route('/ventas/historial')
@login_required
def historial_ventas():
    if current_user.rol == 'fabrica':
        ventas = Venta.query.order_by(Venta.fecha.desc()).all()
    else:
        ventas = Venta.query.filter_by(vendedor_id=current_user.id).order_by(Venta.fecha.desc()).all()
    return render_template('historial_ventas.html', ventas=ventas)


# --- 6. BLOQUE LOCAL ABSOLUTO (Solo para ejecutar en tu PC) ---
if __name__ == '__main__':
    app.run(debug=True)