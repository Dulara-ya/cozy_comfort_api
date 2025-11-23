# 🛋️ Cozy Comfort Supply Chain Management (SCM) System

This is a Flask-based web server application designed to simulate a basic supply chain for a company selling comfort goods (like blankets). The system includes user authentication and role-based dashboards for **Manufacturers**, **Distributors**, and **Sellers**, managing products, inventory, and customer orders.

## 🌐 System Architecture

The application follows a simple **three-tier supply chain model**:

1.  **Manufacturer (Cozy Comfort MFG):** Creates products and manages the primary stock.
2.  **Distributor (Metro Distribution):** Orders stock from the Manufacturer and supplies it to assigned Sellers.
3.  **Seller (The Comfort Store):** Orders stock from the Distributor and creates final customer orders, drawing inventory from both their own stock and the Distributor's stock.

[Image of a supply chain diagram showing Manufacturer -> Distributor -> Seller -> Customer]

## 🚀 Getting Started

### Prerequisites

* Python 3.x
* MySQL Server (accessible via network or locally)
* Required Python packages: `flask`, `mysql-connector-python`, `flask-cors`, `werkzeug`, `python-dotenv` (if using `.env` file for setup).

### Installation and Setup

1.  **Clone the repository:**
    ```bash
    git clone [YOUR_REPO_URL]
    cd Cozy-Comfort-Web-Server
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *(Note: You'll need to create a `requirements.txt` based on the imports in the file: `flask`, `mysql-connector-python`, `flask-cors`, `werkzeug`, `python-dotenv`.)*

3.  **Configure Environment Variables:**
    The application reads database credentials from environment variables. Create a file named `.env` in the project root or set these in your shell:
    ```
    MYSQL_HOST=localhost
    MYSQL_USER=root
    MYSQL_PASSWORD=your_mysql_password
    MYSQL_DATABASE=cozycomfort_db
    MYSQL_PORT=3306
    PORT=5021
    ```

4.  **Run the Server:**
    ```bash
    python server.py
    ```
    *(If your file is named `Cozy Comfort Web Server.py`, rename it to `server.py` or run `python "Cozy Comfort Web Server.py"`).*

5.  **Access the Application:**
    Open your browser and navigate to `http://localhost:5021` (or the port specified in your environment variables).

### 🔑 Sample Login Credentials

The `DatabaseManager.insert_sample_data` method automatically populates the database with initial users. All sample users use the password: `pass`.

| Role | Username | Company Name |
| :--- | :--- | :--- |
| **Manufacturer** | `cozy_mfg` | Cozy Comfort MFG |
| **Distributor** | `metro_dist` | Metro Distribution |
| **Seller** | `comfort_store` | The Comfort Store |

---

## 💾 Database Schema

The system uses a MySQL database structured with the following key tables:

| Table | Description | Key Columns |
| :--- | :--- | :--- |
| `users` | Stores user accounts and their roles (`manufacturer`, `distributor`, `seller`). | `id`, `username`, `user_type`, `company_name` |
| `products` | Stores details of items manufactured. | `id`, `name`, `model`, `price`, `manufacturer_id (FK)` |
| `inventory` | Tracks the stock quantity of products, separated by the `owner_id` (who holds the stock) and `owner_type`. | `product_id (FK)`, `owner_id (FK)`, `quantity` |
| `orders` | Records customer orders placed by a Seller. | `id`, `seller_id (FK)`, `distributor_id (FK)`, `total_amount`, `status` |
| `order_items` | Details the products and quantities within each order. | `order_id (FK)`, `product_id (FK)`, `quantity`, `unit_price` |
| `distributor_sellers`| Links Distributors to their assigned Sellers. | `distributor_id (FK)`, `seller_id (FK)` |

---

## 🔌 API Endpoints

The application exposes several REST API endpoints for different business operations:

### Authentication

| Route | Method | Role | Description |
| :--- | :--- | :--- | :--- |
| `/api/login` | `POST` | N/A | Authenticates user and sets session. |
| `/api/logout` | `POST` | Logged In | Clears session. |
| `/api/session` | `GET` | N/A | Checks current login status and returns user data. |

### Role-Based Operations (Requires Authentication)

| Route | Method | Role | Description |
| :--- | :--- | :--- | :--- |
| `/api/dashboard` | `GET` | All | Retrieves data relevant to the user's role (inventory, orders). |
| `/api/manufacturer/product`| `POST` | Manufacturer | Creates a new product and initial manufacturer inventory record. |
| `/api/manufacturer/inventory`| `PUT` | Manufacturer | Updates the manufacturer's stock level for a product. |
| `/api/distributor/order`| `POST` | Distributor | Orders stock from the Manufacturer, deducting from manufacturer inventory and adding to distributor inventory (uses database transaction). |
| `/api/seller/stock_order`|
