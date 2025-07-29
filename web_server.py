# web_server.py
# Cozy Comfort Web Server - Fully Revised and Feature-Complete Version

import mysql.connector
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import os
import traceback
from datetime import datetime

# ================================
# DATABASE SETUP AND CONNECTION
# ================================
class DatabaseManager:
    def __init__(self):
        self.config = {
            'host': os.environ.get('DB_HOST', 'localhost'),
            'user': os.environ.get('DB_USER', 'root'),
            'password': os.environ.get('DB_PASSWORD', ''),
            'database': os.environ.get('DB_NAME', 'cozy_comfort_db'),
            'port': int(os.environ.get('DB_PORT', 3306)),
            'charset': 'utf8mb4',
        }
        self.init_database()

    def get_connection(self):
        try:
            conn = mysql.connector.connect(**self.config)
            return conn
        except mysql.connector.Error as err:
            print(f"Database connection error: {err}")
            return None

    def init_database(self):
        try:
            print("Connecting to database server to ensure database exists...")
            temp_config = self.config.copy()
            db_name = temp_config.pop('database')
            conn = mysql.connector.connect(**temp_config)
            cursor = conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            print(f"Database '{db_name}' checked/created successfully.")
            cursor.close()
            conn.close()

            print("Initializing tables and data...")
            self.create_tables()
            self.insert_sample_data()
            print("Database setup complete.")
        except mysql.connector.Error as err:
            print(f"FATAL: Database initialization failed: {err}")
            exit(1)

    def create_tables(self):
        conn = self.get_connection()
        if not conn:
            print("FATAL: Could not connect to the database to create tables.")
            exit(1)
        
        cursor = conn.cursor()
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY, username VARCHAR(100) UNIQUE NOT NULL, email VARCHAR(150) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL, user_type ENUM('manufacturer', 'distributor', 'seller') NOT NULL,
                    company_name VARCHAR(200), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB;
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(200) NOT NULL, model VARCHAR(100) NOT NULL, material VARCHAR(100),
                    size VARCHAR(50), color VARCHAR(50), price DECIMAL(10,2) NOT NULL, manufacturer_id INT,
                    FOREIGN KEY (manufacturer_id) REFERENCES users(id) ON DELETE SET NULL
                ) ENGINE=InnoDB;
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    id INT AUTO_INCREMENT PRIMARY KEY, product_id INT NOT NULL, owner_id INT NOT NULL,
                    owner_type ENUM('manufacturer', 'distributor', 'seller') NOT NULL, quantity INT NOT NULL DEFAULT 0,
                    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
                    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE KEY unique_inventory (product_id, owner_id, owner_type)
                ) ENGINE=InnoDB;
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INT AUTO_INCREMENT PRIMARY KEY, order_number VARCHAR(100) UNIQUE NOT NULL, seller_id INT NOT NULL,
                    distributor_id INT, customer_name VARCHAR(200) NOT NULL, customer_email VARCHAR(150), total_amount DECIMAL(10,2) NOT NULL,
                    status ENUM('pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled') DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    confirmed_by_id INT,
                    FOREIGN KEY (seller_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (distributor_id) REFERENCES users(id) ON DELETE SET NULL,
                    FOREIGN KEY (confirmed_by_id) REFERENCES users(id) ON DELETE SET NULL
                ) ENGINE=InnoDB;
            """)
            
            # Schema migration for existing databases. Add confirmed_by_id if it doesn't exist.
            db_name = self.config['database']
            cursor.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'orders' AND COLUMN_NAME = 'confirmed_by_id'
            """, (db_name,))
            if cursor.fetchone()[0] == 0:
                print("Applying schema migration: Adding 'confirmed_by_id' to 'orders' table...")
                cursor.execute("""
                    ALTER TABLE orders
                    ADD COLUMN confirmed_by_id INT,
                    ADD CONSTRAINT fk_confirmed_by FOREIGN KEY (confirmed_by_id) REFERENCES users(id) ON DELETE SET NULL
                """)
                print("Schema migration successful.")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS order_items (
                    id INT AUTO_INCREMENT PRIMARY KEY, order_id INT NOT NULL, product_id INT NOT NULL, quantity INT NOT NULL,
                    unit_price DECIMAL(10,2) NOT NULL, FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
                    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
                ) ENGINE=InnoDB;
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS distributor_sellers (
                    distributor_id INT NOT NULL, seller_id INT NOT NULL,
                    FOREIGN KEY (distributor_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (seller_id) REFERENCES users(id) ON DELETE CASCADE,
                    PRIMARY KEY (distributor_id, seller_id)
                ) ENGINE=InnoDB;
            """)
            conn.commit()
        except mysql.connector.Error as err:
            print(f"Error during table creation: {err}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()

    def insert_sample_data(self):
        conn = self.get_connection()
        if not conn: return
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM users")
            if cursor.fetchone()[0] > 0: return

            print("No existing users found. Inserting sample data...")
            # Users
            users = [ (1, 'cozy_mfg', 'mfg@cozy.com', 'pass', 'manufacturer', 'Cozy Comfort MFG'), (2, 'metro_dist', 'dist@metro.com', 'pass', 'distributor', 'Metro Distribution'), (4, 'comfort_store', 'seller@comfort.com', 'pass', 'seller', 'The Comfort Store') ]
            cursor.executemany("INSERT INTO users (id, username, email, password, user_type, company_name, created_at) VALUES (%s, %s, %s, %s, %s, %s, NOW())", users)
            # Products
            products = [ (1, 'Ultra Soft Fleece Blanket', 'USF-001', 'Fleece', 'Queen', 'Blue', 45.99, 1), (2, 'Premium Wool Blanket', 'PWB-002', 'Wool', 'King', 'Gray', 89.99, 1), (3, 'Cotton Comfort Throw', 'CCT-003', 'Cotton', 'Throw', 'Beige', 29.99, 1) ]
            cursor.executemany("INSERT INTO products (id, name, model, material, size, color, price, manufacturer_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", products)
            # Inventory
            inventory = [ (1, 1, 1, 'manufacturer', 500), (2, 2, 1, 'manufacturer', 300), (3, 3, 1, 'manufacturer', 750), (4, 1, 2, 'distributor', 50), (5, 2, 2, 'distributor', 30), (6, 1, 4, 'seller', 10), (7, 2, 4, 'seller', 5) ]
            cursor.executemany("INSERT INTO inventory (id, product_id, owner_id, owner_type, quantity) VALUES (%s, %s, %s, %s, %s)", inventory)
            # Relationship
            cursor.execute("INSERT INTO distributor_sellers (distributor_id, seller_id) VALUES (2, 4)")
            conn.commit()
            print("Sample data inserted successfully.")
        except mysql.connector.Error as err:
            print(f"Error inserting sample data: {err}")
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

class ManufacturerService(BaseService):
    def get_dashboard_data(self, user_id):
        conn = self.db.get_connection()
        if not conn: return jsonify({'error': 'DB connection failed'}), 500
        try:
            cursor = conn.cursor(dictionary=True)
            # Get inventory
            cursor.execute("SELECT i.product_id, p.name, p.model, i.quantity FROM inventory i JOIN products p ON i.product_id = p.id WHERE i.owner_id = %s", (user_id,))
            inventory = cursor.fetchall()
            # Get all orders (as a central view)
            cursor.execute("""
                SELECT o.id, o.order_number, u_seller.company_name as seller, u_dist.company_name as distributor, o.status, o.created_at
                FROM orders o
                JOIN users u_seller ON o.seller_id = u_seller.id
                LEFT JOIN users u_dist ON o.distributor_id = u_dist.id
                ORDER BY o.created_at DESC
            """)
            orders = cursor.fetchall()
            return jsonify({'inventory': inventory, 'orders': orders})
        except mysql.connector.Error as e: return self.handle_error(e, "fetching manufacturer data")
        finally: conn.close()

    def update_inventory(self, product_id, quantity, user_id):
        conn = self.db.get_connection()
        if not conn: return jsonify({'error': 'DB connection failed'}), 500
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE inventory SET quantity = %s WHERE product_id = %s AND owner_id = %s", (quantity, product_id, user_id))
            conn.commit()
            if cursor.rowcount == 0: return jsonify({'error': 'Product not found in your inventory or quantity is the same'}), 404
            return jsonify({'success': True, 'message': 'Inventory updated successfully.'})
        except mysql.connector.Error as e: conn.rollback(); return self.handle_error(e, "updating inventory")
        finally: conn.close()

class DistributorService(BaseService):
    def get_dashboard_data(self, user_id):
        conn = self.db.get_connection()
        if not conn: return jsonify({'error': 'DB connection failed'}), 500
        try:
            cursor = conn.cursor(dictionary=True)
            # Get inventory and compare with manufacturer stock
            cursor.execute("""
                SELECT p.id, p.name, p.model, p.price,
                       COALESCE(i.quantity, 0) as your_stock,
                       (SELECT quantity FROM inventory mi WHERE mi.product_id = p.id AND mi.owner_type = 'manufacturer') as manufacturer_stock
                FROM products p
                LEFT JOIN inventory i ON p.id = i.product_id AND i.owner_id = %s
            """, (user_id,))
            inventory = cursor.fetchall()
            
            # Get orders assigned to this distributor
            cursor.execute("""
                SELECT o.id, o.order_number, u_seller.company_name AS seller, o.status, o.created_at, o.customer_name
                FROM orders o
                JOIN users u_seller ON o.seller_id = u_seller.id
                WHERE o.distributor_id = %s
                ORDER BY o.created_at DESC
            """, (user_id,))
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
            # Check and lock manufacturer stock
            cursor.execute("SELECT quantity, owner_id FROM inventory WHERE product_id = %s AND owner_type = 'manufacturer' FOR UPDATE", (product_id,))
            mfg_inv = cursor.fetchone()
            if not mfg_inv or mfg_inv['quantity'] < quantity:
                conn.rollback()
                return jsonify({'error': 'Insufficient manufacturer stock.'}), 400
            
            # Update inventories
            cursor.execute("UPDATE inventory SET quantity = quantity - %s WHERE product_id = %s AND owner_id = %s", (quantity, product_id, mfg_inv['owner_id']))
            cursor.execute("""
                INSERT INTO inventory (product_id, owner_id, owner_type, quantity) VALUES (%s, %s, 'distributor', %s)
                ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
            """, (product_id, user_id, quantity))

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
            # Get product catalog
            cursor.execute("""
                SELECT p.id, p.name, p.model, p.price,
                       COALESCE(si.quantity, 0) as seller_stock,
                       COALESCE(di.quantity, 0) as distributor_stock
                FROM products p
                LEFT JOIN inventory si ON p.id = si.product_id AND si.owner_id = %s
                LEFT JOIN distributor_sellers ds ON ds.seller_id = %s
                LEFT JOIN inventory di ON p.id = di.product_id AND di.owner_id = ds.distributor_id
            """, (user_id, user_id))
            products = cursor.fetchall()
            
            # Get seller's orders and who confirmed them
            cursor.execute("""
                SELECT o.*, u_confirmer.company_name AS confirmer_name
                FROM orders o
                LEFT JOIN users u_confirmer ON o.confirmed_by_id = u_confirmer.id
                WHERE o.seller_id = %s
                ORDER BY o.created_at DESC
            """, (user_id,))
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

            # Get seller's assigned distributor
            cursor.execute("SELECT distributor_id FROM distributor_sellers WHERE seller_id = %s", (user_id,))
            dist_res = cursor.fetchone()
            if not dist_res: return jsonify({'error': 'You are not assigned to a distributor.'}), 400
            distributor_id = dist_res['distributor_id']

            # Check and lock distributor stock
            cursor.execute("SELECT quantity FROM inventory WHERE product_id = %s AND owner_id = %s AND owner_type = 'distributor' FOR UPDATE", (product_id, distributor_id))
            dist_inv = cursor.fetchone()
            if not dist_inv or dist_inv['quantity'] < quantity:
                conn.rollback()
                return jsonify({'error': 'Insufficient distributor stock.'}), 400

            # Decrease distributor stock
            cursor.execute("UPDATE inventory SET quantity = quantity - %s WHERE product_id = %s AND owner_id = %s", (quantity, product_id, distributor_id))
            
            # Increase seller stock
            cursor.execute("""
                INSERT INTO inventory (product_id, owner_id, owner_type, quantity) VALUES (%s, %s, 'seller', %s)
                ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
            """, (product_id, user_id, quantity))

            conn.commit()
            return jsonify({'success': True, 'message': f'Successfully ordered {quantity} units from distributor.'})
        except mysql.connector.Error as e:
            conn.rollback()
            return self.handle_error(e, "ordering from distributor")
        finally:
            conn.close()

    def create_order(self, user_id, order_data):
        conn = self.db.get_connection()
        if not conn: return jsonify({'error': 'DB connection failed'}), 500
        try:
            conn.start_transaction()
            cursor = conn.cursor(dictionary=True)
            
            # Get distributor
            cursor.execute("SELECT distributor_id FROM distributor_sellers WHERE seller_id = %s", (user_id,))
            dist_res = cursor.fetchone()
            if not dist_res: return jsonify({'error': 'You are not assigned to a distributor.'}), 400
            distributor_id = dist_res['distributor_id']

            total_amount = 0
            # Check all items for stock before making changes
            for item in order_data['items']:
                total_amount += item['quantity'] * item['price']
                cursor.execute("SELECT name FROM products WHERE id = %s", (item['product_id'],))
                product_name = cursor.fetchone()['name']
                
                cursor.execute("SELECT COALESCE(SUM(quantity), 0) as total_stock FROM inventory WHERE product_id = %s AND ((owner_id = %s AND owner_type='seller') OR (owner_id = %s AND owner_type='distributor'))", (item['product_id'], user_id, distributor_id))
                total_stock = cursor.fetchone()['total_stock']
                if total_stock < item['quantity']:
                    conn.rollback()
                    return jsonify({'error': f"Out of stock for '{product_name}'. Requested: {item['quantity']}, Total available: {int(total_stock)}."}), 400
            
            # Deduct inventory
            for item in order_data['items']:
                qty_to_deduct = item['quantity']
                # From seller first
                cursor.execute("SELECT quantity FROM inventory WHERE product_id = %s AND owner_id = %s FOR UPDATE", (item['product_id'], user_id))
                seller_inv = cursor.fetchone()
                seller_stock = seller_inv['quantity'] if seller_inv else 0
                
                deduct_from_seller = min(qty_to_deduct, seller_stock)
                if deduct_from_seller > 0:
                    cursor.execute("UPDATE inventory SET quantity = quantity - %s WHERE product_id = %s AND owner_id = %s", (deduct_from_seller, item['product_id'], user_id))
                    qty_to_deduct -= deduct_from_seller

                # From distributor if needed
                if qty_to_deduct > 0:
                    cursor.execute("UPDATE inventory SET quantity = quantity - %s WHERE product_id = %s AND owner_id = %s", (qty_to_deduct, item['product_id'], distributor_id))

            # Create order record
            order_number = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            cursor.execute("INSERT INTO orders (order_number, seller_id, distributor_id, customer_name, customer_email, total_amount) VALUES (%s, %s, %s, %s, %s, %s)",
                (order_number, user_id, distributor_id, order_data['customer_name'], order_data['customer_email'], total_amount))
            order_id = cursor.lastrowid
            
            item_values = [(order_id, i['product_id'], i['quantity'], i['price']) for i in order_data['items']]
            cursor.executemany("INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s)", item_values)
            
            conn.commit()
            return jsonify({'success': True, 'message': f'Order {order_number} created successfully!'})
        except mysql.connector.Error as e:
            conn.rollback()
            return self.handle_error(e, "creating order")
        finally:
            conn.close()

class OrderService(BaseService):
    def update_status(self, order_id, status, user_id):
        conn = self.db.get_connection()
        if not conn: return jsonify({'error': 'DB connection failed'}), 500
        try:
            cursor = conn.cursor()
            if status == 'confirmed':
                # Set status and the user who confirmed it. Only confirm if currently pending.
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
CORS(app)

mfg_service = ManufacturerService()
dist_service = DistributorService()
seller_service = SellerService()
order_service = OrderService()

def get_current_user():
    return {'id': int(request.headers.get('X-User-ID')), 'type': request.headers.get('X-User-Type')}

# --- API Endpoints ---
@app.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    user = get_current_user()
    if user['type'] == 'manufacturer': return mfg_service.get_dashboard_data(user['id'])
    if user['type'] == 'distributor': return dist_service.get_dashboard_data(user['id'])
    if user['type'] == 'seller': return seller_service.get_dashboard_data(user['id'])

@app.route('/api/manufacturer/inventory', methods=['PUT'])
def update_mfg_inventory():
    user = get_current_user()
    if user['type'] != 'manufacturer': return jsonify({'error': 'Unauthorized'}), 403
    data = request.json
    return mfg_service.update_inventory(data['product_id'], data['quantity'], user['id'])

@app.route('/api/distributor/order', methods=['POST'])
def order_from_mfg():
    user = get_current_user()
    if user['type'] != 'distributor': return jsonify({'error': 'Unauthorized'}), 403
    data = request.json
    return dist_service.order_from_manufacturer(data['product_id'], data['quantity'], user['id'])

@app.route('/api/seller/stock_order', methods=['POST'])
def order_from_dist():
    user = get_current_user()
    if user['type'] != 'seller': return jsonify({'error': 'Unauthorized'}), 403
    data = request.json
    return seller_service.order_from_distributor(user['id'], data['product_id'], data['quantity'])

@app.route('/api/seller/order', methods=['POST'])
def create_seller_order():
    user = get_current_user()
    if user['type'] != 'seller': return jsonify({'error': 'Unauthorized'}), 403
    return seller_service.create_order(user['id'], request.json)

@app.route('/api/order/<int:order_id>/status', methods=['PUT'])
def update_order_status(order_id):
    user = get_current_user()
    # Allow manufacturer or distributor to update status
    if user['type'] not in ['manufacturer', 'distributor']: return jsonify({'error': 'Unauthorized'}), 403
    data = request.json
    return order_service.update_status(order_id, data['status'], user['id'])

# --- Web Interface ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cozy Comfort Management</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        :root {
            --primary-color: #4f46e5; --primary-hover: #4338ca; --secondary-color: #f3f4f6;
            --text-dark: #111827; --text-light: #6b7280; --border-color: #e5e7eb;
            --success-bg: #dcfce7; --success-text: #166534; --error-bg: #fee2e2; --error-text: #991b1b;
            --shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -2px rgba(0,0,0,0.1);
            --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -4px rgba(0,0,0,0.1);
        }
        body { font-family: 'Inter', sans-serif; background-color: var(--secondary-color); margin: 0; color: var(--text-dark); }
        .container { max-width: 1200px; margin: 30px auto; padding: 0 20px; }
        .main-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; }
        .main-header h1 { font-size: 2.5rem; font-weight: 700; color: var(--primary-color); }
        .card { background: #fff; border-radius: 12px; box-shadow: var(--shadow); margin-bottom: 2rem; transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out; }
        .card:hover { transform: translateY(-5px); box-shadow: var(--shadow-lg); }
        .card-header { padding: 1.5rem; border-bottom: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center;}
        .card-header h3 { margin: 0; font-size: 1.25rem; font-weight: 600; }
        .card-content { padding: 1.5rem; }
        .user-selector { display: flex; gap: 10px; background: #fff; padding: 1rem; border-radius: 12px; box-shadow: var(--shadow); }
        .user-selector button { flex-grow: 1; padding: 12px 20px; border: none; background: transparent; cursor: pointer; border-radius: 8px; font-size: 1rem; font-weight: 500; color: var(--text-light); transition: all 0.2s; position: relative; }
        .user-selector button.active { background-color: var(--primary-color); color: white; font-weight: 600; box-shadow: var(--shadow); }
        .table { width: 100%; border-collapse: collapse; }
        .table th, .table td { padding: 1rem; text-align: left; border-bottom: 1px solid var(--border-color); vertical-align: middle; }
        .table th { background-color: #f9fafb; font-weight: 600; color: var(--text-light); }
        .table tr:last-child td { border-bottom: none; }
        .btn { padding: 10px 18px; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 0.9rem; transition: background-color 0.2s, transform 0.1s; }
        .btn:hover { transform: scale(1.05); }
        .btn-primary { background-color: var(--primary-color); color: white; } .btn-primary:hover { background-color: var(--primary-hover); }
        .btn-secondary { background-color: var(--secondary-color); color: var(--text-dark); border: 1px solid var(--border-color); } .btn-secondary:hover { background-color: #e5e7eb; }
        .modal { display: none; position: fixed; z-index: 100; left: 0; top: 0; width: 100%; height: 100%; overflow: auto; background-color: rgba(0,0,0,0.5); backdrop-filter: blur(4px); animation: fadeIn 0.3s; }
        .modal-content { background-color: #fff; margin: 10% auto; padding: 2.5rem; border-radius: 12px; width: 90%; max-width: 500px; box-shadow: var(--shadow-lg); animation: slideIn 0.4s; }
        .modal-content h2 { margin-top: 0; margin-bottom: 1rem; font-size: 1.5rem; } .modal-content p { margin-bottom: 1.5rem; color: var(--text-light); }
        .form-group { margin-bottom: 1.5rem; } .form-group label { display: block; margin-bottom: 0.5rem; font-weight: 500; }
        .form-group input { width: 100%; padding: 12px; box-sizing: border-box; border-radius: 8px; border: 1px solid var(--border-color); font-size: 1rem; }
        .alert { padding: 1rem 1.5rem; margin-bottom: 1.5rem; border-radius: 8px; font-weight: 500; display: flex; align-items: center; justify-content: center; animation: slideInDown 0.5s; }
        .alert-success { color: var(--success-text); background-color: var(--success-bg); } .alert-danger { color: var(--error-text); background-color: var(--error-bg); }
        .order-item-list div { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; padding: 1rem; background: #f9fafb; border-radius: 8px; }
        .order-item-list input { width: 80px; text-align: center; }
        .status { padding: 5px 12px; border-radius: 99px; font-size: 0.8rem; font-weight: 600; text-transform: capitalize; color: #fff; }
        .status-pending { background-color: #f59e0b; } .status-confirmed { background-color: #10b981; } .status-shipped { background-color: #3b82f6; }
        .status-delivered { background-color: #84cc16; } .status-processing { background-color: #6366f1; } .status-cancelled { background-color: #ef4444;}
        .loading-spinner { border: 4px solid #f3f3f3; border-top: 4px solid var(--primary-color); border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 50px auto; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes slideIn { from { transform: translateY(-30px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
        @keyframes slideInDown { from { transform: translateY(-20px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="container">
        <div class="main-header">
            <h1>Cozy Comfort</h1>
            <div class="user-selector">
                <button class="user-btn active" onclick="switchUser(1, 'manufacturer', this)">🏭 Manufacturer</button>
                <button class="user-btn" onclick="switchUser(2, 'distributor', this)">📦 Distributor</button>
                <button class="user-btn" onclick="switchUser(4, 'seller', this)">🏪 Seller</button>
            </div>
        </div>
        <div id="alert-container"></div>
        
        <!-- 
          STATIC DASHBOARD STRUCTURE:
          The content below is a static placeholder to show the dashboard's structure directly in the HTML.
          The `loadDashboard()` JavaScript function will automatically replace this with live data from the server when the page loads.
          This section has been "uncommented" as requested.
        -->
        <div id="dashboard">
            <div class="card">
                <div class="card-header">
                    <h3>Product Catalog & Inventory</h3>
                    <button class="btn btn-primary" onclick="openSellerOrderModal()">+ New Customer Order</button>
                </div>
                <div class="card-content" style="overflow-x:auto;">
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Product</th>
                                <th>Model</th>
                                <th>Price</th>
                                <th>Your Stock</th>
                                <th>Distributor Stock</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>Ultra Soft Fleece Blanket</td>
                                <td>USF-001</td>
                                <td>$45.99</td>
                                <td><strong>10</strong></td>
                                <td>50</td>
                                <td><button class="btn btn-primary" onclick="openSellerStockOrderModal(1, 'Ultra Soft Fleece Blanket', 50)">Order Stock</button></td>
                            </tr>
                            <tr>
                                <td>Premium Wool Blanket</td>
                                <td>PWB-002</td>
                                <td>$89.99</td>
                                <td><strong>5</strong></td>
                                <td>30</td>
                                <td><button class="btn btn-primary" onclick="openSellerStockOrderModal(2, 'Premium Wool Blanket', 30)">Order Stock</button></td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
            <div class="card">
                <div class="card-header">
                    <h3>Your Customer Orders</h3>
                </div>
                <div class="card-content" style="overflow-x:auto;">
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Order #</th>
                                <th>Customer</th>
                                <th>Amount</th>
                                <th>Status</th>
                                <th>Date</th>
                                <th>Confirmed By</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>ORD-2025072812345</td>
                                <td>John Doe</td>
                                <td>$175.97</td>
                                <td><span class="status status-pending">pending</span></td>
                                <td>7/28/2025</td>
                                <td><i>Pending</i></td>
                            </tr>
                             <tr>
                                <td>ORD-2025072708301</td>
                                <td>Jane Smith</td>
                                <td>$89.99</td>
                                <td><span class="status status-confirmed">confirmed</span></td>
                                <td>7/27/2025</td>
                                <td>Metro Distribution</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
    
    <div id="formModal" class="modal"><div class="modal-content" id="modal-content-host"></div></div>

    <script>
        // All JavaScript functions remain unchanged and will work as before.
        let currentUser = { id: 1, type: 'manufacturer' };
        let productCatalog = [];

        function showAlert(message, isError = false) {
            const container = document.getElementById('alert-container');
            const alertType = isError ? 'alert-danger' : 'alert-success';
            container.innerHTML = `<div class="alert ${alertType}">${message}</div>`;
            setTimeout(() => { container.innerHTML = ''; }, 5000);
        }

        async function api(endpoint, options = {}) {
            try {
                const response = await fetch(`/api${endpoint}`, {
                    headers: { 'Content-Type': 'application/json', 'X-User-ID': currentUser.id, 'X-User-Type': currentUser.type },
                    ...options
                });
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || 'API request failed');
                return data;
            } catch (err) {
                showAlert(err.message, true);
                throw err;
            }
        }
        
        function switchUser(id, type, btn) {
            currentUser = { id, type };
            document.querySelectorAll('.user-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            loadDashboard();
        }

        function renderTable(headers, rows) {
            const head = `<thead><tr>${headers.map(h => `<th>${h}</th>`).join('')}</tr></thead>`;
            const body = `<tbody>${rows.map(row => `<tr>${row.map(cell => `<td>${cell}</td>`).join('')}</tr>`).join('')}</tbody>`;
            return `<div class="card-content" style="overflow-x:auto;"><table class="table">${head}${body}</table></div>`;
        }

        async function loadDashboard() {
            document.getElementById('dashboard').innerHTML = '<div class="loading-spinner"></div>';
            try {
                const data = await api('/dashboard');
                let html = '';
                if (currentUser.type === 'manufacturer') {
                    html += `<div class="card"><div class="card-header"><h3>Inventory</h3></div>${renderTable(
                        ['Product', 'Model', 'Stock', 'Actions'],
                        data.inventory.map(p => [p.name, p.model, `<strong>${p.quantity}</strong> units`, `<button class="btn btn-secondary" onclick="openMfgUpdateModal(${p.product_id}, '${p.name}', ${p.quantity})">Edit Stock</button>`])
                    )}</div>`;
                    html += `<div class="card"><div class="card-header"><h3>All Customer Orders</h3></div>${renderTable(
                        ['Order #', 'Seller', 'Distributor', 'Status', 'Date', 'Actions'],
                        data.orders.map(o => [o.order_number, o.seller, o.distributor, `<span class="status status-${o.status}">${o.status}</span>`, new Date(o.created_at).toLocaleDateString(), o.status === 'pending' ? `<button class="btn btn-primary" onclick="updateOrderStatus(${o.id}, 'confirmed')">Confirm</button>` : 'N/A'])
                    )}</div>`;
                }
                if (currentUser.type === 'distributor') {
                    html += `<div class="card"><div class="card-header"><h3>Inventory & Ordering</h3></div>${renderTable(
                        ['Product', 'Model', 'Price', 'Your Stock', 'Mfg. Stock', 'Actions'],
                        data.inventory.map(p => [p.name, p.model, `$${p.price}`, `<strong>${p.your_stock}</strong>`, p.manufacturer_stock, `<button class="btn btn-primary" onclick="openDistOrderModal(${p.id}, '${p.name}')">Order More</button>`])
                    )}</div>`;
                    html += `<div class="card"><div class="card-header"><h3>Customer Orders to Fulfill</h3></div>${renderTable(
                        ['Order #', 'Customer', 'From Seller', 'Status', 'Date', 'Actions'],
                        data.orders.map(o => [o.order_number, o.customer_name, o.seller, `<span class="status status-${o.status}">${o.status}</span>`, new Date(o.created_at).toLocaleDateString(), o.status === 'pending' ? `<button class="btn btn-primary" onclick="updateOrderStatus(${o.id}, 'confirmed')">Confirm</button>` : 'N/A'])
                    )}</div>`;
                }
                if (currentUser.type === 'seller') {
                    productCatalog = data.products; 
                    html += `<div class="card"><div class="card-header"><h3>Product Catalog & Inventory</h3><button class="btn btn-primary" onclick="openSellerOrderModal()">+ New Customer Order</button></div>${renderTable(
                        ['Product', 'Model', 'Price', 'Your Stock', 'Distributor Stock', 'Actions'],
                        data.products.map(p => [p.name, p.model, `$${p.price}`, `<strong>${p.seller_stock}</strong>`, p.distributor_stock, `<button class="btn btn-primary" onclick="openSellerStockOrderModal(${p.id}, '${p.name}', ${p.distributor_stock})">Order Stock</button>`])
                    )}</div>`;
                     html += `<div class="card"><div class="card-header"><h3>Your Customer Orders</h3></div>${renderTable(
                        ['Order #', 'Customer', 'Amount', 'Status', 'Date', 'Confirmed By'],
                        data.orders.map(o => [o.order_number, o.customer_name, `$${Number(o.total_amount).toFixed(2)}`, `<span class="status status-${o.status}">${o.status}</span>`, new Date(o.created_at).toLocaleDateString(), o.confirmer_name || '<i>Pending</i>'])
                    )}</div>`;
                }
                document.getElementById('dashboard').innerHTML = html;
            } catch (err) { document.getElementById('dashboard').innerHTML = `<div class="alert alert-danger">Could not load dashboard. ${err.message}</div>`; }
        }

        function openModal(html) {
            document.getElementById('modal-content-host').innerHTML = html;
            document.getElementById('formModal').style.display = 'block';
        }
        function closeModal() { document.getElementById('formModal').style.display = 'none'; }

        function openMfgUpdateModal(id, name, qty) {
            openModal(`<h2>Update Inventory</h2><p>Product: ${name}</p><div class="form-group"><label for="mfgQty">New Quantity</label><input id="mfgQty" type="number" value="${qty}"></div><button class="btn btn-primary" onclick="submitMfgUpdate(${id})">Update Stock</button>`);
        }
        function openDistOrderModal(id, name) {
            openModal(`<h2>Order from Manufacturer</h2><p>Product: ${name}</p><div class="form-group"><label for="distQty">Quantity to Order</label><input id="distQty" type="number" min="1"></div><button class="btn btn-primary" onclick="submitDistOrder(${id})">Place Order</button>`);
        }
        function openSellerStockOrderModal(id, name, dist_stock) {
            openModal(`<h2>Order Stock from Distributor</h2><p>Product: ${name}</p><p>Distributor has: <strong>${dist_stock} units</strong> available.</p><div class="form-group"><label for="sellerQty">Quantity to Order</label><input id="sellerQty" type="number" min="1" max="${dist_stock}"></div><button class="btn btn-primary" onclick="submitSellerStockOrder(${id})">Place Stock Order</button>`);
        }
        function openSellerOrderModal() {
            const productList = productCatalog.map(p => `<div><span><strong>${p.name}</strong><br><small>Price: $${p.price} | Available: ${p.seller_stock + p.distributor_stock}</small></span> <input type="number" class="order-item form-group input" min="0" data-id="${p.id}" data-price="${p.price}" placeholder="0"></div>`).join('');
            openModal(`<h2>Create Customer Order</h2>
                <div class="form-group"><label for="custName">Customer Name</label><input id="custName" type="text"></div>
                <div class="form-group"><label for="custEmail">Customer Email</label><input id="custEmail" type="email"></div>
                <hr style="border:none; border-top:1px solid var(--border-color); margin: 1.5rem 0;">
                <h3 style="margin-bottom: 1rem;">Order Items</h3>
                <div class="order-item-list">${productList}</div>
                <button class="btn btn-primary" style="width:100%; padding:15px;" onclick="submitSellerOrder()">Create Customer Order</button>`);
        }
        
        async function submitMfgUpdate(product_id) {
            const quantity = parseInt(document.getElementById('mfgQty').value);
            if (isNaN(quantity) || quantity < 0) return showAlert('Please enter a valid quantity.', true);
            await api('/manufacturer/inventory', { method: 'PUT', body: JSON.stringify({ product_id, quantity }) })
                .then(data => { showAlert(data.message); closeModal(); loadDashboard(); })
                .catch(() => {});
        }
        async function submitDistOrder(product_id) {
            const quantity = parseInt(document.getElementById('distQty').value);
            if (!quantity || quantity <= 0) return showAlert('Please enter a quantity greater than 0.', true);
            await api('/distributor/order', { method: 'POST', body: JSON.stringify({ product_id, quantity }) })
                .then(data => { showAlert(data.message); closeModal(); loadDashboard(); })
                .catch(() => {});
        }
        async function submitSellerStockOrder(product_id) {
            const quantity = parseInt(document.getElementById('sellerQty').value);
            if (!quantity || quantity <= 0) return showAlert('Please enter a quantity greater than 0.', true);
            await api('/seller/stock_order', { method: 'POST', body: JSON.stringify({ product_id, quantity }) })
                .then(data => { showAlert(data.message); closeModal(); loadDashboard(); })
                .catch(() => {});
        }
        async function submitSellerOrder() {
            const items = Array.from(document.querySelectorAll('.order-item'))
                .map(i => ({ product_id: parseInt(i.dataset.id), quantity: parseInt(i.value) || 0, price: parseFloat(i.dataset.price) }))
                .filter(i => i.quantity > 0);

            if(items.length === 0) return showAlert('Please add at least one item to the order', true);
            
            const payload = {
                customer_name: document.getElementById('custName').value.trim(),
                customer_email: document.getElementById('custEmail').value.trim(),
                items
            };

            if(!payload.customer_name) return showAlert('Customer name is required', true);
            
            await api('/seller/order', { method: 'POST', body: JSON.stringify(payload) })
                .then(data => { showAlert(data.message); closeModal(); loadDashboard(); })
                .catch(() => {});
        }
        async function updateOrderStatus(order_id, status) {
            await api(`/order/${order_id}/status`, { method: 'PUT', body: JSON.stringify({ status }) })
                .then(data => { showAlert(data.message); loadDashboard(); })
                .catch(() => {});
        }

        window.onclick = (event) => { if (event.target == document.getElementById('formModal')) closeModal(); };
        document.addEventListener('DOMContentLoaded', () => loadDashboard());
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


    #pip install flask flask-cors mysql-connector-python
    #Python web_server.py