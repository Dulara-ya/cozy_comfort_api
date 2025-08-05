# web_server.py
# Cozy Comfort Web Server - Final All-in-One Version
# This script automatically handles database creation, table setup, and data insertion before starting the web server.

import os
import traceback
from datetime import datetime
from functools import wraps
from decimal import Decimal, InvalidOperation

import mysql.connector
from flask import Flask, request, jsonify, render_template_string, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

# ================================
# DATABASE SETUP AND CONNECTION
# ================================
class DatabaseManager:
    """
    Manages the MySQL database connection, setup, and initial data population.
    The setup process is triggered automatically when the server starts.
    """
    def __init__(self):
        self.config = {
            'host': os.environ.get('DB_HOST', 'localhost'),
            'user': os.environ.get('DB_USER', 'root'),
            'password': os.environ.get('DB_PASSWORD', ''),
            'database': os.environ.get('DB_NAME', 'cozy_comfort_db'),
            'port': int(os.environ.get('DB_PORT', 3306)),
            'charset': 'utf8mb4',
            # -- ADD THESE TWO LINES FOR RENDER DATABASE --
            'ssl_ca': '/opt/render/etc/tls/ca-bundle.crt.pem',
            'ssl_verify_identity': True
            # ---------------------------------------------
        }
        self.init_database()

    def get_connection(self):
        """Establishes and returns a database connection."""
        try:
            conn = mysql.connector.connect(**self.config)
            return conn
        except mysql.connector.Error as err:
            print(f"❌ Database connection error: {err}")
            return None

    def init_database(self):
        """Coordinates the entire database setup process."""
        try:
            print("--- Starting Database Initialization ---")
            temp_config = self.config.copy()
            db_name = temp_config.pop('database')
            
            conn = mysql.connector.connect(**temp_config)
            cursor = conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            print(f"✅ Database '{db_name}' is ready.")
            cursor.close()
            conn.close()

            self.create_tables()
            self.insert_sample_data()
            print("\n✅ Database setup complete and is persistent.")
            
        except mysql.connector.Error as err:
            print(f"❌ FATAL: Database initialization failed: {err}")
            exit(1)

    def create_tables(self):
        """Creates all required tables if they do not already exist."""
        conn = self.get_connection()
        if not conn:
            print("❌ FATAL: Could not connect to the database to create tables.")
            exit(1)
        
        print("\nChecking and creating tables...")
        cursor = conn.cursor()
        try:
            cursor.execute("CREATE TABLE IF NOT EXISTS users (id INT AUTO_INCREMENT PRIMARY KEY, username VARCHAR(100) UNIQUE NOT NULL, email VARCHAR(150) UNIQUE NOT NULL, password VARCHAR(255) NOT NULL, user_type ENUM('manufacturer', 'distributor', 'seller') NOT NULL, company_name VARCHAR(200), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP) ENGINE=InnoDB;")
            cursor.execute("CREATE TABLE IF NOT EXISTS products (id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(200) NOT NULL, model VARCHAR(100) NOT NULL, material VARCHAR(100), size VARCHAR(50), color VARCHAR(50), price DECIMAL(10,2) NOT NULL, manufacturer_id INT, FOREIGN KEY (manufacturer_id) REFERENCES users(id) ON DELETE SET NULL) ENGINE=InnoDB;")
            cursor.execute("CREATE TABLE IF NOT EXISTS inventory (id INT AUTO_INCREMENT PRIMARY KEY, product_id INT NOT NULL, owner_id INT NOT NULL, owner_type ENUM('manufacturer', 'distributor', 'seller') NOT NULL, quantity INT NOT NULL DEFAULT 0, FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE, FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE, UNIQUE KEY unique_inventory (product_id, owner_id, owner_type)) ENGINE=InnoDB;")
            cursor.execute("CREATE TABLE IF NOT EXISTS orders (id INT AUTO_INCREMENT PRIMARY KEY, order_number VARCHAR(100) UNIQUE NOT NULL, seller_id INT NOT NULL, distributor_id INT, customer_name VARCHAR(200) NOT NULL, customer_email VARCHAR(150), total_amount DECIMAL(10,2) NOT NULL, status ENUM('pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled') DEFAULT 'pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, confirmed_by_id INT, FOREIGN KEY (seller_id) REFERENCES users(id) ON DELETE CASCADE, FOREIGN KEY (distributor_id) REFERENCES users(id) ON DELETE SET NULL, FOREIGN KEY (confirmed_by_id) REFERENCES users(id) ON DELETE SET NULL) ENGINE=InnoDB;")
            cursor.execute("CREATE TABLE IF NOT EXISTS order_items (id INT AUTO_INCREMENT PRIMARY KEY, order_id INT NOT NULL, product_id INT NOT NULL, quantity INT NOT NULL, unit_price DECIMAL(10,2) NOT NULL, FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE, FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE) ENGINE=InnoDB;")
            cursor.execute("CREATE TABLE IF NOT EXISTS distributor_sellers (distributor_id INT NOT NULL, seller_id INT NOT NULL, FOREIGN KEY (distributor_id) REFERENCES users(id) ON DELETE CASCADE, FOREIGN KEY (seller_id) REFERENCES users(id) ON DELETE CASCADE, PRIMARY KEY (distributor_id, seller_id)) ENGINE=InnoDB;")
            conn.commit()
            print("  - All tables are present.")
        except mysql.connector.Error as err:
            print(f"❌ Error during table creation: {err}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()

    def insert_sample_data(self):
        """Inserts sample data only if the 'users' table is empty."""
        conn = self.get_connection()
        if not conn: return
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM users")
            if cursor.fetchone()[0] > 0:
                print("  - Database already contains data. Skipping sample data insertion.")
                return

            print("  - Database is empty. Inserting sample data...")
            users = [ 
                (1, 'cozy_mfg', 'mfg@cozy.com', generate_password_hash('pass'), 'manufacturer', 'Cozy Comfort MFG'), 
                (2, 'metro_dist', 'dist@metro.com', generate_password_hash('pass'), 'distributor', 'Metro Distribution'), 
                (4, 'comfort_store', 'seller@comfort.com', generate_password_hash('pass'), 'seller', 'The Comfort Store') 
            ]
            cursor.executemany("INSERT INTO users (id, username, email, password, user_type, company_name) VALUES (%s, %s, %s, %s, %s, %s)", users)
            products = [ (1, 'Ultra Soft Fleece Blanket', 'USF-001', 'Fleece', 'Queen', 'Blue', 45.99, 1), (2, 'Premium Wool Blanket', 'PWB-002', 'Wool', 'King', 'Gray', 89.99, 1), (3, 'Cotton Comfort Throw', 'CCT-003', 'Cotton', 'Throw', 'Beige', 29.99, 1) ]
            cursor.executemany("INSERT INTO products (id, name, model, material, size, color, price, manufacturer_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", products)
            inventory = [ (1, 1, 1, 'manufacturer', 500), (2, 2, 1, 'manufacturer', 300), (3, 3, 1, 'manufacturer', 750), (4, 1, 2, 'distributor', 50), (5, 2, 2, 'distributor', 30), (6, 1, 4, 'seller', 10), (7, 2, 4, 'seller', 5) ]
            cursor.executemany("INSERT INTO inventory (id, product_id, owner_id, owner_type, quantity) VALUES (%s, %s, %s, %s, %s)", inventory)
            cursor.execute("INSERT INTO distributor_sellers (distributor_id, seller_id) VALUES (2, 4)")
            conn.commit()
            print("  - Sample data inserted successfully.")
        except mysql.connector.Error as err:
            print(f"❌ Error inserting sample data: {err}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()

# ================================
# SERVICE LAYER
# ================================
class BaseService:
    db = DatabaseManager()
    def handle_error(self, e, operation):
        traceback.print_exc()
        return jsonify({'error': f'An error occurred during {operation}.', 'details': str(e)}), 500

class AuthenticationService(BaseService):
    def login(self, username, password):
        conn = self.db.get_connection()
        if not conn: return jsonify({'error': 'DB connection failed'}), 500
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id, username, password, user_type, company_name FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            if user and check_password_hash(user['password'], password):
                session.clear()
                session['user_id'], session['user_type'], session['username'], session['company_name'] = user['id'], user['user_type'], user['username'], user['company_name']
                return jsonify({'success': True, 'message': 'Login successful.','user': { 'id': user['id'], 'type': user['user_type'], 'username': user['username'], 'company_name': user['company_name'] }})
            return jsonify({'error': 'Invalid username or password'}), 401
        except mysql.connector.Error as e: return self.handle_error(e, "logging in")
        finally: conn.close()

    def logout(self):
        session.clear()
        return jsonify({'success': True, 'message': 'You have been logged out.'})

    def get_session(self):
        if 'user_id' in session:
            return jsonify({'is_logged_in': True, 'user': { 'id': session['user_id'], 'type': session['user_type'], 'username': session['username'], 'company_name': session['company_name'] }})
        return jsonify({'is_logged_in': False})

class ManufacturerService(BaseService):
    def get_dashboard_data(self, user_id):
        conn = self.db.get_connection()
        if not conn: return jsonify({'error': 'DB connection failed'}), 500
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT i.product_id, p.name, p.model, i.quantity FROM inventory i JOIN products p ON i.product_id = p.id WHERE i.owner_id = %s ORDER BY p.name", (user_id,))
            inventory = cursor.fetchall()
            cursor.execute("SELECT o.id, o.order_number, u_seller.company_name as seller, u_dist.company_name as distributor, o.status, o.created_at FROM orders o JOIN users u_seller ON o.seller_id = u_seller.id LEFT JOIN users u_dist ON o.distributor_id = u_dist.id ORDER BY o.created_at DESC")
            orders = cursor.fetchall()
            return jsonify({'inventory': inventory, 'orders': orders})
        except mysql.connector.Error as e: return self.handle_error(e, "fetching manufacturer data")
        finally: conn.close()

    def create_product(self, user_id, data):
        conn = self.db.get_connection()
        if not conn: return jsonify({'error': 'DB connection failed'}), 500
        try:
            name, model, price, initial_stock = data.get('name'), data.get('model'), Decimal(data.get('price')), int(data.get('initial_stock'))
            if not all([name, model, price, initial_stock is not None]): return jsonify({'error': 'Missing required fields'}), 400
            conn.start_transaction()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO products (name, model, material, size, color, price, manufacturer_id) VALUES (%s, %s, %s, %s, %s, %s, %s)", (name, model, data.get('material'), data.get('size'), data.get('color'), price, user_id))
            product_id = cursor.lastrowid
            cursor.execute("INSERT INTO inventory (product_id, owner_id, owner_type, quantity) VALUES (%s, %s, 'manufacturer', %s)", (product_id, user_id, initial_stock))
            conn.commit()
            return jsonify({'success': True, 'message': f"Product '{name}' created!", 'product_id': product_id})
        except (mysql.connector.Error, InvalidOperation, ValueError) as e: conn.rollback(); return self.handle_error(e, "creating product")
        finally: conn.close()

    def update_inventory(self, product_id, quantity, user_id):
        conn = self.db.get_connection()
        if not conn: return jsonify({'error': 'DB connection failed'}), 500
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE inventory SET quantity = %s WHERE product_id = %s AND owner_id = %s", (quantity, product_id, user_id))
            conn.commit()
            if cursor.rowcount == 0: return jsonify({'error': 'Product not found or quantity is the same'}), 404
            return jsonify({'success': True, 'message': 'Inventory updated successfully.'})
        except mysql.connector.Error as e: conn.rollback(); return self.handle_error(e, "updating inventory")
        finally: conn.close()
        
class DistributorService(BaseService):
    def get_dashboard_data(self, user_id):
        conn = self.db.get_connection()
        if not conn: return jsonify({'error': 'DB connection failed'}), 500
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT p.id, p.name, p.model, p.price, COALESCE(i.quantity, 0) as your_stock, (SELECT quantity FROM inventory mi WHERE mi.product_id = p.id AND mi.owner_type = 'manufacturer') as manufacturer_stock FROM products p LEFT JOIN inventory i ON p.id = i.product_id AND i.owner_id = %s ORDER BY p.name", (user_id,))
            inventory = cursor.fetchall()
            cursor.execute("SELECT o.id, o.order_number, u_seller.company_name AS seller, o.status, o.created_at, o.customer_name FROM orders o JOIN users u_seller ON o.seller_id = u_seller.id WHERE o.distributor_id = %s ORDER BY o.created_at DESC", (user_id,))
            orders = cursor.fetchall()
            return jsonify({'inventory': inventory, 'orders': orders})
        except mysql.connector.Error as e: return self.handle_error(e, "fetching distributor data")
        finally: conn.close()

    def order_from_manufacturer(self, product_id, quantity, user_id):
        conn = self.db.get_connection()
        if not conn: return jsonify({'error': 'DB connection failed'}), 500
        try:
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT quantity, owner_id FROM inventory WHERE product_id = %s AND owner_type = 'manufacturer' FOR UPDATE", (product_id,))
            mfg_inv = cursor.fetchone()
            if not mfg_inv or mfg_inv['quantity'] < quantity: conn.rollback(); return jsonify({'error': 'Insufficient manufacturer stock.'}), 400
            cursor.execute("UPDATE inventory SET quantity = quantity - %s WHERE product_id = %s AND owner_id = %s", (quantity, product_id, mfg_inv['owner_id']))
            cursor.execute("INSERT INTO inventory (product_id, owner_id, owner_type, quantity) VALUES (%s, %s, 'distributor', %s) ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)", (product_id, user_id, quantity))
            conn.commit()
            return jsonify({'success': True, 'message': f'Successfully ordered {quantity} units.'})
        except mysql.connector.Error as e: conn.rollback(); return self.handle_error(e, "ordering from manufacturer")
        finally: conn.close()
        
class SellerService(BaseService):
    def get_dashboard_data(self, user_id):
        conn = self.db.get_connection()
        if not conn: return jsonify({'error': 'DB connection failed'}), 500
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT p.id, p.name, p.model, p.price, p.manufacturer_id, COALESCE(si.quantity, 0) as seller_stock, COALESCE(di.quantity, 0) as distributor_stock FROM products p LEFT JOIN inventory si ON p.id = si.product_id AND si.owner_id = %s LEFT JOIN distributor_sellers ds ON ds.seller_id = %s LEFT JOIN inventory di ON p.id = di.product_id AND di.owner_id = ds.distributor_id ORDER BY p.name", (user_id, user_id))
            products = cursor.fetchall()
            cursor.execute("SELECT o.*, u_confirmer.company_name AS confirmer_name FROM orders o LEFT JOIN users u_confirmer ON o.confirmed_by_id = u_confirmer.id WHERE o.seller_id = %s ORDER BY o.created_at DESC", (user_id,))
            orders = cursor.fetchall()
            return jsonify({'products': products, 'orders': orders})
        except mysql.connector.Error as e: return self.handle_error(e, "fetching seller data")
        finally: conn.close()

    def order_from_distributor(self, user_id, product_id, quantity):
        conn = self.db.get_connection()
        if not conn: return jsonify({'error': 'DB connection failed'}), 500
        try:
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT distributor_id FROM distributor_sellers WHERE seller_id = %s", (user_id,))
            dist_res = cursor.fetchone()
            if not dist_res: return jsonify({'error': 'You are not assigned to a distributor.'}), 400
            distributor_id = dist_res['distributor_id']
            cursor.execute("SELECT quantity FROM inventory WHERE product_id = %s AND owner_id = %s AND owner_type = 'distributor' FOR UPDATE", (product_id, distributor_id))
            dist_inv = cursor.fetchone()
            if not dist_inv or dist_inv['quantity'] < quantity: conn.rollback(); return jsonify({'error': 'Insufficient distributor stock.'}), 400
            cursor.execute("UPDATE inventory SET quantity = quantity - %s WHERE product_id = %s AND owner_id = %s", (quantity, product_id, distributor_id))
            cursor.execute("INSERT INTO inventory (product_id, owner_id, owner_type, quantity) VALUES (%s, %s, 'seller', %s) ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)", (product_id, user_id, quantity))
            conn.commit()
            return jsonify({'success': True, 'message': f'Successfully ordered {quantity} units.'})
        except mysql.connector.Error as e: conn.rollback(); return self.handle_error(e, "ordering from distributor")
        finally: conn.close()

    def create_order(self, user_id, order_data):
        conn = self.db.get_connection()
        if not conn: return jsonify({'error': 'DB connection failed'}), 500
        try:
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT distributor_id FROM distributor_sellers WHERE seller_id = %s", (user_id,))
            dist_res = cursor.fetchone()
            if not dist_res: return jsonify({'error': 'You are not assigned to a distributor.'}), 400
            distributor_id = dist_res['distributor_id']
            total_amount = Decimal('0.0')
            for item in order_data['items']:
                try:
                    quantity, price = int(item['quantity']), Decimal(str(item['price']))
                    if quantity > 0: total_amount += quantity * price
                except (InvalidOperation, ValueError, TypeError): conn.rollback(); return jsonify({'error': f"Invalid data for product_id {item.get('product_id')}."}), 400
            for item in order_data['items']:
                quantity = int(item['quantity']);
                if quantity <= 0: continue
                cursor.execute("SELECT name FROM products WHERE id = %s", (item['product_id'],))
                product_name = cursor.fetchone()['name']
                cursor.execute("SELECT COALESCE(SUM(quantity), 0) as total_stock FROM inventory WHERE product_id = %s AND ((owner_id = %s AND owner_type='seller') OR (owner_id = %s AND owner_type='distributor'))", (item['product_id'], user_id, distributor_id))
                total_stock = cursor.fetchone()['total_stock']
                if total_stock < quantity: conn.rollback(); return jsonify({'error': f"Out of stock for '{product_name}'. Requested: {quantity}, Available: {int(total_stock)}."}), 400
            for item in order_data['items']:
                qty_to_deduct = int(item['quantity']);
                if qty_to_deduct <= 0: continue
                cursor.execute("SELECT quantity FROM inventory WHERE product_id = %s AND owner_id = %s FOR UPDATE", (item['product_id'], user_id))
                seller_inv = cursor.fetchone(); seller_stock = seller_inv['quantity'] if seller_inv else 0
                deduct_from_seller = min(qty_to_deduct, seller_stock)
                if deduct_from_seller > 0:
                    cursor.execute("UPDATE inventory SET quantity = quantity - %s WHERE product_id = %s AND owner_id = %s", (deduct_from_seller, item['product_id'], user_id))
                    qty_to_deduct -= deduct_from_seller
                if qty_to_deduct > 0:
                    cursor.execute("UPDATE inventory SET quantity = quantity - %s WHERE product_id = %s AND owner_id = %s", (qty_to_deduct, item['product_id'], distributor_id))
            order_number = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            cursor.execute("INSERT INTO orders (order_number, seller_id, distributor_id, customer_name, customer_email, total_amount) VALUES (%s, %s, %s, %s, %s, %s)", (order_number, user_id, distributor_id, order_data['customer_name'], order_data['customer_email'], total_amount))
            order_id = cursor.lastrowid
            item_values = [(order_id, i['product_id'], int(i['quantity']), Decimal(str(i['price']))) for i in order_data['items'] if int(i.get('quantity',0)) > 0]
            cursor.executemany("INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s)", item_values)
            conn.commit()
            return jsonify({'success': True, 'message': f'Order {order_number} created successfully!'})
        except (mysql.connector.Error, InvalidOperation, ValueError, TypeError) as e: conn.rollback(); return self.handle_error(e, "creating order")
        finally: conn.close()

class OrderService(BaseService):
    def update_status(self, order_id, status, user_id):
        conn = self.db.get_connection()
        if not conn: return jsonify({'error': 'DB connection failed'}), 500
        try:
            cursor = conn.cursor()
            if status == 'confirmed':
                cursor.execute("UPDATE orders SET status = %s, confirmed_by_id = %s WHERE id = %s AND status = 'pending'", (status, user_id, order_id))
            else:
                cursor.execute("UPDATE orders SET status = %s WHERE id = %s", (status, order_id))
            conn.commit()
            if cursor.rowcount == 0: return jsonify({'error': 'Order not found or status cannot be updated.'}), 404
            return jsonify({'success': True, 'message': f'Order status updated to {status}.'})
        except mysql.connector.Error as e: conn.rollback(); return self.handle_error(e, "updating order status")
        finally: conn.close()

# ================================
# FLASK APP & ROUTES
# ================================
app = Flask(__name__)
app.secret_key = os.urandom(24) 
CORS(app, supports_credentials=True)

auth_service, mfg_service, dist_service, seller_service, order_service = AuthenticationService(), ManufacturerService(), DistributorService(), SellerService(), OrderService()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session: return jsonify({'error': 'Authentication required. Please log in.'}), 401
        return f(*args, **kwargs)
    return decorated_function

def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get('user_type') not in allowed_roles: return jsonify({'error': 'Unauthorized for this role'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/api/login', methods=['POST'])
def login(): return auth_service.login(request.json['username'], request.json['password'])
@app.route('/api/logout', methods=['POST'])
@login_required
def logout(): return auth_service.logout()
@app.route('/api/session', methods=['GET'])
def get_current_session(): return auth_service.get_session()
@app.route('/api/dashboard', methods=['GET'])
@login_required
def get_dashboard():
    user_id, user_type = session['user_id'], session['user_type']
    if user_type == 'manufacturer': return mfg_service.get_dashboard_data(user_id)
    if user_type == 'distributor': return dist_service.get_dashboard_data(user_id)
    if user_type == 'seller': return seller_service.get_dashboard_data(user_id)
    return jsonify({'error': 'Invalid user type'}), 400
@app.route('/api/manufacturer/product', methods=['POST'])
@login_required
@role_required(['manufacturer'])
def create_mfg_product(): return mfg_service.create_product(session['user_id'], request.json)
@app.route('/api/manufacturer/inventory', methods=['PUT'])
@login_required
@role_required(['manufacturer'])
def update_mfg_inventory(): return mfg_service.update_inventory(request.json['product_id'], request.json['quantity'], session['user_id'])
@app.route('/api/distributor/order', methods=['POST'])
@login_required
@role_required(['distributor'])
def order_from_mfg(): return dist_service.order_from_manufacturer(request.json['product_id'], request.json['quantity'], session['user_id'])
@app.route('/api/seller/stock_order', methods=['POST'])
@login_required
@role_required(['seller'])
def order_from_dist(): return seller_service.order_from_distributor(session['user_id'], request.json['product_id'], request.json['quantity'])
@app.route('/api/seller/order', methods=['POST'])
@login_required
@role_required(['seller'])
def create_seller_order(): return seller_service.create_order(session['user_id'], request.json)
@app.route('/api/order/<int:order_id>/status', methods=['PUT'])
@login_required
@role_required(['manufacturer', 'distributor'])
def update_order_status(order_id): return order_service.update_status(order_id, request.json['status'], session['user_id'])

# ================================
# HTML TEMPLATE
# ================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cozy Comfort Management</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&family=Great+Vibes&display=swap');
        :root{--primary-color:#5A67D8;--secondary-color:#38B2AC;--bg-color:#F7FAFC;--card-bg:#FFFFFF;--text-primary:#2D3748;--text-secondary:#718096;--success:#48BB78;--warning:#ED8936;--danger:#E53E3E;--info:#4299E1;--border-color:#E2E8F0;--shadow-sm:0 1px 2px 0 rgba(0,0,0,0.05);--shadow-md:0 4px 6px -1px rgba(0,0,0,0.1),0 2px 4px -1px rgba(0,0,0,0.06);--shadow-lg:0 10px 15px -3px rgba(0,0,0,0.1),0 4px 6px -2px rgba(0,0,0,0.05);}
        body{font-family:'Poppins',sans-serif;background-color:var(--bg-color);margin:0;color:var(--text-primary);-webkit-font-smoothing:antialiased;}
        .container{max-width:1280px;margin:2rem auto;padding:0 1rem;}
        .main-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:2.5rem;}
        .main-header h1{font-family:'Great Vibes',cursive;font-size:3.5rem;font-weight:400;color:var(--primary-color);text-shadow:1px 1px 2px rgba(0,0,0,0.1);margin:0;animation:fadeInDown .8s ease-out;}
        .card{background:var(--card-bg);border-radius:12px;box-shadow:var(--shadow-md);margin-bottom:2rem;border:1px solid var(--border-color);transition:transform .3s ease,box-shadow .3s ease;animation:fadeInUp .5s ease-out forwards;opacity:0;}
        .card:hover{transform:translateY(-5px);box-shadow:var(--shadow-lg);}
        .card-header{padding:1.25rem 1.5rem;border-bottom:1px solid var(--border-color);display:flex;justify-content:space-between;align-items:center;}
        .card-header h3{margin:0;font-size:1.2rem;font-weight:600;}
        .card-content{padding:1.5rem;}
        .user-info{display:flex;gap:1rem;align-items:center;}
        .table{width:100%;border-collapse:collapse;}
        .table th,.table td{padding:1rem 1.5rem;text-align:left;border-bottom:1px solid var(--border-color);}
        .table th{background-color:var(--bg-color);font-weight:600;color:var(--text-secondary);text-transform:uppercase;font-size:.8rem;letter-spacing:.05em;}
        .table tr:last-child td{border-bottom:none;}
        .table td strong{color:var(--text-primary);font-weight:600;}
        .btn{padding:.75rem 1.25rem;border:none;border-radius:8px;cursor:pointer;font-weight:600;font-size:.9rem;transition:all .3s ease;box-shadow:var(--shadow-sm);display:inline-flex;align-items:center;gap:.5rem;}
        .btn:disabled{background-color:#A0AEC0;cursor:not-allowed;}
        .btn:hover:not(:disabled){transform:translateY(-2px);box-shadow:var(--shadow-md);}
        .btn-primary{background:linear-gradient(45deg,var(--primary-color),#7f9cf5);color:#fff;}
        .btn-primary:hover:not(:disabled){background:linear-gradient(45deg,#7f9cf5,var(--primary-color));}
        .btn-secondary{background-color:var(--bg-color);color:var(--text-primary);border:1px solid var(--border-color);}
        .btn-secondary:hover:not(:disabled){background-color:#E2E8F0;border-color:#CBD5E0;}
        .btn-danger{background-color:var(--danger);color:#fff;}
        .modal{display:none;position:fixed;z-index:100;left:0;top:0;width:100%;height:100%;overflow:auto;background-color:rgba(45,55,72,.7);backdrop-filter:blur(5px);animation:fadeIn .4s ease;}
        .modal-content{background-color:var(--card-bg);margin:8% auto;padding:2.5rem;border-radius:12px;width:90%;max-width:550px;box-shadow:var(--shadow-lg);animation:slideInUp .5s ease;}
        .modal-content h2{margin-top:0;color:var(--primary-color);}
        .form-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1.5rem;}
        .form-group.full-width{grid-column:1 / -1;}
        .form-group label{display:block;margin-bottom:.5rem;font-weight:500;color:var(--text-secondary);}
        .form-group input{width:100%;padding:.8rem 1rem;box-sizing:border-box;border-radius:8px;border:1px solid var(--border-color);font-size:1rem;background:var(--bg-color);transition:border-color .3s,box-shadow .3s;}
        .form-group input:focus{border-color:var(--primary-color);box-shadow:0 0 0 3px rgba(90,103,216,.3);outline:none;}
        .alert{padding:1rem 1.5rem;margin-bottom:1rem;border-radius:8px;font-weight:500;border-left:5px solid;animation:fadeInDown .5s;}
        .alert-danger{color:#9B2C2C;background-color:#FED7D7;border-color:var(--danger);}
        .alert-success{color:#276749;background-color:#C6F6D5;border-color:var(--success);}
        .status{padding:.25rem .75rem;border-radius:99px;font-size:.8rem;font-weight:600;text-transform:capitalize;}
        .status-pending{background-color:#FEF3C7;color:#9A5B22;border:1px solid #F6E05E;}
        .status-confirmed{background-color:#C6F6D5;color:#276749;border:1px solid #68D391;}
        .status-shipped{background-color:#BEE3F8;color:#2C5282;border:1px solid #63B3ED;}
        .status-cancelled{background-color:#FED7D7;color:#9B2C2C;border:1px solid #FC8181;}
        .loading-spinner{border:4px solid var(--border-color);border-top:4px solid var(--primary-color);border-radius:50%;width:50px;height:50px;animation:spin 1s linear infinite;margin:80px auto;}
        @keyframes fadeIn{from{opacity:0}to{opacity:1}}
        @keyframes fadeInDown{from{opacity:0;transform:translateY(-20px)}to{opacity:1;transform:translateY(0)}}
        @keyframes fadeInUp{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}
        @keyframes slideInUp{from{transform:translateY(50px);opacity:0}to{transform:translateY(0);opacity:1}}
        @keyframes spin{0%{transform:rotate(0deg)}100%{transform:rotate(360deg)}}
    </style>
</head>
<body>
    <div class="container">
        <header class="main-header"><h1>Cozy Comfort</h1><div class="user-info" id="user-display"></div></header>
        <main><div id="alert-container"></div><div id="content-area"></div></main>
    </div>
    <div id="formModal" class="modal"><div class="modal-content" id="modal-content-host"></div></div>
    <script>
        let productCatalog = [], currentUser = null;
        function showAlert(message, isError = false, containerId = 'alert-container') { const container = document.getElementById(containerId); const alertType = isError ? 'alert-danger' : 'alert-success'; container.innerHTML = `<div class="alert ${alertType}">${message}</div>`; if (containerId === 'alert-container') setTimeout(() => { container.innerHTML = ''; }, 5000); }
        async function api(endpoint, options = {}) { if (options.body) options.headers = { 'Content-Type': 'application/json', ...options.headers }; try { const response = await fetch(`/api${endpoint}`, options); const data = await response.json(); if (!response.ok) { if (response.status === 401) handleLoggedOutState(); throw new Error(data.error || 'API Request Failed'); } return data; } catch (err) { if (err instanceof SyntaxError) showAlert("An unexpected server error occurred. Please try again.", true); else showAlert(err.message, true); throw err; } }
        async function performLogin() { const form = document.getElementById('loginForm'), btn = form.querySelector('button[type="submit"]'); btn.disabled = true; btn.textContent = 'Logging in...'; try { const data = await api('/login', { method: 'POST', body: JSON.stringify({ username: form.username.value, password: form.password.value }) }); currentUser = data.user; showAlert(data.message, false); renderUserDisplay(); loadDashboard(); closeModal(); } catch (err) { showAlert(err.message, true, 'login-alert-container'); } finally { btn.disabled = false; btn.textContent = 'Login'; } }
        async function performLogout() { try { await api('/logout', { method: 'POST' }); handleLoggedOutState(); showAlert("You have been logged out.", false); } catch (err) {} }
        function renderUserDisplay() { document.getElementById('user-display').innerHTML = currentUser ? `<span>Logged in as <strong>${currentUser.company_name}</strong></span><button class="btn btn-danger" onclick="performLogout()">Logout</button>` : ''; }
        function handleLoggedOutState() { currentUser = null; renderUserDisplay(); document.getElementById('content-area').innerHTML = `<div class="card"><div class="card-header"><h3>Welcome to the Supply Chain Portal</h3></div><div class="card-content" style="text-align:center;"><p style="font-size:1.1rem; color:var(--text-secondary); margin: 1rem 0 2.5rem;">Please select your role to log in and manage your operations.</p><div style="display:flex; justify-content:center; flex-wrap: wrap; gap: 1.5rem;"><button class="btn btn-primary" onclick="openLoginModal('cozy_mfg', 'Manufacturer')">🏭 Login as Manufacturer</button><button class="btn btn-primary" onclick="openLoginModal('metro_dist', 'Distributor')">📦 Login as Distributor</button><button class="btn btn-primary" onclick="openLoginModal('comfort_store', 'Seller')">🏪 Login as Seller</button></div></div></div>`; }
        function renderTable(headers, rows) { const head = `<thead><tr>${headers.map(h => `<th>${h}</th>`).join('')}</tr></thead>`; const body = `<tbody>${rows.map(row => `<tr>${row.map(cell => `<td>${cell}</td>`).join('')}</tr>`).join('')}</tbody>`; return `<div class="card-content" style="overflow-x:auto;"><table class="table">${head}${body}</table></div>`; }
        async function loadDashboard() { document.getElementById('content-area').innerHTML = '<div class="loading-spinner"></div>'; if (!currentUser) { handleLoggedOutState(); return; } try { const data = await api('/dashboard'); let html = ''; if (currentUser.type === 'manufacturer') { html += `<div class="card"><div class="card-header"><h3>Inventory</h3><button class="btn btn-primary" onclick="openNewProductModal()">+ New Product</button></div>${renderTable(['Product', 'Model', 'Stock', 'Actions'], data.inventory.map(p => [p.name, p.model, `<strong>${p.quantity}</strong> units`, `<button class="btn btn-secondary" onclick='openMfgUpdateModal(${JSON.stringify(p)})'>Edit Stock</button>`]))}</div>`; html += `<div class="card"><div class="card-header"><h3>All Customer Orders</h3></div>${renderTable(['Order #', 'Seller', 'Distributor', 'Status', 'Date', 'Actions'], data.orders.map(o => [o.order_number, o.seller, o.distributor || 'N/A', `<span class="status status-${o.status}">${o.status}</span>`, new Date(o.created_at).toLocaleDateString(), o.status === 'pending' ? `<button class="btn btn-primary" onclick="updateOrderStatus(${o.id}, 'confirmed')">Confirm</button>` : 'N/A']))}</div>`; } if (currentUser.type === 'distributor') { html += `<div class="card"><div class="card-header"><h3>Inventory & Ordering</h3></div>${renderTable(['Product', 'Model', 'Price', 'Your Stock', 'Mfg. Stock', 'Actions'], data.inventory.map(p => [p.name, p.model, `$${p.price}`, `<strong>${p.your_stock}</strong>`, p.manufacturer_stock, `<button class="btn btn-primary" onclick='openDistOrderModal(${JSON.stringify(p)})'>Order More</button>`]))}</div>`; html += `<div class="card"><div class="card-header"><h3>Customer Orders to Fulfill</h3></div>${renderTable(['Order #', 'Customer', 'From Seller', 'Status', 'Date', 'Actions'], data.orders.map(o => [o.order_number, o.customer_name, o.seller, `<span class="status status-${o.status}">${o.status}</span>`, new Date(o.created_at).toLocaleDateString(), o.status === 'pending' ? `<button class="btn btn-primary" onclick="updateOrderStatus(${o.id}, 'confirmed')">Confirm</button>` : 'N/A']))}</div>`; } if (currentUser.type === 'seller') { productCatalog = data.products; html += `<div class="card"><div class="card-header"><h3>Product Catalog & Inventory</h3><button class="btn btn-primary" onclick="openSellerOrderModal()">+ New Customer Order</button></div>${renderTable(['Product', 'Model', 'Price', 'Your Stock', 'Distributor Stock', 'Actions'], data.products.map(p => [p.name, p.model, `$${p.price}`, `<strong>${p.seller_stock}</strong>`, p.distributor_stock, `<button class="btn btn-primary" onclick='openSellerStockOrderModal(${JSON.stringify(p)})'>Order Stock</button>`]))}</div>`; html += `<div class="card"><div class="card-header"><h3>Your Customer Orders</h3></div>${renderTable(['Order #', 'Customer', 'Amount', 'Status', 'Date', 'Confirmed By'], data.orders.map(o => [o.order_number, o.customer_name, `$${Number(o.total_amount).toFixed(2)}`, `<span class="status status-${o.status}">${o.status}</span>`, new Date(o.created_at).toLocaleDateString(), o.confirmer_name || '<i>Pending</i>']))}</div>`; } document.getElementById('content-area').innerHTML = html; } catch (err) { document.getElementById('content-area').innerHTML = `<div class="alert alert-danger">Could not load dashboard.</div>`; } }
        function openModal(html) { document.getElementById('modal-content-host').innerHTML = html; document.getElementById('formModal').style.display = 'block'; }
        function closeModal() { document.getElementById('formModal').style.display = 'none'; }
        function openLoginModal(username, roleName) { openModal(`<h2>${roleName} Login</h2><p style="color:var(--text-secondary)">All sample users have the password: <strong>pass</strong></p><div id="login-alert-container"></div><form id="loginForm" onsubmit="event.preventDefault(); performLogin();"><div class="form-group"><label>Username</label><input name="username" value="${username}" required></div><div class="form-group"><label>Password</label><input name="password" type="password" required></div><button type="submit" class="btn btn-primary" style="width:100%;padding:1rem;">Login</button></form>`); document.getElementById('loginForm').password.focus(); }
        function openNewProductModal() { openModal(`<h2>Create New Product</h2><form id="newProductForm" onsubmit="event.preventDefault(); submitNewProduct();"><div id="product-alert-container"></div><div class="form-grid"><div class="form-group full-width"><label>Product Name</label><input name="name" required></div><div class="form-group"><label>Model</label><input name="model" required></div><div class="form-group"><label>Material</label><input name="material"></div><div class="form-group"><label>Size</label><input name="size"></div><div class="form-group"><label>Color</label><input name="color"></div><div class="form-group"><label>Price (USD)</label><input name="price" type="number" step="0.01" required></div><div class="form-group"><label>Initial Stock Quantity</label><input name="initial_stock" type="number" step="1" required></div></div><button type="submit" class="btn btn-primary" style="width:100%;padding:1rem;margin-top:1rem;">Create Product</button></form>`); }
        function openMfgUpdateModal(p) { openModal(`<h2>Update Inventory</h2><p>${p.name}</p><div class="form-group"><label>New Quantity</label><input id="mfgQty" type="number" value="${p.quantity}"></div><button class="btn btn-primary" onclick="submitMfgUpdate(${p.product_id})">Update</button>`); }
        function openDistOrderModal(p) { openModal(`<h2>Order from Manufacturer</h2><p>${p.name}</p><div class="form-group"><label>Quantity</label><input id="distQty" type="number" min="1"></div><button class="btn btn-primary" onclick="submitDistOrder(${p.id})">Order</button>`); }
        function openSellerStockOrderModal(p) { openModal(`<h2>Order from Distributor</h2><p>${p.name}</p><p>Distributor has: <strong>${p.distributor_stock}</strong> units</p><div class="form-group"><label>Quantity</label><input id="sellerQty" type="number" min="1" max="${p.distributor_stock}"></div><button class="btn btn-primary" onclick="submitSellerStockOrder(${p.id})">Order</button>`); }
        function openSellerOrderModal() { const list = productCatalog.map(p => `<div style="display:flex;align-items:center;justify-content:space-between;padding:0.5rem;border-bottom:1px solid var(--border-color)"><span><strong>${p.name}</strong><br><small style="color:var(--text-secondary)">Available: ${p.seller_stock + p.distributor_stock}</small></span><input type="number" class="order-item" min="0" data-id="${p.id}" data-price="${p.price}" placeholder="0" style="width:70px"></div>`).join(''); openModal(`<h2>New Customer Order</h2><div class="form-group"><label>Customer Name</label><input id="custName"></div><div class="form-group"><label>Customer Email</label><input id="custEmail"></div><h3 style="margin-top:1.5rem;color:var(--text-secondary)">Items</h3><div style="max-height:200px;overflow-y:auto;border:1px solid var(--border-color);border-radius:8px;padding:0.5rem">${list}</div><button class="btn btn-primary" style="width:100%;padding:1rem;margin-top:1.5rem" onclick="submitSellerOrder()">Create Order</button>`); }
        async function submitNewProduct() { const form = document.getElementById('newProductForm'); const payload = { name: form.name.value, model: form.model.value, material: form.material.value, size: form.size.value, color: form.color.value, price: form.price.value, initial_stock: form.initial_stock.value }; if (!payload.name || !payload.model || !payload.price || !payload.initial_stock) return showAlert('Please fill out all required fields.', true, 'product-alert-container'); await api('/manufacturer/product', { method: 'POST', body: JSON.stringify(payload) }).then(d => { showAlert(d.message, false); closeModal(); loadDashboard(); }).catch(err => showAlert(err.message, true, 'product-alert-container')); }
        async function submitMfgUpdate(product_id) { const quantity = parseInt(document.getElementById('mfgQty').value); await api('/manufacturer/inventory', { method: 'PUT', body: JSON.stringify({ product_id, quantity }) }).then(d => { showAlert(d.message, false); closeModal(); loadDashboard(); }).catch(() => {}); }
        async function submitDistOrder(product_id) { const quantity = parseInt(document.getElementById('distQty').value); if (!quantity || quantity <= 0) return showAlert('Quantity must be greater than 0.', true); await api('/distributor/order', { method: 'POST', body: JSON.stringify({ product_id, quantity }) }).then(d => { showAlert(d.message, false); closeModal(); loadDashboard(); }).catch(() => {}); }
        async function submitSellerStockOrder(product_id) { const quantity = parseInt(document.getElementById('sellerQty').value); if (!quantity || quantity <= 0) return showAlert('Quantity must be greater than 0.', true); await api('/seller/stock_order', { method: 'POST', body: JSON.stringify({ product_id, quantity }) }).then(d => { showAlert(d.message, false); closeModal(); loadDashboard(); }).catch(() => {}); }
        async function submitSellerOrder() { const items = Array.from(document.querySelectorAll('.order-item')).map(i => ({ product_id: i.dataset.id, quantity: parseInt(i.value) || 0, price: i.dataset.price })).filter(i => i.quantity > 0); if (items.length === 0) return showAlert('Please add at least one item.', true); const customer_name = document.getElementById('custName').value.trim(); if (!customer_name) return showAlert('Customer name is required.', true); const payload = { customer_name, customer_email: document.getElementById('custEmail').value.trim(), items }; await api('/seller/order', { method: 'POST', body: JSON.stringify(payload) }).then(d => { showAlert(d.message, false); closeModal(); loadDashboard(); }).catch(() => {}); }
        async function updateOrderStatus(order_id, status) { await api(`/order/${order_id}/status`, { method: 'PUT', body: JSON.stringify({ status }) }).then(d => { showAlert(d.message, false); loadDashboard(); }).catch(() => {}); }
        window.onclick = (event) => { if (event.target == document.getElementById('formModal')) closeModal(); };
        document.addEventListener("DOMContentLoaded", async () => { try { const d = await api('/session'); if (d.is_logged_in) { currentUser = d.user; renderUserDisplay(); loadDashboard(); } else { handleLoggedOutState(); } } catch (e) { handleLoggedOutState(); } });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    print("🚀 Cozy Comfort Web Server Starting...")
    port = int(os.environ.get('PORT', 5021))
    print(f"🌐 Server will be available at: http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
