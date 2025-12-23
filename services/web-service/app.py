import json
from flask import Flask, render_template_string, request, redirect, url_for, flash
import requests
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"  # You should change this in production

REGISTRY_URL = os.environ.get("REGISTRY_URL", "http://registry:5000")

CATALOG_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>E-commerce Storefront</title>
</head>
<body>
    <h1>Product Catalog</h1>
    <form method="POST" action="/buy">
    <table border="1">
        <tr>
            <th>Product</th>
            <th>Description</th>
            <th>Price</th>
            <th>Available</th>
            <th>Quantity</th>
        </tr>
        {% for prod in products %}
        <tr>
            <td>{{ prod.name }}</td>
            <td>{{ prod.description }}</td>
            <td>{{ prod.price }}</td>
            <td>{{ prod.stock }}</td>
            <td>
                <input type="number" min="0" max="{{ prod.stock }}" name="prod_{{ prod.id }}" value="0">
            </td>
        </tr>
        {% endfor %}
    </table>
    <br>
    Your email: <input type="email" name="customer_email" required>
    <button type="submit">Buy Selected</button>
    </form>
    {% with messages = get_flashed_messages() %}
      {% if messages %}
        <ul>
        {% for message in messages %}
          <li>{{ message }}</li>
        {% endfor %}
        </ul>
      {% endif %}
    {% endwith %}
</body>
</html>
"""


@app.route("/")
def home():
    products = []
    try:
        # Discover API Gateway from registry
        api_gateway = requests.get(f"{REGISTRY_URL}/discover/api-gateway", timeout=5)
        if api_gateway.status_code == 200:
            api_gateway_url = api_gateway.json().get("url")
            # Get products via API Gateway
            r = requests.get(
                f"{api_gateway_url}/proxy/product-service/api/products", timeout=5
            )
            products = r.json().get("products", [])
    except Exception as e:
        products = []
        flash(f"Could not load products: {e}")
    return render_template_string(CATALOG_TEMPLATE, products=products)


@app.route("/buy", methods=["POST"])
def buy():
    items = []
    for key, value in request.form.items():
        if key.startswith("prod_") and value and int(value) > 0:
            prod_id = key.replace("prod_", "")
            items.append({"product_id": prod_id, "quantity": int(value)})
    customer = request.form.get("customer_email")

    order_data = {
        "customer_id": customer,
        "customer_email": customer,
        "items": items,
        "payment": {
            "method": "credit_card",
            "card_number": "4532123456789012",
            "cvv": "123",
        },
        "shipping_address": {
            "street": "N/A",
            "city": "N/A",
            "zip": "N/A",
            "country": "N/A",
        },
    }

    try:
        # Discover API Gateway and use correct proxy path
        api_gateway = requests.get(f"{REGISTRY_URL}/discover/api-gateway", timeout=5)
        if api_gateway.status_code == 200:
            api_gateway_url = api_gateway.json().get("url")
            # POST to /proxy/order-service/api/orders
            resp = requests.post(
                f"{api_gateway_url}/proxy/order-service/api/orders",
                json=order_data,
                timeout=10,
            )
            if resp.status_code == 201:
                flash("Order placed successfully! Check your email!")
            else:
                flash(f"Order failed: {resp.text}")
        else:
            flash("Could not discover API Gateway")
    except Exception as e:
        flash(f"Could not place order: {e}")

    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
