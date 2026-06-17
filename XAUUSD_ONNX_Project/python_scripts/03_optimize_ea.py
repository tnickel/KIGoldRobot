#!/usr/bin/env python3
"""
Phase 4: Automated Optimization & Walk-Forward Validation (03_optimize_ea.py)
----------------------------------------------------------------------------
This script automates the parameters search for our XAUUSD ONNX Expert Advisor.
It generates parameter search grids (.set), configures the Java Backtester, 
executes MT5 genetic optimizations in the In-Sample period, performs out-of-sample 
forward validation on the best candidates, and runs a final real-ticks verification.

It uses the mt5-backtester JAR tool located in the workspace structure.
"""

import os
import json
import subprocess
import shutil
import argparse
from datetime import datetime

# Configuration Paths (Dynamic relative paths based on project location)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE_DIR = BASE_DIR
SET_FILE_PATH = os.path.join(WORKSPACE_DIR, "temp_opt.set")
JSON_CONFIG_PATH = os.path.join(WORKSPACE_DIR, "python_scripts", "batch_opt_temp.json")

# Backtester Jar path (Relative to GitWorkspace directory)
# GitWorkspace is the parent of KIGoldRobot (two levels up from WORKSPACE_DIR)
GIT_WORKSPACE_DIR = os.path.dirname(os.path.dirname(WORKSPACE_DIR))
JAR_PATH = os.path.join(GIT_WORKSPACE_DIR, "Backtester", "target", "mt5-backtester-1.2.6.jar")
EX5_PATH = os.path.join(WORKSPACE_DIR, "mql5_ea", "XAU_ONNX_Bot.ex5")

# Standard MT5 tester model maps:
# 1 = 1 minute OHLC (Fast, great for coarse optimization)
# 4 = Every tick based on real ticks (High precision, for final validation)
MODEL_FAST = 1
MODEL_REAL_TICKS = 4

# Standard MT5 optimization maps:
# 0 = No optimization (standard backtest)
# 2 = Genetic algorithm optimization
OPTIMIZATION_GENETIC = 2
OPTIMIZATION_DISABLED = 0

def get_optimization_parameters():
    """
    Defines default values and search ranges for the XAUUSD ONNX Robot.
    Format: "Value||Start||Step||Stop||Y/N"
      - Y means optimized (search grid active)
      - N means fixed (non-optimized)
    """
    return {
        # Risk Settings
        "InpLotSize": "0.1||0||0||0||N",
        "InpUseDynamicRisk": "false||0||0||0||N",
        "InpRiskPercent": "1.0||0||0||0||N",
        "InpCommissionPerLot": "6.0||0||0||0||N",
        
        # Volatility Stops (Optimized ranges)
        "InpStopLossATRMultiplier": "2.0||1.0||0.2||3.0||Y",
        "InpTakeProfitATRMultiplier": "3.0||1.5||0.3||5.0||Y",
        
        # Model Execution Filters (Optimized range)
        "InpMinProbability": "0.55||0.50||0.05||0.75||Y",
        "InpCloseOnOppositeSignal": "true||0||0||0||N",
        
        # Safety Settings
        "InpMaxSpreadPoints": "50||0||0||0||N",
        "InpMagicNumber": "881209||0||0||0||N"
    }

def write_set_file(params, filepath):
    """Writes standard MT5 .set parameter configuration in UTF-16 format."""
    with open(filepath, "w", encoding="utf-16") as f:
        f.write("; saved by python batch optimizer for XAUUSD_ONNX\n")
        for k, v in params.items():
            f.write(f"{k}={v}\n")

def write_json_config(results_dir, from_date, to_date, model=MODEL_FAST, optimization=OPTIMIZATION_GENETIC):
    """Generates the runner JSON config for the Java backtester CLI."""
    config = {
        "output_directory": results_dir,
        "settings": {
            "from_date": from_date,
            "to_date": to_date,
            "deposit": 10000,
            "currency": "USD",
            "leverage": "1:100",
            "model": model,
            "optimization": optimization,
            "use_virtual_desktop": True,
            "auto_kill_mt5": True
        },
        "runs": [
            {
                "expert_name": "XAU_ONNX_Bot",
                "expert_path": EX5_PATH,
                "symbol": "XAUUSD",
                "period": "H1",
                "set_file_path": SET_FILE_PATH
            }
        ]
    }
    with open(JSON_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

def run_java_tool(results_json_path):
    """Clears MT5 tester cache and executes the Java backtester executable CLI."""
    # Remove previous results json
    if os.path.exists(results_json_path):
        try:
            os.remove(results_json_path)
        except:
            pass
            
    # Attempt to clear MT5 Tester cache (if in default/known directories)
    # This prevents MT5 from serving cached optimization results
    cache_dirs = [
        r"C:\Forex\Mt5\TickmillLifeMql5\Tester\cache",
        os.path.expandvars(r"%APPDATA%\MetaQuotes\Terminal\Common\Tester\cache")
    ]
    for cache_dir in cache_dirs:
        if os.path.exists(cache_dir):
            for f in os.listdir(cache_dir):
                if f.lower().endswith(".tst") or f.lower().endswith(".xml"):
                    try:
                        os.remove(os.path.join(cache_dir, f))
                    except:
                        pass

    print(f"Executing Java Backtester CLI wrapper...", flush=True)
    cmd = f'java -jar "{JAR_PATH}" --cli "{JSON_CONFIG_PATH}"'
    process = subprocess.run(cmd, shell=True, cwd=WORKSPACE_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8")
    return process

def calculate_fitness(profit, rf, trades, dd):
    """
    Calculates fitness score for optimization passes.
    Prioritizes high recovery factor, stable trade count, and penalizes high drawdowns (>10%).
    """
    # Strict drawdown penalty
    if dd > 10.0:
        penalty = 1000.0
    elif dd > 5.0:
        penalty = 10.0
    else:
        penalty = 1.0
        
    if profit <= 0 or trades < 10:  # Require at least 10 trades over 1-year period to avoid overfitted fluke trades
        return 0.0
        
    return (profit * rf * (trades ** 0.5)) / (((dd + 0.1) ** 2) * penalty)

def prepare_candidate_set_file(cand, target_set_path):
    """Creates a fixed .set file containing specific values from an optimization pass."""
    params_set = {}
    opt_params = get_optimization_parameters()
    for k, v in opt_params.items():
        parts = v.split("||")
        pname = k
        if pname in cand["params"]:
            params_set[pname] = f"{cand['params'][pname]}||0||0||0||N"
        else:
            params_set[pname] = f"{parts[0]}||0||0||0||N"
    write_set_file(params_set, target_set_path)

def main():
    parser = argparse.ArgumentParser(description="Walk-Forward Optimization for Gold ONNX Robot")
    parser.add_argument("--is-start", type=str, default="2024-06-01", help="In-Sample start date (YYYY-MM-DD)")
    parser.add_argument("--is-end", type=str, default="2025-06-01", help="In-Sample end date (YYYY-MM-DD)")
    parser.add_argument("--oos-start", type=str, default="2025-06-01", help="Out-of-Sample start date (YYYY-MM-DD)")
    parser.add_argument("--oos-end", type=str, default="2026-06-01", help="Out-of-Sample end date (YYYY-MM-DD)")
    args = parser.parse_args()
    
    print("\n=======================================================")
    print("STARTING WALK-FORWARD OPTIMIZATION: XAUUSD H1 ONNX BOT")
    print("=======================================================")
    
    # Verify paths
    if not os.path.exists(JAR_PATH):
        print(f"Error: Java backtester JAR not found at {JAR_PATH}.")
        print("Please check the path mapping of the Backtester repository.")
        return
        
    if not os.path.exists(EX5_PATH):
        print(f"Error: Expert Advisor ex5 not found at {EX5_PATH}.")
        print("Please compile XAU_ONNX_Bot.mq5 in MT5 MetaEditor first to generate the ex5 file.")
        return
        
    results_dir = os.path.join(WORKSPACE_DIR, "backtest_reports", "xauusd_onnx_opt")
    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(os.path.join(WORKSPACE_DIR, "settings"), exist_ok=True)
    
    results_json_path = os.path.join(results_dir, "batch_results.json")
    
    print(f"In-Sample Optimization Period : {args.is_start} to {args.is_end}")
    print(f"Out-of-Sample Forward Period  : {args.oos_start} to {args.oos_end}")
    
    # 1. Create optimization configuration
    opt_params = get_optimization_parameters()
    write_set_file(opt_params, SET_FILE_PATH)
    write_json_config(results_dir, args.is_start, args.is_end, model=MODEL_FAST, optimization=OPTIMIZATION_GENETIC)
    
    # 2. Run In-Sample optimization
    print("\nLaunching In-Sample Genetic Search (1-minute OHLC mode for speed)...")
    run_java_tool(results_json_path)
    
    if not os.path.exists(results_json_path):
        print("Error: No batch_results.json generated by the Java Backtester!")
        return
        
    with open(results_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    run_res = data["runs"][0]
    passes = run_res.get("optimization_passes", [])
    
    if not passes:
        print(f"Error: No optimization passes found in result. Error: {run_res.get('error_message')}")
        return
        
    print(f"In-Sample Search complete. Evaluated {len(passes)} parameter configurations.")
    
    # 3. Score and rank candidates based on fitness
    evaluated_passes = []
    for idx, ps in enumerate(passes):
        profit = ps.get("profit", 0.0)
        trades = ps.get("totalTrades", 0)
        dd = ps.get("drawdownPercent", 0.0)
        rf = ps.get("recoveryFactor", 0.0)
        params = ps.get("parameterValues", {})
        pass_num = ps.get("passNumber", idx)
        
        fit = calculate_fitness(profit, rf, trades, dd)
        evaluated_passes.append({
            "pass_num": pass_num,
            "profit": profit,
            "trades": trades,
            "drawdown": dd,
            "recovery_factor": rf,
            "fitness": fit,
            "params": params
        })
        
    evaluated_passes.sort(key=lambda x: x["fitness"], reverse=True)
    
    # 4. Out-of-Sample Forward Validation on top 5 candidates
    num_candidates = min(5, len(evaluated_passes))
    candidates = evaluated_passes[:num_candidates]
    
    print(f"\nEvaluating Top {num_candidates} Candidates on Out-of-Sample Forward Period...")
    
    for rank, cand in enumerate(candidates):
        print(f"  Candidate Rank {rank+1} (Pass {cand['pass_num']} | IS Profit: ${cand['profit']:.2f} | IS Drawdown: {cand['drawdown']:.2f}%)")
        prepare_candidate_set_file(cand, SET_FILE_PATH)
        
        # Run standard backtest in OOS period (no optimization)
        write_json_config(results_dir, args.oos_start, args.oos_end, model=MODEL_FAST, optimization=OPTIMIZATION_DISABLED)
        run_java_tool(results_json_path)
        
        if not os.path.exists(results_json_path):
            print(f"    Error: Forward test run failed for Pass {cand['pass_num']}")
            cand["oos_success"] = False
            continue
            
        with open(results_json_path, "r", encoding="utf-8") as f:
            oos_data = json.load(f)
            
        oos_run = oos_data["runs"][0]
        if oos_run.get("success"):
            cand["oos_success"] = True
            cand["oos_profit"] = oos_run.get("profit", 0.0)
            cand["oos_trades"] = oos_run.get("trades", 0)
            cand["oos_drawdown"] = oos_run.get("drawdown", 0.0)
            cand["oos_profit_factor"] = oos_run.get("profit_factor", 0.0)
            print(f"    OOS Result -> Profit: ${cand['oos_profit']:.2f} | Drawdown: {cand['oos_drawdown']:.2f}% | Trades: {cand['oos_trades']} | PF: {cand['oos_profit_factor']:.2f}")
        else:
            cand["oos_success"] = False
            print(f"    OOS run failed: {oos_run.get('error_message')}")
            
    # Filter candidates that succeeded forward test
    valid_candidates = [c for c in candidates if c.get("oos_success", False)]
    if not valid_candidates:
        print("\nError: No candidates completed OOS forward tests successfully!")
        return
        
    # Select best candidate: OOS Drawdown <= 10.0%, sorted by profit
    selectable = [c for c in valid_candidates if c["oos_drawdown"] <= 10.0 and c["oos_profit"] > 0]
    if not selectable:
        print("\nWarning: No candidates met strict criteria (OOS Drawdown <= 10.0% and positive profit). Selecting by lowest OOS drawdown.")
        selectable = sorted(valid_candidates, key=lambda x: x["oos_drawdown"])
        best_cand = selectable[0]
    else:
        selectable.sort(key=lambda x: x["oos_profit"], reverse=True)
        best_cand = selectable[0]
        
    print(f"\nBest Walk-Forward Candidate: Pass {best_cand['pass_num']}")
    print(f"  In-Sample Fitness: {best_cand['fitness']:.2f}")
    print(f"  OOS Drawdown:       {best_cand['oos_drawdown']:.2f}%")
    print(f"  OOS Profit:         ${best_cand['oos_profit']:.2f}")
    
    # 5. Save best settings to settings folder
    best_set_path = os.path.join(WORKSPACE_DIR, "settings", "optimized_xauusd_best.set")
    with open(best_set_path, "w", encoding="utf-16") as sf:
        sf.write(f"; Best Settings for XAUUSD H1 (OOS Drawdown: {best_cand['oos_drawdown']:.2f}%)\n")
        for k, v in best_cand["params"].items():
            sf.write(f"{k}={v}\n")
    print(f"\nSaved best parameters preset to: {best_set_path}")
    
    # 6. Execute Final 2-Year Verification (Full tick-by-tick based on real ticks)
    print("\nRunning Final 2-Year Real-Ticks Verification Backtest...")
    prepare_candidate_set_file(best_cand, SET_FILE_PATH)
    write_json_config(results_dir, args.is_start, args.oos_end, model=MODEL_REAL_TICKS, optimization=OPTIMIZATION_DISABLED)
    run_java_tool(results_json_path)
    
    if not os.path.exists(results_json_path):
        print("Error: Final verification run failed to write results JSON!")
        return
        
    with open(results_json_path, "r", encoding="utf-8") as f:
        verify_data = json.load(f)
        
    v_run = verify_data["runs"][0]
    if v_run.get("success"):
        print(f"\n=== VERIFICATION BACKTEST COMPLETED SUCCESSFULLY ===")
        print(f"  Evaluation Period: {args.is_start} to {args.oos_end}")
        print(f"  Net Profit:        ${v_run.get('profit', 0.0):.2f}")
        print(f"  Total Trades:      {v_run.get('trades', 0)}")
        print(f"  Max Drawdown:      {v_run.get('drawdown', 0.0):.2f}%")
        print(f"  Profit Factor:     {v_run.get('profit_factor', 0.0):.2f}")
        print(f"=====================================================")
    else:
        print(f"Verification run failed: {v_run.get('error_message')}")
        
    # Clean up temp file
    if os.path.exists(SET_FILE_PATH):
        try:
            os.remove(SET_FILE_PATH)
        except:
            pass

if __name__ == "__main__":
    main()
