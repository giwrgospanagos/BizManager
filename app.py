import os
import sqlite3
from contextlib import contextmanager

from flask import (
    Flask,
    request,
    redirect,
    render_template,
    render_template_string,
    abort,
)

app = Flask(__name__)

DATABASE = "bizmanager.db"
DATABASE_URL = os.environ.get("DATABASE_URL")

# PostgreSQL is used online; SQLite remains available locally.
if DATABASE_URL:
    import psycopg
    from psycopg.rows import dict_row


@contextmanager
def get_db_connection():
    if DATABASE_URL:
        conn = psycopg.connect(
            DATABASE_URL,
            row_factory=dict_row
        )
    else:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute_query(conn, query, params=()):
    # SQLite uses ?; PostgreSQL uses %s.
    if DATABASE_URL:
        query = query.replace("?", "%s")

    return conn.execute(query, params)


def init_db():
    if DATABASE_URL:
        create_table_sql = """
            CREATE TABLE IF NOT EXISTS products (
                id BIGSERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                price DOUBLE PRECISION NOT NULL,
                quantity INTEGER NOT NULL
            )
        """
    else:
        create_table_sql = """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL
            )
        """

    with get_db_connection() as conn:
        execute_query(conn, create_table_sql)


@app.route("/")
def home():
    search = request.args.get("search", "").strip()

    with get_db_connection() as conn:
        if search:
            products = execute_query(
                conn,
                """
                SELECT * FROM products
                WHERE name LIKE ?
                ORDER BY id DESC
                """,
                (f"%{search}%",)
            ).fetchall()
        else:
            products = execute_query(
                conn,
                "SELECT * FROM products ORDER BY id DESC"
            ).fetchall()

        stats = execute_query(
            conn,
            """
            SELECT
                COUNT(*) AS total_products,
                COALESCE(SUM(quantity), 0) AS total_units,
                COALESCE(SUM(price * quantity), 0) AS stock_value,
                COALESCE(
                    SUM(
                        CASE WHEN quantity < 5 THEN 1 ELSE 0 END
                    ),
                    0
                ) AS low_stock
            FROM products
            """
        ).fetchone()

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
        execute_query(
            conn,
            """
            INSERT INTO products (name, price, quantity)
            VALUES (?, ?, ?)
            """,
            (name, price, quantity)
        )

    return redirect("/")


@app.route(
    "/edit-product/<int:product_id>",
    methods=["GET", "POST"]
)
def edit_product(product_id):
    with get_db_connection() as conn:
        product = execute_query(
            conn,
            "SELECT * FROM products WHERE id = ?",
            (product_id,)
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
                abort(
                    400,
                    description="Μη έγκυρα στοιχεία προϊόντος."
                )

            execute_query(
                conn,
                """
                UPDATE products
                SET name = ?, price = ?, quantity = ?
                WHERE id = ?
                """,
                (name, price, quantity, product_id)
            )

            return redirect("/")

    return render_template_string(
        """
        <!DOCTYPE html>
        <html lang="el">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport"
                  content="width=device-width, initial-scale=1">
            <title>Επεξεργασία προϊόντος</title>
        </head>
        <body style="font-family:Arial;max-width:600px;margin:40px auto">
            <h1>Επεξεργασία προϊόντος</h1>
            <form method="POST">
                <p>Όνομα</p>
                <input name="name"
                       value="{{ product['name'] }}" required>
                <p>Τιμή (€)</p>
                <input name="price" type="number" step="0.01"
                       min="0" value="{{ product['price'] }}" required>
                <p>Ποσότητα</p>
                <input name="quantity" type="number" step="1"
                       min="0" value="{{ product['quantity'] }}" required>
                <p><button type="submit">Αποθήκευση</button></p>
            </form>
            <a href="/">Επιστροφή στην αποθήκη</a>
        </body>
        </html>
        """,
        product=product
    )


@app.route(
    "/delete-product/<int:product_id>",
    methods=["POST"]
)
def delete_product(product_id):
    with get_db_connection() as conn:
        execute_query(
            conn,
            "DELETE FROM products WHERE id = ?",
            (product_id,)
        )

    return redirect("/")


init_db()

if __name__ == "__main__":
    app.run(debug=True)
