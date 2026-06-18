import os
import sys
import json
import subprocess

# Paths
workspace_dir = r"D:\AntiGravitySoftware\GitWorkspace\ToTheMoonKI"
jar_path = r"D:\AntiGravitySoftware\GitWorkspace\Backtester\target\mt5-backtester-1.2.6.jar"
json_config_path = os.path.join(workspace_dir, "skripte", "tuning_config.json")
settings_dir = os.path.join(workspace_dir, "settings")
reports_dir = os.path.join(workspace_dir, "backtest_reports")
results_json_path = os.path.join(reports_dir, "batch_results.json")

# Core parameters matching the optimized AUDUSD setup
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
        f.write("; validation parameters\n")
        for k, v in params.items():
            f.write(f"{k}={v}\n")

def main():
    # We will test thresholds from 0.50 to 0.64 in steps of 0.02
    thresholds = [0.50, 0.52, 0.54, 0.56, 0.58, 0.60, 0.62, 0.64]
    
    # Prepare runs configuration
    runs = []
    
    # 1. Base run (No ONNX)
    set_base_path = os.path.join(settings_dir, "temp_base.set")
    params_base = BASE_PARAMS.copy()
    params_base["Inp_Use_ONNX_Gatekeeper"] = "false||0||0||0||N"
    params_base["Inp_Min_ONNX_Probability"] = "0.65||0||0||0||N"
    write_set_file(params_base, set_base_path)
    
    runs.append({
        "expert_name": "Base_No_ONNX",
        "expert_path": os.path.join(workspace_dir, "mql5_ea", "ToTheMoonKI.ex5"),
        "symbol": "AUDUSD",
        "period": "M5",
        "set_file_path": set_base_path
    })
    
    # 2. ONNX runs with different thresholds
    for thresh in thresholds:
        set_onnx_path = os.path.join(settings_dir, f"temp_onnx_{int(thresh*100)}.set")
        params_onnx = BASE_PARAMS.copy()
        params_onnx["Inp_Use_ONNX_Gatekeeper"] = "true||0||0||0||N"
        params_onnx["Inp_Min_ONNX_Probability"] = f"{thresh:.2f}||0||0||0||N"
        write_set_file(params_onnx, set_onnx_path)
        
        runs.append({
            "expert_name": f"ONNX_{int(thresh*100)}",
            "expert_path": os.path.join(workspace_dir, "mql5_ea", "ToTheMoonKI.ex5"),
            "symbol": "AUDUSD",
            "period": "M5",
            "set_file_path": set_onnx_path
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
        
    print(f"Created tuning config with {len(runs)} runs.")
    
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
            
    print("Running backtests...")
    cmd = f'java -jar "{jar_path}" --cli "{json_config_path}"'
    process = subprocess.run(cmd, shell=True, cwd=workspace_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8")
    
    if process.returncode != 0 or not os.path.exists(results_json_path):
        print("Backtest run failed!")
        print("Stderr:", process.stderr)
        return
        
    with open(results_json_path, "r", encoding="utf-8") as f:
        results = json.load(f)
        
    runs_results = results.get("runs", [])
    
    print("\n==========================================================================================")
    print("ONNX GATEKEEPER THRESHOLD TUNING RESULTS (2-YEAR BACKTEST)")
    print("==========================================================================================")
    print(f"{'Run / Threshold':<20} | {'Profit ($)':<12} | {'Trades':<8} | {'Drawdown (%)':<14} | {'PF':<6} | {'Trades/Yr':<10}")
    print("-" * 85)
    
    for r in runs_results:
        name = r.get("expert_name", "")
        profit = r.get("profit", 0.0)
        trades = r.get("trades", 0)
        dd = r.get("drawdown", 0.0)
        pf = r.get("profit_factor", 0.0)
        trades_per_year = trades / 2.0
        print(f"{name:<20} | {profit:>12.2f} | {trades:>8d} | {dd:>13.2f}% | {pf:>6.2f} | {trades_per_year:>10.1f}")
        
    print("==========================================================================================")

if __name__ == "__main__":
    main()
