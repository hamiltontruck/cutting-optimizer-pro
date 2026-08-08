# Cutting Optimizer Pro

Two ways to run this, from lightest to strongest:

## 1. Frontend only (index.html)
No install, no server. Open `index.html` on any phone or PC, or host it on
GitHub Pages the way you host MAGPMS/EHAB Ride.

- 1D (bars/pipes/lumber) and 2D (sheets) tabs
- Pattern-based near-optimal packing done entirely in JavaScript
  (enumerates every valid cut pattern per bar, greedily covers demand,
  then runs a compaction pass to squeeze out extra bars)
- Paste rows or import CSV to load pieces
- Download CSV / Print the result

This gets very close to optimal (matched the OR-Tools reference exactly
on your 3.6m/2.3m/12m test: 11 bars, 95.4% efficiency) and runs instantly
with zero backend.

## 2. Python + Google OR-Tools backend (backend/app.py)
For guaranteed **exact optimal** solutions (true ILP solve via CP-SAT),
same engine class as the reference site you compared against.

### Run locally
```bash
cd backend
pip install -r requirements.txt
python app.py
```
Server starts on `http://localhost:8080`.

### API
`POST /api/optimize/1d`
```json
{
  "pieces": [
    {"len": 3.6, "qty": 19, "label": "Leg"},
    {"len": 2.3, "qty": 25, "label": "Rail"}
  ],
  "stock_len": 12,
  "kerf": 0
}
```
Returns bar-by-bar cutting plan, bar count, waste, efficiency, and whether
the solver proved optimality.

### Deploy to Render (matches your usual stack)
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- Add an env var if you want a custom port (Render sets `PORT` automatically)

### Wiring the frontend to the backend
Right now `index.html` solves everything client-side. To use the exact
Python solver instead for large/critical jobs, add a fetch call to
`/api/optimize/1d` on your Render URL and swap in the returned `bars` array
wherever `runOptimize1d()` currently uses its JS result. Say the word and
I'll wire that in directly next.

## Files
```
index.html            <- standalone frontend, works anywhere
backend/app.py         <- Flask + OR-Tools exact solver
backend/requirements.txt
```
