import os

from flask import Flask, jsonify, request

from subsystems import REGISTRY

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(os.path.dirname(BACKEND_DIR), "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")


@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.route("/api/subsystems")
def list_subsystems():
    return jsonify(
        {
            name: {**module.META, "output_columns": module.OUTPUT_COLUMNS}
            for name, module in REGISTRY.items()
        }
    )


@app.route("/api/predict/<subsystem>", methods=["POST"])
def predict(subsystem):
    module = REGISTRY.get(subsystem)
    if module is None:
        return jsonify({"error": f"unknown subsystem '{subsystem}'"}), 404

    if "file" not in request.files:
        return jsonify({"error": "no file uploaded (expected form field 'file')"}), 400

    uploaded_file = request.files["file"]
    if not uploaded_file.filename:
        return jsonify({"error": "empty filename"}), 400

    ext = os.path.splitext(uploaded_file.filename)[1].lower()
    if ext not in module.META["allowed_extensions"]:
        allowed = ", ".join(sorted(module.META["allowed_extensions"]))
        return (
            jsonify({"error": f"{subsystem} expects a {allowed} file, got '{ext}'"}),
            400,
        )

    try:
        result = module.predict(uploaded_file)
    except Exception as exc:  # placeholder modules; keep the API resilient
        return jsonify({"error": f"prediction failed: {exc}"}), 500

    return jsonify(result)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
