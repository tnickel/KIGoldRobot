import os
import sys
import json
import subprocess

# Paths
workspace_dir = r"D:\AntiGravitySoftware\GitWorkspace\ToTheMoonKI"
jar_path = r"D:\AntiGravitySoftware\GitWorkspace\Backtester\target\mt5-backtester-1.2.6.jar"
json_config_path = os.path.join(workspace_dir, "skripte", "low_dd_config.json")
settings_dir = os.path.join(workspace_dir, "settings")
reports_dir = os.path.join(workspace_dir, "backtest_reports")
results_json_path = os.path.join(reports_dir, "batch_results.json")

# Base params
BASE_PARAMS = {
    "Inp_Magic": "123||0||0||0||N",
    "Inp_Order_Comment": "ToTheMoonKI-Opt-Best||0||0||0||N",
    "Inp_Spread_Max": "40.0||0||0||0||N",
    "Inp_Debug_Mode": "true||0||0||0||N",
    "Inp_Initial_Lot": "0.01||0||0||0||N",
    "Inp_Min_Lot": "0.01||0||0||0||N",
    "Inp_Max_Lot": "0.1||0||0||0||N",
    "Inp_Preset_Factor": "1200.0||0||0||0||N",
    "Inp_Grid_Step": "1000||0||0||0||N",
    "Inp_Step_Multiplier": "1.33||0||0||0||N",
    "Inp_Next_Lot_Multiplier": "1.38||0||0||0||N",
    "Inp_TakeProfit": "50||0||0||0||N",
    "Min_Profit": "5.0||0||0||0||N",
    "Inp_Wait_Open_Equal_Orders": "30||0||0||0||N",
    "Inp_Wait_Next_Lot": "600||0||0||0||N",
    "Inp_Start_Wait_Next_Lot": "1||0||0||0||N",
    "Inp_Stop_Wait_Next_Lot": "100||0||0||0||N",
    "TimeFrame_Envelopes": "16385||0||0||0||N",  # H1
    "Inp_Envelopes_Period": "14||0||0||0||N",
    "Envelopes_Method": "1||0||0||0||N",
    "Envelopes_Price": "1||0||0||0||N",
    "Inp_Envelopes_Deviation": "0.133||0||0||0||N",
    "Values_Envelopes_Lower": "1||0||0||0||N",
    "TimeFrame_Envelopes_Lower": "16385||0||0||0||N",  # H1
    "Inp_Envelopes_Period_Lower": "20||0||0||0||N",
    "Envelopes_Method_Lower": "1||0||0||0||N",
    "Envelopes_Price_Lower": "4||0||0||0||N",
    "Inp_Envelopes_Deviation_Lower": "0.299||0||0||0||N",
    "Inp_Use_Trend_Filter": "true||0||0||0||N",
    "Inp_Trend_EMA_Period": "250||0||0||0||N",
    "Inp_Use_RSI_Filter": "false||0||0||0||N",
    "Inp_RSI_Period": "21||0||0||0||N",
    "Inp_RSI_Oversold": "23.6||0||0||0||N",
    "Inp_RSI_Overbought": "69.7||0||0||0||N",
    "Inp_Use_ADX_Filter": "false||0||0||0||N",
    "Inp_ADX_Period": "14||0||0||0||N",
    "Inp_ADX_Timeframe": "16385||0||0||0||N",
    "Inp_ADX_Max_Level": "30.0||0||0||0||N",
    "Inp_Use_ER_Filter": "false||0||0||0||N",
    "Inp_ER_Period": "10||0||0||0||N",
    "Inp_ER_Timeframe": "16385||0||0||0||N",
    "Inp_ER_Max_Level": "0.30||0||0||0||N",
    "Inp_Use_ATR_Step": "false||0||0||0||N",
    "Inp_ATR_Period": "10||0||0||0||N",
    "Inp_ATR_Timeframe": "15||0||0||0||N",
    "Inp_ATR_Multiplier": "1.5||0||0||0||N",
    "Inp_Use_BreakEven": "false||0||0||0||N",
    "Inp_BE_Trigger_Points": "150||0||0||0||N",
    "Inp_BE_Points": "30||0||0||0||N",
    "Inp_Max_Grid_Levels": "12||0||0||0||N",
    "Inp_Max_DD_Percent": "30.0||0||0||0||N",
    "Inp_Halt_After_DD_Stop": "false||0||0||0||N",
    "Inp_Use_Vol_Filter": "false||0||0||0||N",
    "Inp_Vol_ATR_Period": "10||0||0||0||N",
    "Inp_Vol_ATR_Timeframe": "15||0||0||0||N",
    "Inp_Vol_ATR_Max_Multiplier": "2.0||0||0||0||N",
    "Inp_Use_Correlation_Filter": "false||0||0||0||N"
}

def write_set_file(params, filepath):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-16") as f:
        f.write("; low dd optimization parameters\n")
        for k, v in params.items():
            f.write(f"{k}={v}\n")

def main():
    # Targeted low drawdown search space (36 combinations)
    onnx_probs = [0.50, 0.52, 0.54]           # 3 values (higher probability = lower raw DD)
    grid_steps = [750, 850]                  # 2 values
    lot_multipliers = [1.32, 1.36]           # 2 values
    take_profits = [45, 50, 55]              # 3 values
    
    runs = []
    
    for prob in onnx_probs:
        for step in grid_steps:
            for lot_mult in lot_multipliers:
                for tp in take_profits:
                    run_name = f"P{int(prob*100)}_S{step}_L{int(lot_mult*100)}_T{tp}"
                    set_path = os.path.join(settings_dir, f"temp_{run_name}.set")
                    
                    params = BASE_PARAMS.copy()
                    params["Inp_Use_ONNX_Gatekeeper"] = "true||0||0||0||N"
                    params["Inp_Min_ONNX_Probability"] = f"{prob:.2f}||0||0||0||N"
                    params["Inp_Grid_Step"] = f"{step}||0||0||0||N"
                    params["Inp_Next_Lot_Multiplier"] = f"{lot_mult:.2f}||0||0||0||N"
                    params["Inp_TakeProfit"] = f"{tp}||0||0||0||N"
                    # Keep Preset Factor at 1200 to test raw drawdown safety
                    params["Inp_Preset_Factor"] = "1200.0||0||0||0||N"
                    
                    write_set_file(params, set_path)
                    
                    runs.append({
                        "expert_name": run_name,
                        "expert_path": os.path.join(workspace_dir, "mql5_ea", "ToTheMoonKI.ex5"),
                        "symbol": "AUDUSD",
                        "period": "M5",
                        "set_file_path": set_path
                    })
                    
    config = {
        "output_directory": reports_dir,
        "settings": {
            "from_date": "2024-06-10",
            "to_date": "2026-06-10",
            "deposit": 10000,
            "currency": "USD",
            "leverage": "1:100",
            "model": 1,
            "use_virtual_desktop": True,
            "auto_kill_mt5": True
        },
        "runs": runs
    }
    
    with open(json_config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
        
    print(f"Generated low DD config with {len(runs)} runs.")
    
    # Clear cache
    cache_dir = r"C:\Forex\Mt5\TickmillLifeMql5\Tester\cache"
    if os.path.exists(cache_dir):
        for f in os.listdir(cache_dir):
            if f.lower().endswith(".tst") or f.lower().endswith(".xml"):
                try:
                    os.remove(os.path.join(cache_dir, f))
                except:
                    pass
                    
    # Remove old results
    if os.path.exists(results_json_path):
        try:
            os.remove(results_json_path)
        except Exception as e:
            print(f"Could not remove old results: {e}")
            
    print("Running low DD batch in strategy tester...")
    cmd = f'java -jar "{jar_path}" --cli "{json_config_path}"'
    process = subprocess.run(cmd, shell=True, cwd=workspace_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8")
    
    if process.returncode != 0 or not os.path.exists(results_json_path):
        print("Low DD optimization batch failed!")
        print("Stderr:", process.stderr)
        return
        
    with open(results_json_path, "r", encoding="utf-8") as f:
        results = json.load(f)
        
    runs_results = results.get("runs", [])
    
    valid_candidates = []
    
    for r in runs_results:
        name = r.get("expert_name", "")
        raw_profit = r.get("profit", 0.0)
        raw_dd = r.get("drawdown", 0.0)
        trades = r.get("trades", 0)
        trades_per_year = trades / 2.0
        
        # Scale only to keep drawdown strictly under 9.5%
        # Prefer scale >= 0.8 (Preset Factor <= 1500) to avoid martingale capping issues!
        if raw_dd > 0:
            scale = 9.5 / raw_dd
            if scale > 1.0:
                scale = 1.0
        else:
            scale = 1.0
            
        scaled_profit = raw_profit * scale
        scaled_dd = raw_dd * scale
        new_preset_factor = 1200.0 / scale
        
        # Criteria: Trades/Yr >= 100 AND scale >= 0.8 (to prevent martingale degradation)
        is_valid = (trades_per_year >= 100.0)
        is_safe_scale = (scale >= 0.80)
        
        valid_candidates.append({
            "name": name,
            "raw_profit": raw_profit,
            "raw_dd": raw_dd,
            "trades": trades,
            "trades_per_year": trades_per_year,
            "scale": scale,
            "scaled_profit": scaled_profit,
            "scaled_dd": scaled_dd,
            "new_preset_factor": new_preset_factor,
            "is_safe_scale": is_safe_scale,
            "is_valid": is_valid
        })
            
    if len(valid_candidates) == 0:
        print("\nNo runs completed or results found!")
        return
        
    # Sort valid candidates by scaled profit descending
    # Prioritize candidates with safe scale (scale >= 0.80) first!
    safe_candidates = [c for c in valid_candidates if c["is_safe_scale"] and c["is_valid"]]
    
    print("\n" + "="*130)
    print("ALL GRID OPTIMIZATION RUN RESULTS")
    print("="*130)
    print(f"{'Run Config':<22} | {'Raw Profit':<10} | {'Raw DD':<8} | {'Trades/Yr':<9} | {'Scale':<6} | {'Scaled Profit':<13} | {'Scaled DD':<9} | {'New PresetFactor':<16} | {'Status'}")
    print("-" * 130)
    
    # Sort all candidates by scaled profit just to show them ranked
    valid_candidates.sort(key=lambda x: x["scaled_profit"], reverse=True)
    for c in valid_candidates:
        status_parts = []
        if c["is_valid"]: status_parts.append("Trades OK")
        else: status_parts.append(f"LOW TRADES ({c['trades_per_year']:.1f}/yr)")
        if c["is_safe_scale"]: status_parts.append("Scale OK")
        else: status_parts.append("RISKY SCALE")
        
        status_str = ", ".join(status_parts)
        print(f"{c['name']:<22} | {c['raw_profit']:>10.2f} | {c['raw_dd']:>7.2f}% | {c['trades_per_year']:>9.1f} | {c['scale']:>6.3f} | {c['scaled_profit']:>13.2f} | {c['scaled_dd']:>8.2f}% | {c['new_preset_factor']:>16.1f} | {status_str}")
        
    print("="*130)
    
    if len(safe_candidates) > 0:
        safe_candidates.sort(key=lambda x: x["scaled_profit"], reverse=True)
        best = safe_candidates[0]
        print(f"\nBest Safe & Valid Candidate (Trades >= 100 & Scale >= 0.80): {best['name']}")
        print(f"Recommended PresetFactor: {best['new_preset_factor']:.1f}")
    else:
        best_overall = [c for c in valid_candidates if c["is_valid"]]
        if len(best_overall) > 0:
            best_overall.sort(key=lambda x: x["scaled_profit"], reverse=True)
            print(f"\nWarning: No candidate met the scale >= 0.80 safety limit. Best valid overall: {best_overall[0]['name']}")
            print(f"Recommended PresetFactor: {best_overall[0]['new_preset_factor']:.1f}")
        else:
            print("\nWarning: No candidates met the Trades/Yr >= 100 limit at all in this run!")

if __name__ == "__main__":
    main()
