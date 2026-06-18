import os
import sys
import json
import subprocess

# Paths
workspace_dir = r"D:\AntiGravitySoftware\GitWorkspace\ToTheMoonKI"
jar_path = r"D:\AntiGravitySoftware\GitWorkspace\Backtester\target\mt5-backtester-1.2.6.jar"
json_config_path = os.path.join(workspace_dir, "skripte", "opt_grid_config.json")
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
        f.write("; optimization parameters\n")
        for k, v in params.items():
            f.write(f"{k}={v}\n")

def main():
    # Optimization Grid
    onnx_probs = [0.50, 0.52, 0.54, 0.56, 0.58, 0.60]
    grid_steps = [800, 1000]
    step_multipliers = [1.33, 1.40]
    
    runs = []
    
    # Generate all parameter combinations
    for prob in onnx_probs:
        for step in grid_steps:
            for mult in step_multipliers:
                run_name = f"P{int(prob*100)}_S{step}_M{int(mult*100)}"
                set_path = os.path.join(settings_dir, f"temp_{run_name}.set")
                
                params = BASE_PARAMS.copy()
                params["Inp_Use_ONNX_Gatekeeper"] = "true||0||0||0||N"
                params["Inp_Min_ONNX_Probability"] = f"{prob:.2f}||0||0||0||N"
                params["Inp_Grid_Step"] = f"{step}||0||0||0||N"
                params["Inp_Step_Multiplier"] = f"{mult:.2f}||0||0||0||N"
                
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
            "from_date": "2025-01-01",
            "to_date": "2025-12-31",
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
        
    print(f"Generated optimization config with {len(runs)} runs.")
    
    # Clear cache
    cache_dir = r"C:\Forex\Mt5\TickmillLifeMql5\Tester\cache"
    if os.path.exists(cache_dir):
        for f_name in os.listdir(cache_dir):
            if f_name.lower().endswith(".tst") or f_name.lower().endswith(".xml"):
                try:
                    os.remove(os.path.join(cache_dir, f_name))
                except:
                    pass
                    
    # Remove old results
    if os.path.exists(results_json_path):
        try:
            os.remove(results_json_path)
        except Exception as e:
            print(f"Could not remove old results: {e}")
            
    print("Running optimization batch in backtester...")
    cmd = f'java -jar "{jar_path}" --cli "{json_config_path}"'
    process = subprocess.run(cmd, shell=True, cwd=workspace_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8")
    
    if process.returncode != 0 or not os.path.exists(results_json_path):
        print("Optimization batch failed!")
        print("Stderr:", process.stderr)
        return
        
    with open(results_json_path, "r", encoding="utf-8") as f:
        results = json.load(f)
        
    runs_results = results.get("runs", [])
    
    print("\n" + "="*110)
    print("GRID OPTIMIZATION RESULTS - TARGET DRAWDOWN < 10% (RISK SCALED)")
    print("="*110)
    print(f"{'Run Config':<20} | {'Raw Profit':<10} | {'Raw DD':<8} | {'Trades':<6} | {'Trades/Yr':<9} | {'Scale':<6} | {'Scaled Profit':<13} | {'Scaled DD':<9} | {'New PresetFactor':<16}")
    print("-" * 110)
    
    valid_candidates = []
    
    for r in runs_results:
        name = r.get("expert_name", "")
        raw_profit = r.get("profit", 0.0)
        raw_dd = r.get("drawdown", 0.0)
        trades = r.get("trades", 0)
        trades_per_year = trades / 1.0
        
        # Calculate scaling factor to bring DD strictly under 9.5%
        # Standard initial lot is 0.01 with Preset Factor 1200.
        # Drawdown scales proportionally to lot size.
        # Scale = 9.5 / raw_dd
        if raw_dd > 0:
            scale = 9.5 / raw_dd
            if scale > 1.0:
                scale = 1.0  # Do not scale up to avoid exceeding initial lot rules
        else:
            scale = 1.0
            
        scaled_profit = raw_profit * scale
        scaled_dd = raw_dd * scale
        new_preset_factor = 1200.0 / scale
        
        # Filter: Must meet at least 100 trades per year
        is_valid = trades_per_year >= 100.0
        
        if is_valid:
            valid_candidates.append({
                "name": name,
                "raw_profit": raw_profit,
                "raw_dd": raw_dd,
                "trades": trades,
                "trades_per_year": trades_per_year,
                "scale": scale,
                "scaled_profit": scaled_profit,
                "scaled_dd": scaled_dd,
                "new_preset_factor": new_preset_factor
            })
            
        print(f"{name:<20} | {raw_profit:>10.2f} | {raw_dd:>7.2f}% | {trades:>6d} | {trades_per_year:>9.1f} | {scale:>6.3f} | {scaled_profit:>13.2f} | {scaled_dd:>8.2f}% | {new_preset_factor:>16.1f} {'*' if is_valid else ''}")
        
    print("="*110)
    print("* indicates valid candidate (Trades/Yr >= 100)")
    
    if len(valid_candidates) == 0:
        print("\nNo candidates found that met the Trades/Yr >= 100 constraint!")
        return
        
    # Sort by scaled profit descending
    valid_candidates.sort(key=lambda x: x["scaled_profit"], reverse=True)
    best = valid_candidates[0]
    
    print("\n" + "="*60)
    print("BEST SCALED CONFIGURATION FOUND:")
    print("="*60)
    print(f"Configuration:        {best['name']}")
    print(f"Raw Drawdown:         {best['raw_dd']:.2f}%")
    print(f"Raw Profit:           ${best['raw_profit']:.2f}")
    print(f"Trades per Year:      {best['trades_per_year']:.1f}")
    print(f"Scaling Factor:       {best['scale']:.4f}")
    print(f"Scaled Profit (2yr):  ${best['scaled_profit']:.2f}")
    print(f"Scaled Drawdown:      {best['scaled_dd']:.2f}%")
    print(f"Recommended PresetFactor: {best['new_preset_factor']:.1f} (use this instead of 1200.0)")
    print("="*60)
    
if __name__ == "__main__":
    main()
