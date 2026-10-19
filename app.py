from flask import Flask, request, redirect, render_template, render_template_string, abort
import sqlite3

app = Flask(__name__)
DATABASE = "bizmanager.db"


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL
            )
        """)


@app.route("/")
def home():
    search = request.args.get("search", "").strip()

    with get_db_connection() as conn:
        if search:
            products = conn.execute(
                """
                SELECT * FROM products
                WHERE name LIKE ?
                ORDER BY id DESC
                """,
                (f"%{search}%",)
            ).fetchall()
        else:
            products = conn.execute(
                "SELECT * FROM products ORDER BY id DESC"
            ).fetchall()
            
    with get_db_connection() as conn:
     stats = conn.execute("""
        SELECT
            COUNT(*) AS total_products,
            COALESCE(SUM(quantity), 0) AS total_units,
            COALESCE(SUM(price * quantity), 0) AS stock_value,
            COALESCE(
                SUM(CASE WHEN quantity < 5 THEN 1 ELSE 0 END),
                0
            ) AS low_stock
        FROM products
    """).fetchone()


    return render_template(
    "index.html",
    products=products,
    stats=stats
)


@app.route("/add-product", methods=["POST"])
def add_product():
    name = request.form.get("name", "").strip()

    try:
        price = float(request.form["price"])
        quantity = int(request.form["quantity"])
        if not name or price < 0 or quantity < 0:
            raise ValueError
    except (ValueError, KeyError):
        abort(400, description="Μη έγκυρα στοιχεία προϊόντος.")

    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO products (name, price, quantity) VALUES (?, ?, ?)",
            (name, price, quantity)
        )

    return redirect("/")


@app.route("/edit-product/<int:product_id>", methods=["GET", "POST"])
def edit_product(product_id):
    with get_db_connection() as conn:
        product = conn.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone()

        if product is None:
            abort(404)

        if request.method == "POST":
            name = request.form.get("name", "").strip()

            try:
                price = float(request.form["price"])
                quantity = int(request.form["quantity"])
                if not name or price < 0 or quantity < 0:
                    raise ValueError
            except (ValueError, KeyError):
                abort(400, description="Μη έγκυρα στοιχεία προϊόντος.")

            conn.execute("""
                UPDATE products
                SET name = ?, price = ?, quantity = ?
                WHERE id = ?
            """, (name, price, quantity, product_id))

            return redirect("/")

    return render_template_string("""
    <!DOCTYPE html>
    <html lang="el">
    <head>
        <meta charset="UTF-8">
        <title>Επεξεργασία προϊόντος</title>
    </head>
    <body style="font-family:Arial;max-width:600px;margin:40px auto">
        <h1>Επεξεργασία προϊόντος</h1>
        <form method="POST">
            <p>Όνομα</p>
            <input name="name" value="{{ product['name'] }}" required>
            <p>Τιμή (€)</p>
            <input name="price" type="number" step="0.01" min="0"
                   value="{{ product['price'] }}" required>
            <p>Ποσότητα</p>
            <input name="quantity" type="number" step="1" min="0"
                   value="{{ product['quantity'] }}" required>
            <p><button type="submit">Αποθήκευση</button></p>
        </form>
        <a href="/">Επιστροφή στην αποθήκη</a>
    </body>
    </html>
    """, product=product)


@app.route("/delete-product/<int:product_id>", methods=["POST"])
def delete_product(product_id):
    with get_db_connection() as conn:
        conn.execute(
            "DELETE FROM products WHERE id = ?", (product_id,)
        )

    return redirect("/")



init_db()

if __name__ == "__main__":
    app.run(debug=True)
