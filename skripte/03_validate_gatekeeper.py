import os
import sys
import json
import subprocess
import shutil

# Paths
workspace_dir = r"D:\AntiGravitySoftware\GitWorkspace\ToTheMoonKI"
jar_path = r"D:\AntiGravitySoftware\GitWorkspace\Backtester\target\mt5-backtester-1.2.6.jar"
json_config_path = os.path.join(workspace_dir, "skripte", "validation_config.json")
settings_dir = os.path.join(workspace_dir, "settings")
reports_dir = os.path.join(workspace_dir, "backtest_reports")
set_base_path = os.path.join(settings_dir, "temp_base.set")
set_onnx_path = os.path.join(settings_dir, "temp_onnx.set")
results_json_path = os.path.join(reports_dir, "batch_results.json")

# Core parameters matching the optimized AUDUSD setup
BASE_PARAMS = {
    "Inp_Magic": "123||0||0||0||N",
    "Inp_Order_Comment": "ToTheMoonKI-Opt-Best||0||0||0||N",
    "Inp_Spread_Max": "40.0||0||0||0||N",
    "Inp_Debug_Mode": "true||0||0||0||N",
    "Inp_Initial_Lot": "0.19||0||0||0||N",
    "Inp_Min_Lot": "0.19||0||0||0||N",
    "Inp_Max_Lot": "1.90||0||0||0||N",
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

def run_backtest_batch():
    # Remove previous results
    if os.path.exists(results_json_path):
        try:
            os.remove(results_json_path)
        except Exception as e:
            print(f"Could not remove old results: {e}")
            
    # Clear MT5 tester cache to prevent caching old resources
    cache_dir = r"C:\Forex\Mt5\TickmillLifeMql5\Tester\cache"
    if os.path.exists(cache_dir):
        for f in os.listdir(cache_dir):
            if f.lower().endswith(".tst") or f.lower().endswith(".xml"):
                try:
                    os.remove(os.path.join(cache_dir, f))
                except:
                    pass
                    
    print("Executing Java Backtester for validation runs...", flush=True)
    cmd = f'java -jar "{jar_path}" --cli "{json_config_path}"'
    process = subprocess.run(cmd, shell=True, cwd=workspace_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8")
    if process.returncode != 0:
        print("Java Backtester process failed!")
        print("Stdout:", process.stdout)
        print("Stderr:", process.stderr)
    return process.returncode == 0

def main():
    # Write set files
    params_base = BASE_PARAMS.copy()
    params_base["Inp_Use_ONNX_Gatekeeper"] = "false||0||0||0||N"
    params_base["Inp_Min_ONNX_Probability"] = "0.65||0||0||0||N"
    write_set_file(params_base, set_base_path)
    
    params_onnx = BASE_PARAMS.copy()
    params_onnx["Inp_Use_ONNX_Gatekeeper"] = "true||0||0||0||N"
    params_onnx["Inp_Min_ONNX_Probability"] = "0.58||0||0||0||N"
    write_set_file(params_onnx, set_onnx_path)
    
    # RUN 1: Base backtest (auto_kill_mt5 = True)
    config_base = {
        "output_directory": reports_dir,
        "settings": {
            "from_date": "2024-06-10",
            "to_date": "2026-06-10",
            "deposit": 10000,
            "currency": "USD",
            "leverage": "1:100",
            "model": 1,
            "use_virtual_desktop": False,
            "auto_kill_mt5": True
        },
        "runs": [
            {
                "expert_name": "ToTheMoonKI_Base",
                "expert_path": os.path.join(workspace_dir, "mql5_ea", "ToTheMoonKI.ex5"),
                "symbol": "AUDUSD",
                "period": "M5",
                "set_file_path": set_base_path
            }
        ]
    }
    
    with open(json_config_path, "w", encoding="utf-8") as f:
        json.dump(config_base, f, indent=2)
        
    print("Running Base backtest (No ONNX)...")
    success_base = run_backtest_batch()
    if not success_base or not os.path.exists(results_json_path):
        print("Error: Base validation run failed.")
        sys.exit(1)
        
    with open(results_json_path, "r", encoding="utf-8") as f:
        results_base = json.load(f)
    
    base_run = results_base.get("runs", [])[0]
    
    # RUN 2: ONNX backtest (auto_kill_mt5 = False, keeps MT5 open!)
    config_onnx = {
        "output_directory": reports_dir,
        "settings": {
            "from_date": "2024-06-10",
            "to_date": "2026-06-10",
            "deposit": 10000,
            "currency": "USD",
            "leverage": "1:100",
            "model": 1,
            "use_virtual_desktop": False,
            "auto_kill_mt5": False
        },
        "runs": [
            {
                "expert_name": "ToTheMoonKI_ONNX",
                "expert_path": os.path.join(workspace_dir, "mql5_ea", "ToTheMoonKI.ex5"),
                "symbol": "AUDUSD",
                "period": "M5",
                "set_file_path": set_onnx_path
            }
        ]
    }
    
    with open(json_config_path, "w", encoding="utf-8") as f:
        json.dump(config_onnx, f, indent=2)
        
    print("Running ONNX Gatekeeper backtest...")
    success_onnx = run_backtest_batch()
    if not success_onnx or not os.path.exists(results_json_path):
        print("Error: ONNX validation run failed.")
        sys.exit(1)
        
    with open(results_json_path, "r", encoding="utf-8") as f:
        results_onnx = json.load(f)
        
    onnx_run = results_onnx.get("runs", [])[0]
    
    # Extract metrics
    def get_metrics(run_data):
        return {
            "success": run_data.get("success", False),
            "profit": run_data.get("profit", 0.0),
            "trades": run_data.get("trades", 0),
            "drawdown": run_data.get("drawdown", 0.0),
            "profit_factor": run_data.get("profit_factor", 0.0),
            "recovery_factor": run_data.get("recovery_factor", 0.0),
            "error": run_data.get("error_message", "")
        }
        
    m_base = get_metrics(base_run)
    m_onnx = get_metrics(onnx_run)
    
    print("\n==================================================================")
    print("[ONNX] TO THE MOON EA - GATEKEEPER VALIDATION RESULTS (2-YEAR BACKTEST)")
    print("==================================================================")
    print(f"{'Metric':<25} | {'Base (No ONNX)':<18} | {'ONNX Gatekeeper':<18} | {'Change':<10}")
    print("-" * 80)
    
    metrics_to_print = [
        ("Net Profit ($)", "profit", "${:.2f}", True),
        ("Total Trades", "trades", "{:d}", False),
        ("Max Drawdown (%)", "drawdown", "{:.2f}%", True),
        ("Profit Factor", "profit_factor", "{:.2f}", True),
        ("Recovery Factor", "recovery_factor", "{:.2f}", True)
    ]
    
    comparison_md = []
    comparison_md.append("### TO THE MOON GATEKEEPER BACKTEST COMPARISON (2-YEAR)\n")
    comparison_md.append("| Metric | Base (No ONNX) | ONNX Gatekeeper | Change |")
    comparison_md.append("| :--- | :---: | :---: | :---: |")
    
    for label, key, fmt, is_higher_better in metrics_to_print:
        val_base = m_base[key]
        val_onnx = m_onnx[key]
        
        # Format values
        str_base = fmt.format(val_base)
        str_onnx = fmt.format(val_onnx)
        
        # Calculate change
        if val_base == 0:
            change_str = "N/A"
        else:
            diff_pct = ((val_onnx - val_base) / val_base) * 100.0
            change_str = f"{diff_pct:+.1f}%"
            
        print(f"{label:<25} | {str_base:>18} | {str_onnx:>18} | {change_str:>10}")
        comparison_md.append(f"| {label} | {str_base} | {str_onnx} | {change_str} |")
        
    print("==================================================================")
    
    # Save validation report markdown inside workspace and reports dir
    md_report_path = os.path.join(reports_dir, "validation_report.md")
    with open(md_report_path, "w", encoding="utf-8") as rf:
        rf.write("\n".join(comparison_md))
    print(f"Validation comparison report written to {md_report_path}")
    
if __name__ == "__main__":
    main()
