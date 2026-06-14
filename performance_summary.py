import json
from collections import defaultdict
from statistics import mean

runs = []
with open("run_log.jsonl") as f:
    for line in f:
        runs.append(json.loads(line))

print(f"Total runs logged: {len(runs)}")
print(f"Time span: {runs[0]['timestamp']} → {runs[-1]['timestamp']}")
print(f"DB growth: {runs[0]['total_articles_in_db']} → {runs[-1]['total_articles_in_db']} articles "
      f"(+{runs[-1]['total_articles_in_db'] - runs[0]['total_articles_in_db']})")

# --- Per-source performance ---
print("\n=== Per-Source Performance ===")
agency_times = defaultdict(list)
agency_errors = defaultdict(int)
agency_new_articles = defaultdict(int)
agency_runs = defaultdict(int)

for run in runs:
    for src in run["sources"]:
        agency_times[src["agency"]].append(src["elapsed_seconds"])
        agency_new_articles[src["agency"]] += src["saved"]
        agency_runs[src["agency"]] += 1
        if src["error"]:
            agency_errors[src["agency"]] += 1

print(f"{'Agency':<22} {'Runs':<6} {'Errors':<8} {'Avg time (s)':<14} {'Min':<8} {'Max':<8} {'New articles'}")
for agency in agency_times:
    times = agency_times[agency]
    print(f"{agency:<22} {agency_runs[agency]:<6} {agency_errors[agency]:<8} "
          f"{mean(times):<14.2f} {min(times):<8.2f} {max(times):<8.2f} {agency_new_articles[agency]}")

# --- Overall reliability ---
total_attempts = sum(agency_runs.values())
total_errors = sum(agency_errors.values())
success_rate = (total_attempts - total_errors) / total_attempts * 100

print(f"\n=== Overall Reliability ===")
print(f"Total source-attempts: {total_attempts}")
print(f"Total errors: {total_errors}")
print(f"Success rate: {success_rate:.1f}%")

# --- Throughput ---
print(f"\n=== Throughput ===")
total_new = sum(agency_new_articles.values())
print(f"New articles collected across all runs: {total_new}")
print(f"Average new articles per run: {total_new / len(runs):.2f}")
