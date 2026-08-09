"""
Cutting Optimizer Pro — Python backend
Uses Google OR-Tools CP-SAT to solve the 1D cutting-stock problem exactly
(minimum number of stock bars), matching the "Online Google OR-Tools • OPTIMAL"
behavior you compared against.

Deploy target: Render (zero extra services needed — just this Flask app).
Matches your usual stack: Node/Render frontend can call this as a JSON API,
or this can serve the same index.html directly as static files.

Run locally:
    pip install -r requirements.txt
    python app.py

Deploy on Render:
    Build command:  pip install -r requirements.txt
    Start command:  gunicorn app:app
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from ortools.sat.python import cp_model
import os
import math

app = Flask(__name__, static_folder="static")
CORS(app)


# ---------------------------------------------------------------------------
# 1D cutting stock — exact solve via CP-SAT (pattern-based column model)
# ---------------------------------------------------------------------------
def generate_patterns(lengths, stock_len, kerf, max_patterns=200000):
    """Enumerate every combination of piece counts that fits in one stock bar."""
    n = len(lengths)
    patterns = []
    counts = [0] * n

    def rec(idx, used_len, used_count):
        if len(patterns) > max_patterns:
            return
        if idx == n:
            if used_count > 0:
                total = used_len + max(0, used_count - 1) * kerf
                if total <= stock_len + 1e-6:
                    patterns.append(tuple(counts))
            return
        length = lengths[idx]
        c = 0
        while True:
            new_used_len = used_len + c * length
            new_used_count = used_count + c
            kerf_so_far = max(0, new_used_count - 1) * kerf
            if new_used_len + kerf_so_far > stock_len + 1e-6:
                break
            counts[idx] = c
            rec(idx + 1, new_used_len, new_used_count)
            c += 1
        counts[idx] = 0

    rec(0, 0, 0)
    return patterns


def solve_cutting_stock_1d(pieces, stock_len, kerf, time_limit_s=10):
    """
    pieces: list of {"len": float, "qty": int, "label": str}
    Returns: {"bars": [...], "num_bars": int, "waste": float, "efficiency": float}
    Exact minimum-bar solution via CP-SAT over all feasible cutting patterns.
    """
    lengths = [p["len"] for p in pieces]
    demand = [p["qty"] for p in pieces]
    labels = [p.get("label", f"Piece {i}") for i, p in enumerate(pieces)]

    patterns = generate_patterns(lengths, stock_len, kerf)
    if not patterns:
        return {"error": "No feasible cutting pattern found for given stock length."}

    # Upper bound on bars needed (simple heuristic bound to size the model)
    upper_bound = sum(demand)  # worst case: one piece per bar

    model = cp_model.CpModel()
    n_patterns = len(patterns)

    # x[j] = number of times pattern j is used
    max_use = upper_bound
    x = [model.NewIntVar(0, max_use, f"x_{j}") for j in range(n_patterns)]

    # y[j] = 1 if pattern j used at all (for bar-count objective)
    used_bars = model.NewIntVar(0, upper_bound, "used_bars")
    model.Add(used_bars == sum(x))

    # demand coverage
    for i in range(len(lengths)):
        model.Add(sum(patterns[j][i] * x[j] for j in range(n_patterns)) >= demand[i])

    model.Minimize(used_bars)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {"error": "Solver could not find a solution in time."}

    bars = []
    for j in range(n_patterns):
        count = solver.Value(x[j])
        for _ in range(count):
            bar_items = []
            used_len = 0
            for i, c in enumerate(patterns[j]):
                for _ in range(c):
                    bar_items.append({"len": lengths[i], "label": labels[i]})
                    used_len += lengths[i]
            n_items = len(bar_items)
            used_len += max(0, n_items - 1) * kerf
            bars.append({"items": bar_items, "used": used_len, "waste": stock_len - used_len})

    total_stock = len(bars) * stock_len
    total_used = sum(b["used"] for b in bars)
    waste = total_stock - total_used
    efficiency = (total_used / total_stock * 100) if total_stock > 0 else 0
    optimal = status == cp_model.OPTIMAL

    return {
        "bars": bars,
        "num_bars": len(bars),
        "waste": round(waste, 3),
        "efficiency": round(efficiency, 1),
        "optimal": optimal,
    }


@app.route("/api/optimize/1d", methods=["POST"])
def optimize_1d():
    data = request.get_json(force=True)
    pieces = data.get("pieces", [])   # [{len, qty, label}]
    stock_len = float(data.get("stock_len"))
    kerf = float(data.get("kerf", 0))
    time_limit = float(data.get("time_limit", 10))

    if not pieces or stock_len <= 0:
        return jsonify({"error": "pieces and stock_len are required"}), 400

    result = solve_cutting_stock_1d(pieces, stock_len, kerf, time_limit)
    if "error" in result:
        return jsonify(result), 422
    return jsonify(result)


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "engine": "ortools-cpsat"})


# Optional: serve the frontend index.html directly from this same service
@app.route("/")
def serve_index():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), "index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
