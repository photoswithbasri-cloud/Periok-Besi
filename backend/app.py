import os

from flask import Flask, jsonify, request

from subsystems import REGISTRY

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(os.path.dirname(BACKEND_DIR), "frontend")

# Rail Corrugation and SHM score one row per test file, and their Info Kits
# require a single combined predictions.csv covering every test file (68 for
# Rail, 16 for SHM) — so these two accept a batch of files in one request.
# Door (one continuous Test.csv stream) and ACV (a single held-out test file)
# stay single-file.
MULTI_FILE_SUBSYSTEMS = {"rail_corrugation", "shm"}

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

    if subsystem in MULTI_FILE_SUBSYSTEMS:
        uploaded_files = request.files.getlist("file")
        if not uploaded_files:
            return jsonify({"error": "no file uploaded (expected form field 'file')"}), 400
    else:
        if "file" not in request.files:
            return jsonify({"error": "no file uploaded (expected form field 'file')"}), 400
        uploaded_files = [request.files["file"]]

    for uploaded_file in uploaded_files:
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
        per_file_results = [module.predict(f) for f in uploaded_files]
    except Exception as exc:  # placeholder modules; keep the API resilient
        return jsonify({"error": f"prediction failed: {exc}"}), 500

    if len(per_file_results) == 1:
        return jsonify(per_file_results[0])

    # Combine every file's rows into one response, so the download button
    # produces a single predictions.csv covering the whole batch.
    combined_results = []
    for result in per_file_results:
        combined_results.extend(result["results"])

    return jsonify(
        {
            "health_score": round(
                sum(result["health_score"] for result in per_file_results) / len(per_file_results)
            ),
            "alert": any(result["alert"] for result in per_file_results),
            "results": combined_results,
            "file_count": len(per_file_results),
        }
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
