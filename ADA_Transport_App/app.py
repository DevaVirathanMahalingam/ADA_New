from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = "super secret key"

# Initialize database
def init_db():
    conn = sqlite3.connect('ada_transport.db')
    c = conn.cursor()
    c.execute(''' 
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY,
            name TEXT
        )''')
    c.execute(''' 
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            datetime TEXT,
            material_name TEXT,
            vehicle_number TEXT,
            driver_name TEXT,
            material_cost REAL DEFAULT 0.0,
            transport_cost REAL DEFAULT 0.0,
            from_location TEXT,
            to_location TEXT,
            paid_amount REAL DEFAULT 0.0,
            total_amount REAL DEFAULT 0.0,
            remaining_amount REAL DEFAULT 0.0,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )''')
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/home')
def home():
    return render_template('home.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    if username == "sam" and password == "ada":
        flash('Login successful', 'success')
        return redirect(url_for('home'))
    else:
        flash('Invalid credentials', 'danger')
        return redirect(url_for('index'))

@app.route('/data_entry', methods=['GET', 'POST'])
def data_entry():
    total_amount = None
    remaining_amount = None
    
    if request.method == 'POST':
        client_name = request.form['client_name']
        material_name = request.form['material_name']
        vehicle_number = request.form['vehicle_number']
        driver_name = request.form['driver_name']
        
        # Convert cost fields to float, default to 0.0 if empty
        material_cost = float(request.form.get('material_cost', 0) or 0.0)
        transport_cost = float(request.form.get('transport_cost', 0) or 0.0)
        from_location = request.form['from_location']
        to_location = request.form['to_location']
        paid_amount = float(request.form.get('paid_amount', 0) or 0.0)

        # Calculate total and remaining amounts
        total_amount = material_cost + transport_cost
        remaining_amount = total_amount - paid_amount

        conn = sqlite3.connect('ada_transport.db')
        c = conn.cursor()
        
        # Insert client if not exists and retrieve client_id
        c.execute("INSERT OR IGNORE INTO clients (name) VALUES (?)", (client_name,))
        c.execute("SELECT id FROM clients WHERE name=?", (client_name,))
        client_id = c.fetchone()[0]

        # Insert the record
        c.execute(''' 
            INSERT INTO records (
                client_id, datetime, material_name, vehicle_number, driver_name, material_cost, transport_cost, from_location, to_location, paid_amount, total_amount, remaining_amount
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''', (
                client_id, datetime.now(), material_name, vehicle_number, driver_name, 
                material_cost, transport_cost, from_location, to_location, 
                paid_amount, total_amount, remaining_amount
            ))
        
        conn.commit()
        conn.close()
        
        flash(f'Data saved successfully. Total Amount: {total_amount}, Remaining Amount: {remaining_amount}', 'success')
        return redirect(url_for('client_dashboard', client_name=client_name))
    
    return render_template('data_entry.html', total_amount=total_amount, remaining_amount=remaining_amount)


# Client dashboard with totals
@app.route('/dashboard/<client_name>')
def client_dashboard(client_name):
    conn = sqlite3.connect('ada_transport.db')
    c = conn.cursor()
    
    # Get the client ID
    c.execute("SELECT id FROM clients WHERE name=?", (client_name,))
    client = c.fetchone()
    
    if client is None:
        flash(f'Client {client_name} not found', 'danger')
        return redirect(url_for('index'))
    
    client_id = client[0]
    
    # Fetch all records for this client
    c.execute("SELECT * FROM records WHERE client_id=?", (client_id,))
    records = c.fetchall()
    
    # Calculate totals, treating NULL values as zero
    c.execute(""" 
        SELECT COALESCE(SUM(material_cost), 0.0), COALESCE(SUM(transport_cost), 0.0), 
               COALESCE(SUM(total_amount), 0.0), COALESCE(SUM(remaining_amount), 0.0)
        FROM records WHERE client_id=?
    """, (client_id,))
    totals = c.fetchone()
    material_total, transport_total, total_amount, remaining_total = totals
    
    conn.close()
    return render_template('dashboard.html', 
                           client_name=client_name, 
                           records=records, 
                           material_total=material_total,
                           transport_total=transport_total, 
                           total_amount=total_amount, 
                           remaining_total=remaining_total)


@app.route('/clear_client_data/<client_name>', methods=['POST'])
def clear_client_data(client_name):
    conn = sqlite3.connect('ada_transport.db')
    c = conn.cursor()

    c.execute("SELECT id FROM clients WHERE name=?", (client_name,))
    client = c.fetchone()
    
    if client is not None:
        client_id = client[0]
        c.execute("DELETE FROM records WHERE client_id=?", (client_id,))
        conn.commit()
        flash(f'All data for {client_name} cleared successfully', 'success')
    else:
        flash(f'Client {client_name} not found', 'danger')

    conn.close()
    return redirect(url_for('client_dashboard', client_name=client_name))

# Route to clear all data (both clients and records)
@app.route('/clear_data', methods=['POST'])
def clear_data():
    conn = sqlite3.connect('ada_transport.db')
    c = conn.cursor()
    c.execute("DELETE FROM records")
    c.execute("DELETE FROM clients")
    conn.commit()
    conn.close()
    flash('All data cleared successfully', 'success')
    return redirect(url_for('index'))

@app.route('/filter_by_driver', methods=['GET', 'POST'])
def filter_by_driver():
    driver_name = None
    filtered_records = []

    if request.method == 'POST':
        driver_name = request.form['driver_name']

        conn = sqlite3.connect('ada_transport.db')
        c = conn.cursor()

        # Fetch records filtered by driver name
        c.execute(''' 
            SELECT datetime, material_name, from_location, to_location, transport_cost 
            FROM records 
            WHERE driver_name LIKE ? 
        ''', ('%' + driver_name + '%',))
        
        filtered_records = c.fetchall()
        conn.close()

    return render_template('filter.html', filtered_records=filtered_records, driver_name=driver_name)

@app.route('/client', methods=['GET', 'POST'])
def client():
    client_name = None
    client_details = None
    records = None
    totals = None

    if request.method == 'POST':
        client_name = request.form.get('client_name')
        conn = sqlite3.connect('ada_transport.db')
        c = conn.cursor()

        # Get the client details
        c.execute("SELECT id, name FROM clients WHERE name=?", (client_name,))
        client = c.fetchone()

        if client:
            client_details = {"id": client[0], "name": client[1]}

            # Fetch all records for the client
            c.execute("""
                SELECT datetime, material_name, vehicle_number, driver_name, material_cost, 
                       transport_cost, from_location, to_location, paid_amount, total_amount, 
                       remaining_amount
                FROM records WHERE client_id=? ORDER BY datetime DESC
            """, (client[0],))
            records = c.fetchall()

            # Calculate totals
            c.execute("""
                SELECT COALESCE(SUM(material_cost), 0.0), 
                       COALESCE(SUM(transport_cost), 0.0), 
                       COALESCE(SUM(total_amount), 0.0), 
                       COALESCE(SUM(remaining_amount), 0.0) 
                FROM records WHERE client_id=?
            """, (client[0],))
            totals = c.fetchone()

        conn.close()

    return render_template(
        'client.html',
        client_name=client_name,
        client_details=client_details,
        records=records,
        totals=totals
    )


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
