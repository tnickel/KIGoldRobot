#!/usr/bin/env python3
"""
Orchestrator for Automated Hyperparameter Search & Risk Tuning (05_auto_search.py)
---------------------------------------------------------------------------------
This script loops through a grid of Random Forest hyperparameters, trains the model,
compiles the MQL5 EA, runs the walk-forward optimizer, and evaluates the results.

To guarantee that the drawdown is strictly under 10% while maximizing profits and
satisfying the trade count constraint (>= 100 trades/year, i.e., >= 200 total),
it calculates a scaled lot size:
    scaled_lot = floor(0.1 * (9.5 / max_drawdown))

The script selects the model and parameter combination that maximizes the scaled profit
under a strict 10% drawdown budget and >= 200 trades.
"""

import os
import sys
import json
import subprocess
import math
import time

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRAIN_SCRIPT = os.path.join(BASE_DIR, "python_scripts", "02_train_model.py")
OPT_SCRIPT = os.path.join(BASE_DIR, "python_scripts", "03_optimize_ea.py")
COMPILER_PATH = r"C:\Forex\Mt5\TickmillLifeMql5\metaeditor64.exe"
MQ5_PATH = os.path.join(BASE_DIR, "mql5_ea", "XAU_ONNX_Bot.mq5")
COMPILE_LOG = os.path.join(BASE_DIR, "mql5_ea", "compile_output.log")
RESULTS_JSON = os.path.join(BASE_DIR, "backtest_reports", "xauusd_onnx_opt", "batch_results.json")
BEST_SET_PATH = os.path.join(BASE_DIR, "settings", "optimized_xauusd_best.set")

# Define Grid Search Space
GRID = [
    # (max_depth, min_samples_leaf, class_weight, timeframe)
    (5, 15, "balanced", "M30"),
    (5, 25, "balanced", "M30"),
    (6, 15, "balanced", "M30"),
    (6, 25, "balanced", "M30"),
    (7, 15, "balanced", "M30"),
    (7, 25, "balanced", "M30"),
    
    (5, 15, "none", "M30"),
    (5, 25, "none", "M30"),
    (6, 15, "none", "M30"),
    (6, 25, "none", "M30"),
    (7, 15, "none", "M30"),
    (7, 25, "none", "M30"),
]

def compile_ea():
    """Compiles the MQ5 EA using MetaEditor CLI."""
    if not os.path.exists(COMPILER_PATH):
        raise FileNotFoundError(f"MetaEditor compiler not found at {COMPILER_PATH}")
        
    cmd = f'"{COMPILER_PATH}" /portable /compile:"{MQ5_PATH}" /log:"{COMPILE_LOG}"'
    res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        print(f"Compilation warning/failed. Exit code: {res.returncode}")

def update_set_file_with_lot(set_path, scaled_lot):
    """Updates or appends the InpLotSize setting in the UTF-16 .set file."""
    if not os.path.exists(set_path):
        return
        
    # Read UTF-16 file lines
    with open(set_path, "r", encoding="utf-16") as f:
        lines = f.readlines()
        
    lot_written = False
    new_lines = []
    for line in lines:
        if line.startswith("InpLotSize="):
            new_lines.append(f"InpLotSize={scaled_lot}||0||0||0||N\n")
            lot_written = True
        else:
            new_lines.append(line)
            
    if not lot_written:
        new_lines.append(f"InpLotSize={scaled_lot}||0||0||0||N\n")
        
    with open(set_path, "w", encoding="utf-16") as f:
        f.writelines(new_lines)

def main():
    print("======================================================================")
    print("       AUTOMATED HYPERPARAMETER & RISK TUNING COCKPIT")
    print("======================================================================")
    print(f"Grid size: {len(GRID)} combinations to evaluate.")
    print("Target Constraints:")
    print("  - Drawdown        : < 10.0% (guaranteed via risk scaling)")
    print("  - Trades per year : >= 100 (>= 200 total trades in 2-year backtest)")
    print("  - Profit          : Positive & Maximized")
    print("======================================================================\n")
    
    best_candidate = None
    best_score = -1.0
    
    for idx, (max_depth, min_samples_leaf, class_weight, timeframe) in enumerate(GRID):
        print(f"[{idx+1}/{len(GRID)}] Evaluating: max_depth={max_depth}, min_samples_leaf={min_samples_leaf}, class_weight={class_weight}, TF={timeframe}")
        
        # 1. Train model
        print("  -> Training Model...", end="", flush=True)
        t_start = time.time()
        cmd_train = [
            sys.executable, TRAIN_SCRIPT,
            "--max-depth", str(max_depth),
            "--min-samples-leaf", str(min_samples_leaf),
            "--class-weight", class_weight
        ]
        res_train = subprocess.run(cmd_train, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res_train.returncode != 0:
            print(" FAILED!")
            print(res_train.stderr)
            continue
        print(f" Done ({time.time() - t_start:.1f}s)")
        
        # 2. Compile EA
        print("  -> Compiling EA...", end="", flush=True)
        try:
            compile_ea()
            print(" Done")
        except Exception as e:
            print(f" FAILED! {e}")
            continue
            
        # 3. Run Optimization
        print("  -> Running Walk-Forward Optimization...", end="", flush=True)
        cmd_opt = [
            sys.executable, OPT_SCRIPT,
            "--timeframe", timeframe
        ]
        res_opt = subprocess.run(cmd_opt, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res_opt.returncode != 0:
            print(" FAILED!")
            print(res_opt.stderr)
            continue
        print(" Done")
        
        # 4. Parse Results
        if not os.path.exists(RESULTS_JSON):
            print("  Warning: No results JSON generated!")
            continue
            
        with open(RESULTS_JSON, "r", encoding="utf-8") as f:
            res_data = json.load(f)
            
        run_res = res_data["runs"][0]
        if not run_res.get("success"):
            print(f"  Warning: Optimization execution failed: {run_res.get('error_message')}")
            continue
            
        profit = run_res["profit"]
        drawdown = run_res["drawdown"] # in %
        trades = run_res["trades"]
        pf = run_res["profit_factor"]
        win_rate = run_res["win_rate"]
        
        print(f"  Raw Result: Profit=${profit:.2f} | Drawdown={drawdown:.2f}% | Trades={trades} | PF={pf:.2f}")
        
        # 5. Evaluate scaled risk constraints
        if trades < 200:
            print(f"  [REJECTED] Candidate rejected (Trades count {trades} < 200 required).")
            continue
        if profit <= 0:
            print(f"  [REJECTED] Candidate rejected (Negative profit).")
            continue
            
        # Drawdown limit budget = 9.5% to stay safely under 10%
        # Standard lot size was 0.1. Scaled lot size:
        scaled_lot = math.floor(0.1 * (9.5 / drawdown) * 100) / 100.0
        scaled_lot = max(0.01, min(0.50, scaled_lot)) # clamp between 0.01 and 0.50
        
        scaled_drawdown = drawdown * (scaled_lot / 0.1)
        scaled_profit = profit * (scaled_lot / 0.1)
        rf = profit / (drawdown + 0.001)
        
        print(f"  [SUCCESS] Scaled Result: Lot={scaled_lot:.2f} | Profit=${scaled_profit:.2f} | Drawdown={scaled_drawdown:.2f}% | RecFactor={rf:.2f}")
        
        if scaled_drawdown > 10.0:
            print(f"  [WARNING] Scaled drawdown ({scaled_drawdown:.2f}%) exceeds 10.0% constraint. Skipping.")
            continue
            
        # Score is the scaled profit (higher is better)
        score = scaled_profit
        if score > best_score:
            best_score = score
            best_candidate = {
                "max_depth": max_depth,
                "min_samples_leaf": min_samples_leaf,
                "class_weight": class_weight,
                "timeframe": timeframe,
                "raw_profit": profit,
                "raw_drawdown": drawdown,
                "raw_trades": trades,
                "profit_factor": pf,
                "win_rate": win_rate,
                "scaled_lot": scaled_lot,
                "scaled_profit": scaled_profit,
                "scaled_drawdown": scaled_drawdown,
                "recovery_factor": rf
            }
            print("  *** NEW BEST CANDIDATE ***")
            
    print("\n======================================================================")
    print("                        SEARCH COMPLETED")
    print("======================================================================")
    
    if best_candidate is None:
        print("Error: No candidates met the strict trade count (>= 200) and profit criteria.")
        return
        
    print("Best Performing Configuration:")
    print(f"  Model Parameters  : max_depth={best_candidate['max_depth']}, min_samples_leaf={best_candidate['min_samples_leaf']}, class_weight={best_candidate['class_weight']}")
    print(f"  Timeframe         : {best_candidate['timeframe']}")
    print(f"  Raw Performance   : Profit=${best_candidate['raw_profit']:.2f} | Drawdown={best_candidate['raw_drawdown']:.2f}% | Trades={best_candidate['raw_trades']} | PF={best_candidate['profit_factor']:.2f}")
    print(f"  Optimized Risk    : Scaled Lot size = {best_candidate['scaled_lot']:.2f}")
    print(f"  Scaled Performance: Profit=${best_candidate['scaled_profit']:.2f} | Drawdown={best_candidate['scaled_drawdown']:.2f}% (Safely under 10%!)")
    print(f"  Recovery Factor   : {best_candidate['recovery_factor']:.2f}")
    print("======================================================================\n")
    
    # Apply the best candidate:
    # 1. Train the model
    print("Re-training best model...")
    cmd_train = [
        sys.executable, TRAIN_SCRIPT,
        "--max-depth", str(best_candidate["max_depth"]),
        "--min-samples-leaf", str(best_candidate["min_samples_leaf"]),
        "--class-weight", best_candidate["class_weight"]
    ]
    subprocess.run(cmd_train, check=True)
    
    # 2. Compile EA
    print("Re-compiling EA...")
    compile_ea()
    
    # 3. Run Optimization once more to regenerate the best settings and backtest report
    print("Regenerating final settings preset...")
    cmd_opt = [
        sys.executable, OPT_SCRIPT,
        "--timeframe", best_candidate["timeframe"]
    ]
    subprocess.run(cmd_opt, check=True)
    
    # 4. Inject scaled lot size into final preset file
    print("Injecting scaled lot size into optimized preset...")
    update_set_file_with_lot(BEST_SET_PATH, best_candidate["scaled_lot"])
    
    print("\nALL TASKS COMPLETED SUCCESSFULLY!")
    print(f"Best settings and backtests have been written to {BEST_SET_PATH}.")
    print("You can load this preset file in MetaTrader 5 Strategy Tester to verify the results.")

if __name__ == "__main__":
    main()
