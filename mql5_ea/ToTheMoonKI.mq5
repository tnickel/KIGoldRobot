//+------------------------------------------------------------------+
//|                                                   ToTheMoonKI.mq5   |
//|                                  Copyright 2026, Thomas Nickel   |
//|                               https://www.mql5.com/de/signals/2262642 |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Thomas Nickel"
#property link      "https://www.mql5.com/de/signals/2262642"
#property version   "1.04"
#property strict

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>

#resource "\\exports\\gatekeeper.onnx" as uchar gatekeeper_data[]

// Struct for position tracking
struct GridPosition
{
   ulong ticket;
   double volume;
   double profit;
   double entry_price;
   ulong open_time_msc;  // POSITION_TIME_MSC, for robust oldest/newest ordering
   double commission;    // opening commission, used to estimate the not-yet-charged close cost
};

// --- Inputs
input group "---- INITIAL DATA ----"
input string   Inp_Order_Comment = "ToTheMoonKI-Opt-Best"; // Order Comment
input double   Inp_Spread_Max = 40.0;           // Max Spread allowed (points)
input bool     Inp_Debug_Mode = false;          // Enable Debug Logging
input int      Inp_Dashboard_Font_Size = 11;    // Dashboard Font Size
input int      Inp_Envelope_Width = 2;          // Envelope Line Width

input group "---- MONEY MANAGE ----"
input double   Inp_Initial_Lot = 0.01;          // Base Lot Size
input double   Inp_Min_Lot = 0.01;              // Minimum Lot Size
input double   Inp_Max_Lot = 0.1;               // Maximum Lot Size
input double   Inp_Preset_Factor = 1200.0;      // Balance Divider for Lot Scaling

input group "---- GRID MODE ----"
input int      Inp_Grid_Step = 1000;            // Base Grid Step (points)
input double   Inp_Step_Multiplier = 1.33;      // Step Multiplier
input double   Inp_Next_Lot_Multiplier = 1.38;  // Martingale Lot Multiplier
input int      Inp_TakeProfit = 50;            // Basket TP target (points)
input double   Min_Profit = 5.0;                // Pair Close Target profit (USD)
input int      Inp_Wait_Open_Equal_Orders = 30; // Wait to Open Equal Orders (minutes)
input int      Inp_Wait_Next_Lot = 600;         // Wait Next Lot Grid (minutes)
input int      Inp_Start_Wait_Next_Lot = 1;     // Start Wait Next Lot Grid (level)
input int      Inp_Stop_Wait_Next_Lot = 100;    // Stop Wait Next Lot Grid (level)

input group "---- INDICATOR ENVELOPES (UPPER) ----"
input ENUM_TIMEFRAMES TimeFrame_Envelopes = PERIOD_H1; // Upper Timeframe
input int      Inp_Envelopes_Period = 14;       // Upper Period
input ENUM_MA_METHOD Envelopes_Method = MODE_EMA; // Upper Method
input ENUM_APPLIED_PRICE Envelopes_Price = PRICE_CLOSE; // Upper Applied Price
input double   Inp_Envelopes_Deviation = 0.133; // Upper Deviation (%)

input group "---- INDICATOR ENVELOPES (LOWER) ----"
input int      Values_Envelopes_Lower = 1;      // Values Envelopes Lower (0: Same as Upper, 1: Custom)
input ENUM_TIMEFRAMES TimeFrame_Envelopes_Lower = PERIOD_H1; // Lower Timeframe
input int      Inp_Envelopes_Period_Lower = 20; // Lower Period
input ENUM_MA_METHOD Envelopes_Method_Lower = MODE_EMA; // Lower Method
input ENUM_APPLIED_PRICE Envelopes_Price_Lower = PRICE_LOW; // Lower Applied Price
input double   Inp_Envelopes_Deviation_Lower = 0.299; // Lower Deviation (%)


input group "---- TREND FILTER ----"
input bool     Inp_Use_Trend_Filter = true;       // Use H4 Trend Filter (EMA)
input int      Inp_Trend_EMA_Period = 250;         // Trend EMA Period

input group "---- RSI FILTER ----"
input bool     Inp_Use_RSI_Filter   = false;       // Use RSI Entry Filter
input int      Inp_RSI_Period       = 21;          // RSI Period
input double   Inp_RSI_Oversold     = 23.6;        // RSI Oversold Level
input double   Inp_RSI_Overbought   = 69.7;        // RSI Overbought Level

input group "---- ADX REGIME FILTER ----"
input bool            Inp_Use_ADX_Filter   = false;        // Use ADX Trend-Strength Filter (first entry only)
input int             Inp_ADX_Period       = 14;           // ADX Period
input ENUM_TIMEFRAMES Inp_ADX_Timeframe    = PERIOD_H1;     // ADX Timeframe
input double          Inp_ADX_Max_Level    = 30.0;         // Block first entry if ADX >= this (strong trend)

input group "---- EFFICIENCY RATIO FILTER ----"
input bool            Inp_Use_ER_Filter    = false;        // Use Kaufman Efficiency Ratio Filter (first entry only)
input int             Inp_ER_Period        = 10;           // Efficiency Ratio Period (bars)
input ENUM_TIMEFRAMES Inp_ER_Timeframe     = PERIOD_H1;     // Efficiency Ratio Timeframe
input double          Inp_ER_Max_Level     = 0.30;         // Block first entry if ER >= this (0..1, higher = trending)

input group "---- DYNAMIC GRID STEPS ----"
input bool     Inp_Use_ATR_Step     = false;       // Use ATR-based dynamic steps
input int      Inp_ATR_Period       = 10;          // ATR Period
input ENUM_TIMEFRAMES Inp_ATR_Timeframe = PERIOD_M15; // ATR Timeframe
input double   Inp_ATR_Multiplier   = 1.5;         // ATR Multiplier for base step

input group "---- BREAK EVEN ----"
input bool     Inp_Use_BreakEven    = false;       // Use Break Even
input int      Inp_BE_Trigger_Points= 150;         // Break Even Trigger (points)
input int      Inp_BE_Points        = 30;          // Break Even Profit (points)

input group "---- RISK PROTECTION ----"
input int      Inp_Max_Grid_Levels    = 12;    // Max Grid Levels per direction (0 = unlimited)
input double   Inp_Max_DD_Percent      = 30.0;  // Emergency close if floating loss >= % of balance (0 = off)
input bool     Inp_Halt_After_DD_Stop  = false; // After DD stop: halt NEW entries until EA restart

input group "---- ONNX GATEKEEPER ----"
input bool     Inp_Use_ONNX_Gatekeeper   = true;  // Use ONNX Entry Gatekeeper (first entry only)
input double   Inp_Min_ONNX_Probability  = 0.58;  // Min Probability for Class 1 (Safe)

input group "---- VOLATILITY FILTER ----"
input bool            Inp_Use_Vol_Filter        = false;          // Use Volatility/ATR filter for Grid-Adds
input int             Inp_Vol_ATR_Period        = 10;             // Volatility ATR Period
input ENUM_TIMEFRAMES Inp_Vol_ATR_Timeframe     = PERIOD_M15;     // Volatility ATR Timeframe
input double          Inp_Vol_ATR_Max_Multiplier= 2.0;            // Block adds if current ATR > Average ATR * this

input group "---- CORRELATION FILTER ----"
input bool     Inp_Use_Correlation_Filter = true;  // Block first entry if a correlated pair (shared currency) has open ToTheMoonKI trades

void DrawEnvelopeLines(bool force_redraw);
uint GetSymbolHash(string sym);
bool IsAlreadyRunning();

// --- Globals
CTrade trade;
CPositionInfo pos_info;

ulong calculated_magic = 0;

int handle_up = INVALID_HANDLE;
int handle_down = INVALID_HANDLE;

int handle_trend = INVALID_HANDLE;
int handle_rsi = INVALID_HANDLE;
int handle_atr = INVALID_HANDLE;
int handle_vol_atr = INVALID_HANDLE;
int handle_adx = INVALID_HANDLE;

// --- Dedicated handles for ONNX features (decoupled from user inputs)
int onnx_handle_trend_h4 = INVALID_HANDLE;
int onnx_handle_rsi_m15 = INVALID_HANDLE;
int onnx_handle_adx_h1 = INVALID_HANDLE;
int onnx_handle_vol_atr_m15 = INVALID_HANDLE;

int handle_rsi_m5 = INVALID_HANDLE;
int handle_rsi_h1 = INVALID_HANDLE;
int handle_atr_h1 = INVALID_HANDLE;
int handle_macd = INVALID_HANDLE;
int handle_stoch = INVALID_HANDLE;
int handle_cci = INVALID_HANDLE;
int handle_ema50 = INVALID_HANDLE;
int handle_ema200 = INVALID_HANDLE;
int handle_rsi_us500_h1 = INVALID_HANDLE;
int handle_rsi_xauusd_h1 = INVALID_HANDLE;
int handle_rsi_dxy_h1 = INVALID_HANDLE;
int handle_rsi_audjpy_h1 = INVALID_HANDLE;
int handle_rsi_euraud_h1 = INVALID_HANDLE;
int handle_rsi_gbpaud_h1 = INVALID_HANDLE;
int handle_rsi_usdjpy_h1 = INVALID_HANDLE;
int handle_rsi_h4 = INVALID_HANDLE;
int handle_rsi_d1 = INVALID_HANDLE;
int handle_sma200_h1 = INVALID_HANDLE;
int handle_sma200_h4 = INVALID_HANDLE;
int handle_bb_h1 = INVALID_HANDLE;
int handle_bb_h4 = INVALID_HANDLE;
long onnx_handle = INVALID_HANDLE;

datetime last_bar_time = 0;
datetime last_buy_grid_time = 0;
datetime last_sell_grid_time = 0;

int prev_buy_count = 0;
int prev_sell_count = 0;
datetime last_buy_close_time = 0;
datetime last_sell_close_time = 0;

bool buy_basket_close_pending = false;
bool sell_basket_close_pending = false;
bool g_trading_halted = false;

// Chart drawing / dashboard are skipped in the non-visual tester/optimizer (no chart to render)
bool g_visuals_enabled = true;

// --- Memory-based grid level tracking to bypass comment-stripping bugs in Strategy Tester
int g_highest_buy_level = 0;
int g_highest_sell_level = 0;

// Per-tick cache for GetPositionCommission (cleared at the start of each OnTick)
long   g_comm_cache_id[];
double g_comm_cache_val[];
int    g_comm_cache_count = 0;

enum ESignalState
{
   STATE_NONE = 0,
   STATE_WAIT_FILTER,
   STATE_OUTSIDE_ENVELOPE,
   STATE_BLOCKED_BY_TREND,
   STATE_BLOCKED_BY_RSI,
   STATE_BLOCKED_BY_ADX,
   STATE_BLOCKED_BY_ER,
   STATE_BLOCKED_BY_CORRELATION,
   STATE_BLOCKED_BY_VOLATILITY,
   STATE_DISTANCE_NOT_MET,
   STATE_WAIT_NEXT_LOT,
   STATE_READY
};

ESignalState prev_buy_state = STATE_NONE;
ESignalState prev_sell_state = STATE_NONE;
int prev_buy_count_log = -1;
int prev_sell_count_log = -1;

string GetStateString(ESignalState state)
{
   switch(state)
   {
      case STATE_WAIT_FILTER:      return "Wait Filter Active";
      case STATE_OUTSIDE_ENVELOPE: return "Outside Envelope Band";
      case STATE_BLOCKED_BY_TREND: return "Blocked by Trend Filter";
      case STATE_BLOCKED_BY_RSI:   return "Blocked by RSI Filter";
      case STATE_BLOCKED_BY_ADX:   return "Blocked by ADX Filter";
      case STATE_BLOCKED_BY_ER:    return "Blocked by Efficiency Ratio Filter";
      case STATE_BLOCKED_BY_CORRELATION: return "Blocked by Correlation Filter";
      case STATE_BLOCKED_BY_VOLATILITY: return "Blocked by Volatility Filter";
      case STATE_DISTANCE_NOT_MET: return "Grid Distance Not Met";
      case STATE_WAIT_NEXT_LOT:    return "Wait-Next-Lot Blocked";
      case STATE_READY:            return "Ready";
      default:                     return "Unknown";
   }
}

//+------------------------------------------------------------------+
//| DJB2 String Hashing Algorithm                                    |
//+------------------------------------------------------------------+
uint GetSymbolHash(string sym)
{
   uint hash = 5381;
   int len = StringLen(sym);
   for(int i = 0; i < len; i++)
   {
      ushort c = StringGetCharacter(sym, i);
      hash = ((hash << 5) + hash) + c;
   }
   return hash;
}

//+------------------------------------------------------------------+
//| Deterministic per-symbol magic number (suffix hardcoded to 1).   |
//| Lets us recognise positions opened by a ToTheMoonKI instance on    |
//| any other symbol without sharing state between charts.           |
//+------------------------------------------------------------------+
ulong GetMagicForSymbol(string sym)
{
   uint prefix = 10000 + (GetSymbolHash(sym) % 90000);
   return (ulong)prefix * 10000 + 1;
}

//+------------------------------------------------------------------+
//| Parse the grid level from an order comment of the form           |
//| "<prefix>_L<n>". Uses the LAST "_L" occurrence and validates the |
//| suffix is purely numeric, so a prefix that itself contains "_L", |
//| or a broker-altered/truncated comment, cannot silently corrupt   |
//| the level. Returns 'fallback' when no valid "_L<digits>" exists. |
//+------------------------------------------------------------------+
int GetPositionLevel(string comment, int fallback)
{
   int last = -1;
   int from = 0;
   int idx;
   while((idx = StringFind(comment, "_L", from)) >= 0)
   {
      last = idx;
      from = idx + 2;
   }
   if(last < 0) return fallback;

   string suffix = StringSubstr(comment, last + 2);
   int len = StringLen(suffix);
   if(len <= 0) return fallback;
   
   string digits = "";
   for(int i = 0; i < len; i++)
   {
      ushort c = StringGetCharacter(suffix, i);
      if(c >= '0' && c <= '9')
      {
         // Append digit character
         string char_str = " ";
         StringSetCharacter(char_str, 0, c);
         digits = digits + char_str;
      }
      else
      {
         break;
      }
   }
   if(StringLen(digits) <= 0) return fallback;
   return (int)StringToInteger(digits);
}

//+------------------------------------------------------------------+
//| Check if another instance is already running on the same symbol |
//+------------------------------------------------------------------+
bool IsAlreadyRunning()
{
   string current_ea = MQLInfoString(MQL_PROGRAM_NAME);
   string current_sym = Symbol();
   long current_chart = ChartID();
   
   long chart_id = ChartFirst();
   while(chart_id >= 0)
   {
      if(chart_id != current_chart)
      {
         string ea_name = ChartGetString(chart_id, CHART_EXPERT_NAME);
         string sym = ChartSymbol(chart_id);
         if(ea_name == current_ea && sym == current_sym)
         {
            return true;
         }
      }
      chart_id = ChartNext(chart_id);
   }
   return false;
}

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   // Check for duplicate instance running on the same symbol
   if(IsAlreadyRunning())
   {
      string msg = StringFormat("ERROR: ToTheMoonKI EA is already running on %s on another chart!\nOnly one instance is allowed per symbol. Deinitializing...", Symbol());
      Alert(msg);
      Print("ToTheMoonKI v1.04: " + msg);
      return INIT_FAILED;
   }

   // --- Input Parameter Validation
   if(Inp_Max_Grid_Levels < 0)
   {
      Alert("OnInit: Inp_Max_Grid_Levels cannot be negative.");
      return INIT_FAILED;
   }
    if(Inp_Max_DD_Percent < 0 || Inp_Max_DD_Percent > 100)
    {
       Alert("OnInit: Inp_Max_DD_Percent must be between 0 and 100.");
       return INIT_FAILED;
    }
    if(Inp_Use_Vol_Filter)
    {
       if(Inp_Vol_ATR_Period <= 0 || Inp_Vol_ATR_Max_Multiplier <= 0.0)
       {
          Alert("OnInit: Volatility ATR period and multiplier limit must be greater than zero.");
          return INIT_FAILED;
       }
    }

   if(Inp_Initial_Lot <= 0 || Inp_Min_Lot <= 0 || Inp_Max_Lot <= 0)
   {
      Alert("OnInit: Lot size parameters must be greater than zero.");
      return INIT_FAILED;
   }
   if(Inp_Initial_Lot < Inp_Min_Lot || Inp_Max_Lot < Inp_Initial_Lot)
   {
      Alert("OnInit: Invalid lot scaling boundaries (Inp_Min_Lot <= Inp_Initial_Lot <= Inp_Max_Lot required).");
      return INIT_FAILED;
   }
   if(Inp_Preset_Factor <= 0)
   {
      Alert("OnInit: Inp_Preset_Factor must be greater than zero.");
      return INIT_FAILED;
   }
   if(Inp_Grid_Step <= 0)
   {
      Alert("OnInit: Inp_Grid_Step must be greater than zero.");
      return INIT_FAILED;
   }
   // Use a tight epsilon (not 0.99): tolerates the optimizer's float representation of 1.0
   // while still rejecting genuine sub-1.0 values (e.g. 0.99 would shrink grid steps per level).
   if(Inp_Step_Multiplier < 1.0 - 1e-6 || Inp_Next_Lot_Multiplier < 1.0 - 1e-6)
   {
      Alert("OnInit: Step and Lot multipliers must be greater than or equal to 1.0.");
      return INIT_FAILED;
   }
   if(Inp_TakeProfit <= 0 || Min_Profit <= 0)
   {
      Alert("OnInit: Inp_TakeProfit and Min_Profit must be greater than zero.");
      return INIT_FAILED;
   }
   if(Inp_Wait_Open_Equal_Orders < 0 || Inp_Wait_Next_Lot < 0)
   {
      Alert("OnInit: Wait interval parameters cannot be negative.");
      return INIT_FAILED;
   }
   if(Inp_Wait_Next_Lot > 0)
   {
      if(Inp_Start_Wait_Next_Lot < 1 || Inp_Stop_Wait_Next_Lot < Inp_Start_Wait_Next_Lot)
      {
         Alert("OnInit: Invalid Wait-Next-Lot level boundaries (Inp_Start_Wait_Next_Lot >= 1 and Stop >= Start required).");
         return INIT_FAILED;
      }
   }
   if(Inp_Use_BreakEven)
   {
      if(Inp_BE_Trigger_Points <= 0 || Inp_BE_Points <= 0 || Inp_BE_Trigger_Points <= Inp_BE_Points)
      {
         Alert("OnInit: BreakEven trigger points and BE profit points must be greater than zero, and trigger points must be greater than BE profit points.");
         return INIT_FAILED;
      }
   }
   if(Values_Envelopes_Lower != 0 && Values_Envelopes_Lower != 1)
   {
      Alert("OnInit: Values_Envelopes_Lower must be 0 (same as upper) or 1 (custom lower).");
      return INIT_FAILED;
   }
   if(Inp_Envelopes_Deviation <= 0 || (Values_Envelopes_Lower != 0 && Inp_Envelopes_Deviation_Lower <= 0))
   {
      Alert("OnInit: Envelopes deviation must be greater than zero.");
      return INIT_FAILED;
   }
   if(Inp_Envelopes_Period <= 0 || (Values_Envelopes_Lower != 0 && Inp_Envelopes_Period_Lower <= 0))
   {
      Alert("OnInit: Envelopes indicator period must be greater than zero.");
      return INIT_FAILED;
   }
   if(Inp_Use_Trend_Filter && Inp_Trend_EMA_Period <= 0)
   {
      Alert("OnInit: Inp_Trend_EMA_Period must be greater than zero when Trend Filter is enabled.");
      return INIT_FAILED;
   }
   if(Inp_Use_RSI_Filter && Inp_RSI_Period <= 0)
   {
      Alert("OnInit: Inp_RSI_Period must be greater than zero when RSI Filter is enabled.");
      return INIT_FAILED;
   }
   if(Inp_Use_ADX_Filter)
   {
      if(Inp_ADX_Period <= 0 || Inp_ADX_Max_Level <= 0.0 || Inp_ADX_Max_Level > 100.0)
      {
         Alert("OnInit: ADX Period must be > 0 and ADX Max Level must be between 0 and 100 when ADX Filter is enabled.");
         return INIT_FAILED;
      }
   }
   if(Inp_Use_ER_Filter)
   {
      if(Inp_ER_Period <= 0 || Inp_ER_Max_Level <= 0.0 || Inp_ER_Max_Level > 1.0)
      {
         Alert("OnInit: ER Period must be > 0 and ER Max Level must be between 0 and 1 when Efficiency Ratio Filter is enabled.");
         return INIT_FAILED;
      }
   }
   if(Inp_Use_ATR_Step)
   {
      if(Inp_ATR_Period <= 0 || Inp_ATR_Multiplier <= 0)
      {
         Alert("OnInit: ATR Period and Multiplier must be greater than zero when ATR Step is enabled.");
         return INIT_FAILED;
      }
   }
   if(Inp_Spread_Max <= 0 || Inp_Dashboard_Font_Size <= 0 || Inp_Envelope_Width <= 0)
   {
      Alert("OnInit: Spread max, font size, and envelope width must be greater than zero.");
      return INIT_FAILED;
   }

   // Compute unique magic number for this symbol (Suffix is hardcoded to 1)
   calculated_magic = GetMagicForSymbol(Symbol());
   
   trade.SetExpertMagicNumber(calculated_magic);
   trade.SetTypeFillingBySymbol(Symbol());
   
   // Initialize Envelopes handles (asymmetric deviations and applied prices require two separate handles)
   handle_up = iEnvelopes(Symbol(), TimeFrame_Envelopes, Inp_Envelopes_Period, 0, Envelopes_Method, Envelopes_Price, Inp_Envelopes_Deviation);
   if(Values_Envelopes_Lower == 0)
   {
      handle_down = handle_up;
   }
   else
   {
      handle_down = iEnvelopes(Symbol(), TimeFrame_Envelopes_Lower, Inp_Envelopes_Period_Lower, 0, Envelopes_Method_Lower, Envelopes_Price_Lower, Inp_Envelopes_Deviation_Lower);
   }
   
   if(handle_up == INVALID_HANDLE || handle_down == INVALID_HANDLE)
   {
      Print("Error initializing Envelopes indicator handles.");
      return INIT_FAILED;
   }
   
   if(Inp_Use_Trend_Filter)
   {
      handle_trend = iMA(Symbol(), PERIOD_H4, Inp_Trend_EMA_Period, 0, MODE_EMA, PRICE_CLOSE);
      if(handle_trend == INVALID_HANDLE)
      {
         Print("Error initializing Trend EMA handle.");
         return INIT_FAILED;
      }
   }
   if(Inp_Use_RSI_Filter)
   {
      handle_rsi = iRSI(Symbol(), PERIOD_M15, Inp_RSI_Period, PRICE_CLOSE);
      if(handle_rsi == INVALID_HANDLE)
      {
         Print("Error initializing RSI handle.");
         return INIT_FAILED;
      }
   }
   if(Inp_Use_ADX_Filter)
   {
      handle_adx = iADX(Symbol(), Inp_ADX_Timeframe, Inp_ADX_Period);
      if(handle_adx == INVALID_HANDLE)
      {
         Print("Error initializing ADX handle.");
         return INIT_FAILED;
      }
   }
   if(Inp_Use_ATR_Step)
   {
      handle_atr = iATR(Symbol(), Inp_ATR_Timeframe, Inp_ATR_Period);
      if(handle_atr == INVALID_HANDLE)
      {
         Print("Error initializing ATR handle.");
         return INIT_FAILED;
      }
   }
   if(Inp_Use_Vol_Filter)
   {
      handle_vol_atr = iATR(Symbol(), Inp_Vol_ATR_Timeframe, Inp_Vol_ATR_Period);
      if(handle_vol_atr == INVALID_HANDLE)
      {
         Print("Error initializing Volatility ATR handle.");
         return INIT_FAILED;
      }
   }
   
    handle_rsi_m5 = iRSI(Symbol(), PERIOD_M5, 14, PRICE_CLOSE);
    handle_rsi_h1 = iRSI(Symbol(), PERIOD_H1, 14, PRICE_CLOSE);
    handle_atr_h1 = iATR(Symbol(), PERIOD_H1, 14);
    
    handle_macd = iMACD(Symbol(), PERIOD_H1, 12, 26, 9, PRICE_CLOSE);
    handle_stoch = iStochastic(Symbol(), PERIOD_M15, 14, 3, 3, MODE_SMA, STO_LOWHIGH);
    handle_cci = iCCI(Symbol(), PERIOD_H1, 14, PRICE_TYPICAL);
    handle_ema50 = iMA(Symbol(), PERIOD_H1, 50, 0, MODE_EMA, PRICE_CLOSE);
    handle_ema200 = iMA(Symbol(), PERIOD_H1, 200, 0, MODE_EMA, PRICE_CLOSE);
    handle_rsi_us500_h1 = iRSI("US500", PERIOD_H1, 14, PRICE_CLOSE);
    handle_rsi_xauusd_h1 = iRSI("XAUUSD", PERIOD_H1, 14, PRICE_CLOSE);
    handle_rsi_dxy_h1 = iRSI("DXY", PERIOD_H1, 14, PRICE_CLOSE);
    handle_rsi_audjpy_h1 = iRSI("AUDJPY", PERIOD_H1, 14, PRICE_CLOSE);
    handle_rsi_euraud_h1 = iRSI("EURAUD", PERIOD_H1, 14, PRICE_CLOSE);
    handle_rsi_gbpaud_h1 = iRSI("GBPAUD", PERIOD_H1, 14, PRICE_CLOSE);
    handle_rsi_usdjpy_h1 = iRSI("USDJPY", PERIOD_H1, 14, PRICE_CLOSE);
    
    handle_rsi_h4 = iRSI(Symbol(), PERIOD_H4, 14, PRICE_CLOSE);
    handle_rsi_d1 = iRSI(Symbol(), PERIOD_D1, 14, PRICE_CLOSE);
    handle_sma200_h1 = iMA(Symbol(), PERIOD_H1, 200, 0, MODE_SMA, PRICE_CLOSE);
    handle_sma200_h4 = iMA(Symbol(), PERIOD_H4, 200, 0, MODE_SMA, PRICE_CLOSE);
    handle_bb_h1 = iBands(Symbol(), PERIOD_H1, 20, 0, 2.0, PRICE_CLOSE);
    handle_bb_h4 = iBands(Symbol(), PERIOD_H4, 20, 0, 2.0, PRICE_CLOSE);
    
    // Decoupled ONNX-specific indicator handles
    onnx_handle_trend_h4 = iMA(Symbol(), PERIOD_H4, 250, 0, MODE_EMA, PRICE_CLOSE);
    onnx_handle_rsi_m15 = iRSI(Symbol(), PERIOD_M15, 21, PRICE_CLOSE);
    onnx_handle_adx_h1 = iADX(Symbol(), PERIOD_H1, 14);
    onnx_handle_vol_atr_m15 = iATR(Symbol(), PERIOD_M15, 10);
    
    if(handle_rsi_m5 == INVALID_HANDLE || handle_rsi_h1 == INVALID_HANDLE || handle_atr_h1 == INVALID_HANDLE ||
       onnx_handle_trend_h4 == INVALID_HANDLE || onnx_handle_rsi_m15 == INVALID_HANDLE ||
       onnx_handle_adx_h1 == INVALID_HANDLE || onnx_handle_vol_atr_m15 == INVALID_HANDLE ||
       handle_macd == INVALID_HANDLE || handle_stoch == INVALID_HANDLE || handle_cci == INVALID_HANDLE ||
       handle_ema50 == INVALID_HANDLE || handle_ema200 == INVALID_HANDLE ||
       handle_rsi_us500_h1 == INVALID_HANDLE || handle_rsi_xauusd_h1 == INVALID_HANDLE ||
       handle_rsi_dxy_h1 == INVALID_HANDLE || handle_rsi_audjpy_h1 == INVALID_HANDLE ||
       handle_rsi_euraud_h1 == INVALID_HANDLE || handle_rsi_gbpaud_h1 == INVALID_HANDLE ||
       handle_rsi_usdjpy_h1 == INVALID_HANDLE ||
       handle_rsi_h4 == INVALID_HANDLE || handle_rsi_d1 == INVALID_HANDLE ||
       handle_sma200_h1 == INVALID_HANDLE || handle_sma200_h4 == INVALID_HANDLE ||
       handle_bb_h1 == INVALID_HANDLE || handle_bb_h4 == INVALID_HANDLE)
    {
       Print("Error initializing new ONNX indicator handles.");
       return INIT_FAILED;
    }
   
   if(Inp_Use_ONNX_Gatekeeper)
   {
      // Symbol & Digits Guard: ONNX model is trained ONLY for AUDUSD on a 5-digit broker account
      string sym = Symbol();
      StringToUpper(sym);
      if(StringFind(sym, "AUDUSD") < 0)
      {
         Alert("OnInit ERROR: ONNX Gatekeeper is trained ONLY for AUDUSD. Running on other symbols is blocked when Inp_Use_ONNX_Gatekeeper is enabled.");
         return INIT_FAILED;
      }
      if(Digits() != 5)
      {
         Alert("OnInit ERROR: ONNX Gatekeeper expects 5-digit quoting (Point = 0.00001). Running on this symbol/broker configuration is blocked.");
         return INIT_FAILED;
      }

      onnx_handle = OnnxCreateFromBuffer(gatekeeper_data, ONNX_DEFAULT);
      if(onnx_handle == INVALID_HANDLE)
      {
         Print("Error: Failed to create ONNX session from buffer.");
         return INIT_FAILED;
      }
      
      const long input_shape[] = {1, 49};
      if(!OnnxSetInputShape(onnx_handle, 0, input_shape))
      {
         Print("Error setting ONNX input shape. Error: ", GetLastError());
         OnnxRelease(onnx_handle);
         onnx_handle = INVALID_HANDLE;
         return INIT_FAILED;
      }
      
      const long output0_shape[] = {1};
      const long output1_shape[] = {1, 2};
      if(!OnnxSetOutputShape(onnx_handle, 0, output0_shape) || !OnnxSetOutputShape(onnx_handle, 1, output1_shape))
      {
         Print("Error setting ONNX output shapes. Error: ", GetLastError());
         OnnxRelease(onnx_handle);
         onnx_handle = INVALID_HANDLE;
         return INIT_FAILED;
      }
      
      Print("ONNX Gatekeeper session created successfully.");
   }
   
   last_bar_time = 0;
   prev_buy_count = 0;
   prev_sell_count = 0;
   last_buy_close_time = 0;
   last_sell_close_time = 0;
   g_trading_halted = false;

   // Cache once: enable visuals in live/visual-mode, disable in non-visual tester/optimizer
   g_visuals_enabled = (!MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_VISUAL_MODE));
   
   // Draw initial envelope lines on chart
   DrawEnvelopeLines(true);
    
    PrintFormat("ToTheMoonKI EA v1.04 initialized successfully - (c) by Thomas Nickel. Magic: %I64u | Initial Lot: %.2f | Grid Step: %d | TP: %d", calculated_magic, Inp_Initial_Lot, Inp_Grid_Step, Inp_TakeProfit);
    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   ObjectsDeleteAll(0, "TTM_");
   
   if(handle_up != INVALID_HANDLE)
      IndicatorRelease(handle_up);
   if(handle_down != INVALID_HANDLE && handle_down != handle_up)
      IndicatorRelease(handle_down);
   if(handle_trend != INVALID_HANDLE)
      IndicatorRelease(handle_trend);
   if(handle_rsi != INVALID_HANDLE)
      IndicatorRelease(handle_rsi);
   if(handle_atr != INVALID_HANDLE)
      IndicatorRelease(handle_atr);
   if(handle_vol_atr != INVALID_HANDLE)
      IndicatorRelease(handle_vol_atr);
   if(handle_adx != INVALID_HANDLE)
      IndicatorRelease(handle_adx);
      
   if(onnx_handle_trend_h4 != INVALID_HANDLE)
      IndicatorRelease(onnx_handle_trend_h4);
   if(onnx_handle_rsi_m15 != INVALID_HANDLE)
      IndicatorRelease(onnx_handle_rsi_m15);
   if(onnx_handle_adx_h1 != INVALID_HANDLE)
      IndicatorRelease(onnx_handle_adx_h1);
   if(onnx_handle_vol_atr_m15 != INVALID_HANDLE)
      IndicatorRelease(onnx_handle_vol_atr_m15);
      
   if(handle_rsi_m5 != INVALID_HANDLE)
      IndicatorRelease(handle_rsi_m5);
   if(handle_rsi_h1 != INVALID_HANDLE)
      IndicatorRelease(handle_rsi_h1);
   if(handle_atr_h1 != INVALID_HANDLE)
      IndicatorRelease(handle_atr_h1);
   if(handle_macd != INVALID_HANDLE)
      IndicatorRelease(handle_macd);
   if(handle_stoch != INVALID_HANDLE)
      IndicatorRelease(handle_stoch);
   if(handle_cci != INVALID_HANDLE)
      IndicatorRelease(handle_cci);
    if(handle_ema50 != INVALID_HANDLE)
       IndicatorRelease(handle_ema50);
    if(handle_ema200 != INVALID_HANDLE)
       IndicatorRelease(handle_ema200);
     if(handle_rsi_us500_h1 != INVALID_HANDLE)
        IndicatorRelease(handle_rsi_us500_h1);
     if(handle_rsi_xauusd_h1 != INVALID_HANDLE)
        IndicatorRelease(handle_rsi_xauusd_h1);
     if(handle_rsi_dxy_h1 != INVALID_HANDLE)
        IndicatorRelease(handle_rsi_dxy_h1);
     if(handle_rsi_audjpy_h1 != INVALID_HANDLE)
        IndicatorRelease(handle_rsi_audjpy_h1);
     if(handle_rsi_euraud_h1 != INVALID_HANDLE)
        IndicatorRelease(handle_rsi_euraud_h1);
     if(handle_rsi_gbpaud_h1 != INVALID_HANDLE)
        IndicatorRelease(handle_rsi_gbpaud_h1);
     if(handle_rsi_usdjpy_h1 != INVALID_HANDLE)
        IndicatorRelease(handle_rsi_usdjpy_h1);
     if(handle_rsi_h4 != INVALID_HANDLE)
        IndicatorRelease(handle_rsi_h4);
     if(handle_rsi_d1 != INVALID_HANDLE)
        IndicatorRelease(handle_rsi_d1);
     if(handle_sma200_h1 != INVALID_HANDLE)
        IndicatorRelease(handle_sma200_h1);
     if(handle_sma200_h4 != INVALID_HANDLE)
        IndicatorRelease(handle_sma200_h4);
     if(handle_bb_h1 != INVALID_HANDLE)
        IndicatorRelease(handle_bb_h1);
     if(handle_bb_h4 != INVALID_HANDLE)
        IndicatorRelease(handle_bb_h4);
   if(onnx_handle != INVALID_HANDLE)
   {
      OnnxRelease(onnx_handle);
      onnx_handle = INVALID_HANDLE;
   }
      
   Print("ToTheMoonKI EA v1.04 deinitialized - (c) by Thomas Nickel.");
}

//+------------------------------------------------------------------+
//| Scaled lot calculation based on account balance                  |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Normalize raw lot to volume step, min, and max limits            |
//+------------------------------------------------------------------+
double NormalizeLot(double raw_lot)
{
   double step = SymbolInfoDouble(Symbol(), SYMBOL_VOLUME_STEP);
   if(step <= 0) step = 0.01;
   
   double min_lot = SymbolInfoDouble(Symbol(), SYMBOL_VOLUME_MIN);
   double max_lot = SymbolInfoDouble(Symbol(), SYMBOL_VOLUME_MAX);
   if(min_lot <= 0) min_lot = 0.01;
   if(max_lot <= 0) max_lot = 100.0;
   
   // Robust calculation of decimal digits for the step size (e.g. 0.05, 0.25)
   int lot_digits = 0;
   double temp_step = step;
   while(temp_step > 0 && temp_step - MathFloor(temp_step) > 0.00001 && lot_digits < 8)
   {
      temp_step *= 10;
      lot_digits++;
   }
   
   double lot = NormalizeDouble(MathRound(raw_lot / step) * step, lot_digits);
   
   if(lot < min_lot) lot = min_lot;
   if(lot > max_lot) lot = max_lot;
   return lot;
}

//+------------------------------------------------------------------+
//| Scaled lot calculation based on account balance                  |
//+------------------------------------------------------------------+
double GetScaledLot(double base_lot)
{
   // NOTE: lots scale with balance / Inp_Preset_Factor. On accounts smaller than
   // Inp_Preset_Factor the scaled maximum collapses to the broker minimum lot after
   // normalisation, which flattens the martingale (every grid lot becomes the min lot).
   // The shipped defaults therefore assume an account balance >= Inp_Preset_Factor.
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double scaled = (balance / Inp_Preset_Factor) * base_lot;
   
   double scaled_min = (balance / Inp_Preset_Factor) * Inp_Min_Lot;
   double scaled_max = (balance / Inp_Preset_Factor) * Inp_Max_Lot;
   
   if(scaled < scaled_min) scaled = scaled_min;
   if(scaled > scaled_max) scaled = scaled_max;
   
   return NormalizeLot(scaled);
}

//+------------------------------------------------------------------+
//| Check if a new M5 bar has opened                                |
//+------------------------------------------------------------------+
bool IsNewBar()
{
   datetime current_bar_time = iTime(Symbol(), PERIOD_M5, 0);
   if(current_bar_time != last_bar_time)
   {
      last_bar_time = current_bar_time;
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Get Upper Envelope Band value                                    |
//+------------------------------------------------------------------+
double GetEnvelopeUpper(int index)
{
   double val[];
   ArraySetAsSeries(val, true);
   if(CopyBuffer(handle_up, 0, index, 1, val) > 0)
      return val[0];
   return EMPTY_VALUE;
}

//+------------------------------------------------------------------+
//| Get Lower Envelope Band value                                    |
//+------------------------------------------------------------------+
double GetEnvelopeLower(int index)
{
   double val[];
   ArraySetAsSeries(val, true);
   if(CopyBuffer(handle_down, 1, index, 1, val) > 0)
      return val[0];
   return EMPTY_VALUE;
}

//+------------------------------------------------------------------+
//| Check trend filter for Buy entry                                 |
//+------------------------------------------------------------------+
bool IsTrendBuyAllowed()
{
   if(!Inp_Use_Trend_Filter) return true;
   double ma[];
   ArraySetAsSeries(ma, true);
   if(handle_trend != INVALID_HANDLE && CopyBuffer(handle_trend, 0, 1, 1, ma) > 0)
   {
      double close_val = iClose(Symbol(), PERIOD_M5, 1);
      return (close_val > ma[0]);
   }
   return false; // Fail-safe: block trade if filter is active but data is not ready
}

//+------------------------------------------------------------------+
//| Check trend filter for Sell entry                                |
//+------------------------------------------------------------------+
bool IsTrendSellAllowed()
{
   if(!Inp_Use_Trend_Filter) return true;
   double ma[];
   ArraySetAsSeries(ma, true);
   if(handle_trend != INVALID_HANDLE && CopyBuffer(handle_trend, 0, 1, 1, ma) > 0)
   {
      double close_val = iClose(Symbol(), PERIOD_M5, 1);
      return (close_val < ma[0]);
   }
   return false; // Fail-safe: block trade if filter is active but data is not ready
}

//+------------------------------------------------------------------+
//| Check RSI filter for Buy entry                                   |
//+------------------------------------------------------------------+
bool IsRSIBuyAllowed()
{
   if(!Inp_Use_RSI_Filter) return true;
   double rsi[];
   ArraySetAsSeries(rsi, true);
   if(handle_rsi != INVALID_HANDLE && CopyBuffer(handle_rsi, 0, 1, 1, rsi) > 0)
   {
      return (rsi[0] < Inp_RSI_Oversold);
   }
   return false; // Fail-safe: block trade if filter is active but data is not ready
}

//+------------------------------------------------------------------+
//| Check RSI filter for Sell entry                                  |
//+------------------------------------------------------------------+
bool IsRSISellAllowed()
{
   if(!Inp_Use_RSI_Filter) return true;
   double rsi[];
   ArraySetAsSeries(rsi, true);
   if(handle_rsi != INVALID_HANDLE && CopyBuffer(handle_rsi, 0, 1, 1, rsi) > 0)
   {
      return (rsi[0] > Inp_RSI_Overbought);
   }
   return false; // Fail-safe: block trade if filter is active but data is not ready
}

//+------------------------------------------------------------------+
//| Check ADX trend-strength filter for entry (non-directional).     |
//| Blocks only the FIRST grid entry when a strong trend is active,  |
//| so a new mean-reversion basket is not opened against a runaway   |
//| move. Recovery grid-adds are intentionally NOT filtered.         |
//+------------------------------------------------------------------+
bool IsADXEntryAllowed()
{
   if(!Inp_Use_ADX_Filter) return true;
   double adx[];
   ArraySetAsSeries(adx, true);
   if(handle_adx != INVALID_HANDLE && CopyBuffer(handle_adx, 0, 1, 1, adx) > 0)
   {
      return (adx[0] < Inp_ADX_Max_Level);
   }
   return false; // Fail-safe: block trade if filter is active but data is not ready
}

//+------------------------------------------------------------------+
//| Kaufman Efficiency Ratio = net directional move / total path.    |
//| Computed inline from closes (no indicator handle needed).        |
//| Returns 0..1 (0 = choppy/range, 1 = perfectly trending),         |
//| or -1.0 if the price data is not yet available.                  |
//+------------------------------------------------------------------+
double CalcEfficiencyRatio(int period, ENUM_TIMEFRAMES timeframe)
{
   double closes[];
   ArraySetAsSeries(closes, true);
   if(CopyClose(Symbol(), timeframe, 1, period + 1, closes) < period + 1)
      return -1.0; // data not ready

   double direction = MathAbs(closes[0] - closes[period]);
   double volatility = 0.0;
   for(int i = 0; i < period; i++)
      volatility += MathAbs(closes[i] - closes[i + 1]);

   if(volatility <= 0.0) return 0.0; // flat market: treat as fully non-trending
   return direction / volatility;
}

//+------------------------------------------------------------------+
//| Check Efficiency Ratio filter for entry (non-directional).       |
//| Blocks only the FIRST grid entry when the market is trending     |
//| (ER high), like the ADX filter. Recovery grid-adds are NOT       |
//| filtered.                                                        |
//+------------------------------------------------------------------+
bool IsEREntryAllowed()
{
   if(!Inp_Use_ER_Filter) return true;
   double er = CalcEfficiencyRatio(Inp_ER_Period, Inp_ER_Timeframe);
   if(er < 0.0) return false; // Fail-safe: block trade if data is not ready
   return (er < Inp_ER_Max_Level);
}

//+------------------------------------------------------------------+
//| Get minutes to the next economic calendar event of the currency |
//+------------------------------------------------------------------+
double GetMinutesToNextNews(string currency)
{
   MqlCalendarValue values[];
   datetime time_from = TimeCurrent();
   datetime time_to = TimeCurrent() + 24 * 3600; 
   
   int total = CalendarValueHistory(values, time_from, time_to);
   if(total <= 0)
      return 1440.0;
      
   double min_diff_minutes = 1440.0;
   for(int i = 0; i < total; i++)
   {
      MqlCalendarEvent event;
      if(CalendarEventById(values[i].event_id, event))
      {
         MqlCalendarCountry country;
         if(CalendarCountryById(event.country_id, country))
         {
            if(country.currency == currency)
            {
               if(event.importance == CALENDAR_IMPORTANCE_HIGH || event.importance == CALENDAR_IMPORTANCE_MODERATE)
               {
                  double diff = (double)(values[i].time - time_from) / 60.0;
                  if(diff >= 0 && diff < min_diff_minutes)
                  {
                     min_diff_minutes = diff;
                  }
               }
            }
         }
      }
   }
   return min_diff_minutes;
}

//+------------------------------------------------------------------+
//| Get consecutive bullish/bearish bars on M5                       |
//+------------------------------------------------------------------+
int GetConsecutiveBars()
{
   int count = 0;
   double close1 = iClose(Symbol(), PERIOD_M5, 1);
   double open1 = iOpen(Symbol(), PERIOD_M5, 1);
   if(close1 == open1) return 0;
   
   bool is_bullish = (close1 > open1);
   for(int i = 1; i <= 100; i++)
   {
      double c = iClose(Symbol(), PERIOD_M5, i);
      double o = iOpen(Symbol(), PERIOD_M5, i);
      if(is_bullish)
      {
         if(c > o) count++;
         else break;
      }
      else
      {
         if(c < o) count++;
         else break;
      }
   }
   return is_bullish ? count : -count;
}

//+------------------------------------------------------------------+
//| Get average volume ratio on M5                                   |
//+------------------------------------------------------------------+
double GetVolumeRatio()
{
   long vol_arr[];
   double vol_ratio = 1.0;
   if(CopyTickVolume(Symbol(), PERIOD_M5, 1, 20, vol_arr) >= 20)
   {
      double sum = 0.0;
      for(int i = 0; i < 20; i++) sum += (double)vol_arr[i];
      double avg = sum / 20.0;
      if(avg > 0) vol_ratio = (double)vol_arr[19] / avg;
   }
   return vol_ratio;
}

//+------------------------------------------------------------------+
//| Check ONNX Entry Gatekeeper permission (first entry only)        |
//+------------------------------------------------------------------+
bool IsONNXEntryAllowed(bool is_buy_trigger)
{
   if(!Inp_Use_ONNX_Gatekeeper || onnx_handle == INVALID_HANDLE)
      return true;
      
   float features[49];
   
   // 1. is_buy
   features[0] = is_buy_trigger ? 1.0f : 0.0f;
   
   // 2. dist_ema250_h4
   double close1_m5 = iClose(Symbol(), PERIOD_M5, 1);
   double ma[];
   ArraySetAsSeries(ma, true);
   double ma_val = 0.0;
   if(onnx_handle_trend_h4 != INVALID_HANDLE && CopyBuffer(onnx_handle_trend_h4, 0, 1, 1, ma) > 0)
   {
      ma_val = ma[0];
   }
   features[1] = (float)((close1_m5 - ma_val) / Point());
   
   // 3. rsi_m5
   double rsi_m5_arr[];
   double rsi_m5_val = 50.0;
   if(handle_rsi_m5 != INVALID_HANDLE && CopyBuffer(handle_rsi_m5, 0, 1, 1, rsi_m5_arr) > 0)
   {
      rsi_m5_val = rsi_m5_arr[0];
   }
   features[2] = (float)rsi_m5_val;
   
   // 4. rsi_m15
   double rsi_m15_arr[];
   double rsi_m15_val = 50.0;
   if(onnx_handle_rsi_m15 != INVALID_HANDLE && CopyBuffer(onnx_handle_rsi_m15, 0, 1, 1, rsi_m15_arr) > 0)
   {
      rsi_m15_val = rsi_m15_arr[0];
   }
   features[3] = (float)rsi_m15_val;
   
   // 5. rsi_h1
   double rsi_h1_arr[];
   double rsi_h1_val = 50.0;
   if(handle_rsi_h1 != INVALID_HANDLE && CopyBuffer(handle_rsi_h1, 0, 1, 1, rsi_h1_arr) > 0)
   {
      rsi_h1_val = rsi_h1_arr[0];
   }
   features[4] = (float)rsi_h1_val;
   
   // 6. adx_h1
   double adx_arr[];
   double adx_val = 20.0;
   if(onnx_handle_adx_h1 != INVALID_HANDLE && CopyBuffer(onnx_handle_adx_h1, 0, 1, 1, adx_arr) > 0)
   {
      adx_val = adx_arr[0];
   }
   features[5] = (float)adx_val;
   
   // 7. efficiency_ratio_h1
   features[6] = (float)CalcEfficiencyRatio(10, PERIOD_H1);
   
   // 8. atr_ratio_m15
   double atr_vals_m15[];
   ArraySetAsSeries(atr_vals_m15, true);   // [0] = most recent (shift 1) bar, matching training (atr[t-1] / avg)
   float atr_ratio_m15 = 1.0f;
   if(onnx_handle_vol_atr_m15 != INVALID_HANDLE)
   {
      int copied = CopyBuffer(onnx_handle_vol_atr_m15, 0, 1, 30, atr_vals_m15);
      if(copied >= 30)
      {
         double sum = 0.0;
         for(int i = 0; i < 30; i++) sum += atr_vals_m15[i];
         double avg = sum / 30.0;
         if(avg > 0) atr_ratio_m15 = (float)(atr_vals_m15[0] / avg);
      }
   }
   features[7] = atr_ratio_m15;
   
   // 9. atr_ratio_h1
   double atr_vals_h1[];
   ArraySetAsSeries(atr_vals_h1, true);   // [0] = most recent (shift 1) bar, matching training (atr[t-1] / avg)
   float atr_ratio_h1 = 1.0f;
   if(handle_atr_h1 != INVALID_HANDLE)
   {
      int copied_h1 = CopyBuffer(handle_atr_h1, 0, 1, 30, atr_vals_h1);
      if(copied_h1 >= 30)
      {
         double sum = 0.0;
         for(int i = 0; i < 30; i++) sum += atr_vals_h1[i];
         double avg = sum / 30.0;
         if(avg > 0) atr_ratio_h1 = (float)(atr_vals_h1[0] / avg);
      }
   }
   features[8] = atr_ratio_h1;
   
   // 10. spread_points
   // Training used spread.shift(1) (the just-closed bar's spread), so feed the shift-1 bar
   // spread here rather than the live spread to avoid train/serve skew. Fall back to the live
   // spread only if the bar spread is unavailable.
   int spread_arr[];
   ArraySetAsSeries(spread_arr, true);
   if(CopySpread(Symbol(), PERIOD_M5, 1, 1, spread_arr) > 0)
      features[9] = (float)spread_arr[0];
   else
      features[9] = (float)SymbolInfoInteger(Symbol(), SYMBOL_SPREAD);
   
   // 11. sin_hour, 12. cos_hour, 13. sin_day, 14. cos_day
   datetime t_val = iTime(Symbol(), PERIOD_M5, 0);
   MqlDateTime dt;
   TimeToStruct(t_val, dt);
   int hour = dt.hour;
   int day_of_week = dt.day_of_week;
   features[10] = (float)sin(2.0 * M_PI * hour / 24.0);
   features[11] = (float)cos(2.0 * M_PI * hour / 24.0);
   features[12] = (float)sin(2.0 * M_PI * day_of_week / 7.0);
   features[13] = (float)cos(2.0 * M_PI * day_of_week / 7.0);
   
   // 15. dist_env_up, 16. dist_env_down
   double env_up = GetEnvelopeUpper(1);
   double env_down = GetEnvelopeLower(1);
   features[14] = (float)((close1_m5 - env_up) / Point());
   features[15] = (float)((close1_m5 - env_down) / Point());
   
   // 17. macd_h1, 18. macd_sig_h1, 19. macd_hist_h1
   double macd_line_val = 0.0;
   double macd_sig_val = 0.0;
   double macd_hist_val = 0.0;
   double macd_line_arr[];
   double macd_sig_arr[];
   if(handle_macd != INVALID_HANDLE && CopyBuffer(handle_macd, 0, 1, 1, macd_line_arr) > 0)
   {
      macd_line_val = macd_line_arr[0];
   }
   if(handle_macd != INVALID_HANDLE && CopyBuffer(handle_macd, 1, 1, 1, macd_sig_arr) > 0)
   {
      macd_sig_val = macd_sig_arr[0];
   }
   macd_hist_val = macd_line_val - macd_sig_val;
   features[16] = (float)macd_line_val;
   features[17] = (float)macd_sig_val;
   features[18] = (float)macd_hist_val;
   
   // 20. stoch_k_m15, 21. stoch_d_m15
   double stoch_k_val = 50.0;
   double stoch_d_val = 50.0;
   double stoch_k_arr[];
   double stoch_d_arr[];
   if(handle_stoch != INVALID_HANDLE && CopyBuffer(handle_stoch, 0, 1, 1, stoch_k_arr) > 0)
   {
      stoch_k_val = stoch_k_arr[0];
   }
   if(handle_stoch != INVALID_HANDLE && CopyBuffer(handle_stoch, 1, 1, 1, stoch_d_arr) > 0)
   {
      stoch_d_val = stoch_d_arr[0];
   }
   features[19] = (float)stoch_k_val;
   features[20] = (float)stoch_d_val;
   
   // 22. cci_h1
   double cci_val = 0.0;
   double cci_arr[];
   if(handle_cci != INVALID_HANDLE && CopyBuffer(handle_cci, 0, 1, 1, cci_arr) > 0)
   {
      cci_val = cci_arr[0];
   }
   features[21] = (float)cci_val;
   
   // 23. ema50_ema200_dist_h1
   double ema50_val = close1_m5;
   double ema200_val = close1_m5;
   double ema50_arr[];
   double ema200_arr[];
   if(handle_ema50 != INVALID_HANDLE && CopyBuffer(handle_ema50, 0, 1, 1, ema50_arr) > 0)
   {
      ema50_val = ema50_arr[0];
   }
   if(handle_ema200 != INVALID_HANDLE && CopyBuffer(handle_ema200, 0, 1, 1, ema200_arr) > 0)
   {
      ema200_val = ema200_arr[0];
   }
    features[22] = (float)((ema50_val - ema200_val) / Point());
    
    // 24. vix_close
    double vix_close_arr[];
    float vix_close_val = 15.0f;
    if(CopyClose("VIX", PERIOD_M5, 1, 1, vix_close_arr) > 0)
    {
       vix_close_val = (float)vix_close_arr[0];
    }
    features[23] = vix_close_val;

    // 25. rsi_us500_h1
    double rsi_us500_arr[];
    float rsi_us500_val = 50.0f;
    if(handle_rsi_us500_h1 != INVALID_HANDLE && CopyBuffer(handle_rsi_us500_h1, 0, 1, 1, rsi_us500_arr) > 0)
    {
       rsi_us500_val = (float)rsi_us500_arr[0];
    }
    features[24] = rsi_us500_val;

    // 26. rsi_xauusd_h1
    double rsi_xauusd_arr[];
    float rsi_xauusd_val = 50.0f;
    if(handle_rsi_xauusd_h1 != INVALID_HANDLE && CopyBuffer(handle_rsi_xauusd_h1, 0, 1, 1, rsi_xauusd_arr) > 0)
    {
       rsi_xauusd_val = (float)rsi_xauusd_arr[0];
    }
    features[25] = rsi_xauusd_val;

   // 27. minutes_to_usd_news
   features[26] = (float)GetMinutesToNextNews("USD");

   // 28. minutes_to_aud_news
   features[27] = (float)GetMinutesToNextNews("AUD");

   // 29. dxy_close
   double dxy_close_arr[];
   float dxy_close_val = 100.0f;
   if(CopyClose("DXY", PERIOD_M5, 1, 1, dxy_close_arr) > 0)
   {
      dxy_close_val = (float)dxy_close_arr[0];
   }
   features[28] = dxy_close_val;

   // 30. rsi_dxy_h1
   double rsi_dxy_arr[];
   float rsi_dxy_val = 50.0f;
   if(handle_rsi_dxy_h1 != INVALID_HANDLE && CopyBuffer(handle_rsi_dxy_h1, 0, 1, 1, rsi_dxy_arr) > 0)
   {
      rsi_dxy_val = (float)rsi_dxy_arr[0];
   }
   features[29] = rsi_dxy_val;

   // 31. rsi_audjpy_h1
   double rsi_audjpy_arr[];
   float rsi_audjpy_val = 50.0f;
   if(handle_rsi_audjpy_h1 != INVALID_HANDLE && CopyBuffer(handle_rsi_audjpy_h1, 0, 1, 1, rsi_audjpy_arr) > 0)
   {
      rsi_audjpy_val = (float)rsi_audjpy_arr[0];
   }
   features[30] = rsi_audjpy_val;

   // 32. rsi_euraud_h1
   double rsi_euraud_arr[];
   float rsi_euraud_val = 50.0f;
   if(handle_rsi_euraud_h1 != INVALID_HANDLE && CopyBuffer(handle_rsi_euraud_h1, 0, 1, 1, rsi_euraud_arr) > 0)
   {
      rsi_euraud_val = (float)rsi_euraud_arr[0];
   }
   features[31] = rsi_euraud_val;

   // 33. rsi_gbpaud_h1
   double rsi_gbpaud_arr[];
   float rsi_gbpaud_val = 50.0f;
   if(handle_rsi_gbpaud_h1 != INVALID_HANDLE && CopyBuffer(handle_rsi_gbpaud_h1, 0, 1, 1, rsi_gbpaud_arr) > 0)
   {
      rsi_gbpaud_val = (float)rsi_gbpaud_arr[0];
   }
   features[32] = rsi_gbpaud_val;

   // 34. rsi_usdjpy_h1
   double rsi_usdjpy_arr[];
   float rsi_usdjpy_val = 50.0f;
   if(handle_rsi_usdjpy_h1 != INVALID_HANDLE && CopyBuffer(handle_rsi_usdjpy_h1, 0, 1, 1, rsi_usdjpy_arr) > 0)
   {
      rsi_usdjpy_val = (float)rsi_usdjpy_arr[0];
   }
    features[33] = rsi_usdjpy_val;
    
    // 35. is_asian_session
    features[34] = ((hour >= 22 || hour < 8) ? 1.0f : 0.0f);

    // 36. is_london_session
    features[35] = ((hour >= 8 && hour < 16) ? 1.0f : 0.0f);

    // 37. is_ny_session
    features[36] = ((hour >= 13 && hour < 21) ? 1.0f : 0.0f);

    // 38. consec_bars_m5
    features[37] = (float)GetConsecutiveBars();

    // 39. vol_ratio_m5
    features[38] = (float)GetVolumeRatio();
    
    // 40. rsi_h4
    double rsi_h4_arr[];
    float rsi_h4_val = 50.0f;
    if(handle_rsi_h4 != INVALID_HANDLE && CopyBuffer(handle_rsi_h4, 0, 1, 1, rsi_h4_arr) > 0)
    {
       rsi_h4_val = (float)rsi_h4_arr[0];
    }
    features[39] = rsi_h4_val;

    // 41. rsi_d1
    double rsi_d1_arr[];
    float rsi_d1_val = 50.0f;
    if(handle_rsi_d1 != INVALID_HANDLE && CopyBuffer(handle_rsi_d1, 0, 1, 1, rsi_d1_arr) > 0)
    {
       rsi_d1_val = (float)rsi_d1_arr[0];
    }
    features[40] = rsi_d1_val;

    // 42. dist_sma200_h1
    double sma200_h1_arr[];
    float dist_sma200_h1 = 0.0f;
    if(handle_sma200_h1 != INVALID_HANDLE && CopyBuffer(handle_sma200_h1, 0, 1, 1, sma200_h1_arr) > 0)
    {
       dist_sma200_h1 = (float)((close1_m5 - sma200_h1_arr[0]) / Point());
    }
    features[41] = dist_sma200_h1;

    // 43. dist_sma200_h4
    double sma200_h4_arr[];
    float dist_sma200_h4 = 0.0f;
    if(handle_sma200_h4 != INVALID_HANDLE && CopyBuffer(handle_sma200_h4, 0, 1, 1, sma200_h4_arr) > 0)
    {
       dist_sma200_h4 = (float)((close1_m5 - sma200_h4_arr[0]) / Point());
    }
    features[42] = dist_sma200_h4;

    // 44. bb_width_h1, 46. dist_bb_upper_h1, 47. dist_bb_lower_h1
    double bb_mid_h1[], bb_up_h1[], bb_lo_h1[];
    float bb_width_h1 = 0.0f;
    float dist_bb_upper_h1 = 0.0f;
    float dist_bb_lower_h1 = 0.0f;
    if(handle_bb_h1 != INVALID_HANDLE &&
       CopyBuffer(handle_bb_h1, 0, 1, 1, bb_mid_h1) > 0 &&
       CopyBuffer(handle_bb_h1, 1, 1, 1, bb_up_h1) > 0 &&
       CopyBuffer(handle_bb_h1, 2, 1, 1, bb_lo_h1) > 0)
    {
       if(bb_mid_h1[0] > 0)
          bb_width_h1 = (float)((bb_up_h1[0] - bb_lo_h1[0]) / bb_mid_h1[0]);
       dist_bb_upper_h1 = (float)((close1_m5 - bb_up_h1[0]) / Point());
       dist_bb_lower_h1 = (float)((close1_m5 - bb_lo_h1[0]) / Point());
    }
    features[43] = bb_width_h1;
    
    // 45. bb_width_h4, 48. dist_bb_upper_h4, 49. dist_bb_lower_h4
    double bb_mid_h4[], bb_up_h4[], bb_lo_h4[];
    float bb_width_h4 = 0.0f;
    float dist_bb_upper_h4 = 0.0f;
    float dist_bb_lower_h4 = 0.0f;
    if(handle_bb_h4 != INVALID_HANDLE &&
       CopyBuffer(handle_bb_h4, 0, 1, 1, bb_mid_h4) > 0 &&
       CopyBuffer(handle_bb_h4, 1, 1, 1, bb_up_h4) > 0 &&
       CopyBuffer(handle_bb_h4, 2, 1, 1, bb_lo_h4) > 0)
    {
       if(bb_mid_h4[0] > 0)
          bb_width_h4 = (float)((bb_up_h4[0] - bb_lo_h4[0]) / bb_mid_h4[0]);
       dist_bb_upper_h4 = (float)((close1_m5 - bb_up_h4[0]) / Point());
       dist_bb_lower_h4 = (float)((close1_m5 - bb_lo_h4[0]) / Point());
    }
    features[44] = bb_width_h4;
    features[45] = dist_bb_upper_h1;
    features[46] = dist_bb_lower_h1;
    features[47] = dist_bb_upper_h4;
    features[48] = dist_bb_lower_h4;
    
    // Run ONNX model
    long output_labels[1];
    float output_probs[2];
    
    output_labels[0] = 0;
    output_probs[0] = 0.0f;
    output_probs[1] = 0.0f;
    
    if(Inp_Debug_Mode)
    {
       string feat_str = "";
        for(int i = 0; i < 49; i++)
           feat_str += StringFormat("f[%d]=%.4f ", i, features[i]);
       Print("ONNX Features: ", feat_str);
    }
    
    if(!OnnxRun(onnx_handle, ONNX_NO_CONVERSION, features, output_labels, output_probs))
   {
      Print("ONNX: OnnxRun failed. Error: ", GetLastError());
      return true; // Fail-safe: allow entry if model fails to execute
   }
   
   if(Inp_Debug_Mode)
   {
      PrintFormat("ONNX Gatekeeper Check - Type: %s | Prob Class 0 (Dangerous): %.4f | Prob Class 1 (Safe): %.4f | Decision: %s",
                  (is_buy_trigger ? "BUY" : "SELL"), output_probs[0], output_probs[1], 
                  (output_probs[1] >= Inp_Min_ONNX_Probability ? "ALLOWED" : "BLOCKED"));
   }
   
   return (output_probs[1] >= Inp_Min_ONNX_Probability);
}

//+------------------------------------------------------------------+
//| Correlation exposure filter (first entry only, non-directional). |
//| Returns true if another ToTheMoonKI instance has open positions on |
//| a correlated symbol (one that shares the base or quote currency  |
//| with the current symbol). Used to avoid stacking correlated      |
//| martingale baskets across charts. Only ToTheMoonKI positions count |
//| (deterministic per-symbol magic), and the current symbol's own   |
//| grid is excluded (handled by the normal grid logic).             |
//+------------------------------------------------------------------+
bool IsCorrelatedExposureOpen()
{
   if(!Inp_Use_Correlation_Filter) return false;

   string my_base   = SymbolInfoString(Symbol(), SYMBOL_CURRENCY_BASE);
   string my_profit = SymbolInfoString(Symbol(), SYMBOL_CURRENCY_PROFIT);
   if(my_base == "" && my_profit == "") return false; // currencies unknown: cannot determine correlation

   for(int i = 0; i < PositionsTotal(); i++)
   {
      if(!pos_info.SelectByIndex(i)) continue;

      string sym = pos_info.Symbol();
      if(sym == Symbol()) continue;                         // own symbol: handled by own grid logic
      if(pos_info.Magic() != GetMagicForSymbol(sym)) continue; // only ToTheMoonKI-managed positions

      string b = SymbolInfoString(sym, SYMBOL_CURRENCY_BASE);
      string p = SymbolInfoString(sym, SYMBOL_CURRENCY_PROFIT);
      if(b == "" && p == "") continue;

      if(b == my_base || b == my_profit || p == my_base || p == my_profit)
         return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Get Base Grid Step, dynamically calculated if ATR active         |
//+------------------------------------------------------------------+
double GetBaseStep()
{
   if(!Inp_Use_ATR_Step) return Inp_Grid_Step;
   double atr[];
   ArraySetAsSeries(atr, true);
   if(handle_atr != INVALID_HANDLE && CopyBuffer(handle_atr, 0, 1, 1, atr) > 0)
   {
      double atr_points = atr[0] / Point();
      double step = atr_points * Inp_ATR_Multiplier;
      // Floor at half the configured base step so a quiet market cannot collapse the grid
      // distance into a dense, fast-escalating martingale.
      double min_step = Inp_Grid_Step * 0.5;
      if(step < min_step) step = min_step;
      return step;
   }
   return Inp_Grid_Step;
}

//+------------------------------------------------------------------+
//| Validate indicator values before using them in signal logic       |
//+------------------------------------------------------------------+
bool IsIndicatorValueReady(double value)
{
   return (value > 0.0 && value != EMPTY_VALUE);
}

//+------------------------------------------------------------------+
//| Check if volatility spike is active based on ATR vs rolling avg  |
//+------------------------------------------------------------------+
bool IsVolSpikeActive()
{
   if(!Inp_Use_Vol_Filter || handle_vol_atr == INVALID_HANDLE) return false;
   double atr_vals[];
   ArraySetAsSeries(atr_vals, true);
   int copied = CopyBuffer(handle_vol_atr, 0, 1, 30, atr_vals);
   if(copied < 2) return true;

   double current_atr = atr_vals[0];
   double sum = 0.0;
   for(int i = 0; i < copied; i++)
   {
      sum += atr_vals[i];
   }
   double avg_atr = sum / copied;

   return (current_atr > avg_atr * Inp_Vol_ATR_Max_Multiplier);
}

//+------------------------------------------------------------------+
//| Normalize prices to the symbol's tick size and quote digits       |
//+------------------------------------------------------------------+
double NormalizePrice(double price)
{
   double tick_size = SymbolInfoDouble(Symbol(), SYMBOL_TRADE_TICK_SIZE);
   int digits = (int)SymbolInfoInteger(Symbol(), SYMBOL_DIGITS);
   if(tick_size > 0.0)
      price = MathRound(price / tick_size) * tick_size;
   return NormalizeDouble(price, digits);
}

//+------------------------------------------------------------------+
//| Check broker stop/freeze distance before moving break-even SL     |
//+------------------------------------------------------------------+
bool IsBreakEvenStopAllowed(ENUM_POSITION_TYPE type, double stop_loss, double bid, double ask)
{
   long stops_level = SymbolInfoInteger(Symbol(), SYMBOL_TRADE_STOPS_LEVEL);
   long freeze_level = SymbolInfoInteger(Symbol(), SYMBOL_TRADE_FREEZE_LEVEL);
   long min_level = (stops_level > freeze_level) ? stops_level : freeze_level;
   double min_distance = (double)min_level * Point();

   if(type == POSITION_TYPE_BUY)
      return (stop_loss < bid && (min_distance <= 0.0 || bid - stop_loss >= min_distance));

   return (stop_loss > ask && (min_distance <= 0.0 || stop_loss - ask >= min_distance));
}

//+------------------------------------------------------------------+
//| CTrade bool only validates the request; confirm server retcode    |
//+------------------------------------------------------------------+
bool IsTradeRetcodeSuccessful()
{
   // This EA only sends market orders and position close/modify requests, for which the server
   // returns DONE (or DONE_PARTIAL). TRADE_RETCODE_PLACED is for pending orders and does not mean
   // the market position is actually open/closed/modified, so it is intentionally not accepted.
   uint retcode = trade.ResultRetcode();
   return (retcode == TRADE_RETCODE_DONE ||
           retcode == TRADE_RETCODE_DONE_PARTIAL);
}

bool ClosePositionVerified(ulong ticket, string context)
{
   if(!trade.PositionClose(ticket) || !IsTradeRetcodeSuccessful())
   {
      PrintFormat("ERROR: %s failed to close position ticket %I64u. Retcode: %u",
                  context, ticket, trade.ResultRetcode());
      return false;
   }
   return true;
}

bool ClosePositionPartialVerified(ulong ticket, double volume, string context)
{
   if(!trade.PositionClosePartial(ticket, volume) || !IsTradeRetcodeSuccessful())
   {
      PrintFormat("ERROR: %s failed to partially close position ticket %I64u by %.2f lot. Retcode: %u",
                  context, ticket, volume, trade.ResultRetcode());
      return false;
   }
   return true;
}

bool ModifyPositionVerified(ulong ticket, double stop_loss, double take_profit, string context)
{
   if(!trade.PositionModify(ticket, stop_loss, take_profit) || !IsTradeRetcodeSuccessful())
   {
      PrintFormat("ERROR: %s failed to modify StopLoss for position ticket %I64u. SL: %.5f, TP: %.5f, Retcode: %u",
                  context, ticket, stop_loss, take_profit, trade.ResultRetcode());
      return false;
   }
   return true;
}

//+------------------------------------------------------------------+
//| Close all positions of the specified type                        |
//+------------------------------------------------------------------+
void CloseGrid(ENUM_POSITION_TYPE type)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(pos_info.SelectByIndex(i))
      {
         if(pos_info.Symbol() == Symbol() && pos_info.Magic() == calculated_magic && pos_info.PositionType() == type)
         {
            ulong ticket = pos_info.Ticket();
            ClosePositionVerified(ticket, "CloseGrid");
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Sum the commission charged for a position from its deal history  |
//| (POSITION_COMMISSION / CPositionInfo::Commission() is deprecated  |
//|  and always returns 0, so we read it from the deals instead)      |
//+------------------------------------------------------------------+
double GetPositionCommission(long position_id)
{
   // Reuse the value if it was already looked up during the current tick
   for(int i = 0; i < g_comm_cache_count; i++)
      if(g_comm_cache_id[i] == position_id)
         return g_comm_cache_val[i];

   double commission = 0.0;
   if(HistorySelectByPosition(position_id))
   {
      int deals = HistoryDealsTotal();
      for(int i = 0; i < deals; i++)
      {
         ulong deal_ticket = HistoryDealGetTicket(i);
         if(deal_ticket > 0)
            commission += HistoryDealGetDouble(deal_ticket, DEAL_COMMISSION);
      }
   }

   // Store in the per-tick cache (grows in blocks, never shrinks)
   if(ArraySize(g_comm_cache_id) <= g_comm_cache_count)
   {
      ArrayResize(g_comm_cache_id,  g_comm_cache_count + 16);
      ArrayResize(g_comm_cache_val, g_comm_cache_count + 16);
   }
   g_comm_cache_id[g_comm_cache_count]  = position_id;
   g_comm_cache_val[g_comm_cache_count] = commission;
   g_comm_cache_count++;

   return commission;
}

//+------------------------------------------------------------------+
//| Smart Loss pairing partial close execution                       |
//+------------------------------------------------------------------+
bool CheckSmartLossPairing(ENUM_POSITION_TYPE type)
{
   GridPosition pos_list[];
   int count = 0;
   
   for(int i = 0; i < PositionsTotal(); i++)
   {
      if(pos_info.SelectByIndex(i))
      {
         if(pos_info.Symbol() == Symbol() && pos_info.Magic() == calculated_magic && pos_info.PositionType() == type)
         {
            ArrayResize(pos_list, count + 1);
            double comm = GetPositionCommission(pos_info.Identifier());
            pos_list[count].ticket = pos_info.Ticket();
            pos_list[count].volume = pos_info.Volume();
            pos_list[count].profit = pos_info.Profit() + comm + pos_info.Swap();
            pos_list[count].entry_price = pos_info.PriceOpen();
            pos_list[count].open_time_msc = pos_info.TimeMsc();
            pos_list[count].commission = comm;
            count++;
         }
      }
   }
   
   if(count < 2) return false;
   
   // Sort oldest -> newest by open time (POSITION_TIME_MSC), ticket as tie-breaker.
   // More robust than ticket order alone for identifying the oldest/newest leg.
   for(int i = 0; i < count - 1; i++)
   {
      for(int j = i + 1; j < count; j++)
      {
         bool swap = (pos_list[i].open_time_msc > pos_list[j].open_time_msc) ||
                     (pos_list[i].open_time_msc == pos_list[j].open_time_msc && pos_list[i].ticket > pos_list[j].ticket);
         if(swap)
         {
            GridPosition temp = pos_list[i];
            pos_list[i] = pos_list[j];
            pos_list[j] = temp;
         }
      }
   }
   
   GridPosition oldest = pos_list[0];
   GridPosition newest = pos_list[count - 1];
   
   double initial_scaled_lot = GetScaledLot(Inp_Initial_Lot);
   if(oldest.volume <= 0.0) return false;
   
   // Limit the closed volume of the oldest trade to its actual open volume to avoid overestimating profit
   double close_volume = (initial_scaled_lot < oldest.volume) ? initial_scaled_lot : oldest.volume;
   double proportional_oldest_profit = (close_volume / oldest.volume) * oldest.profit;
   double joint_profit = newest.profit + proportional_oldest_profit;

   // The closing commission is not charged yet (deal history only holds the opening side).
   // Approximate it round-turn-symmetric from the opening commission of the closed volumes and
   // require the *net* result to clear Min_Profit, so a tight target cannot slip negative.
   // NOTE: this assumes per-side-symmetric commission. Brokers that charge the full round turn
   // at open make it slightly conservative; those charging it all at close, slightly optimistic.
   double est_close_cost = MathAbs(newest.commission) + MathAbs(oldest.commission) * (close_volume / oldest.volume);

   if(joint_profit - est_close_cost >= Min_Profit)
   {
      PrintFormat("Smart Loss pairing triggered for %s. Joint profit: %.2f USD. Closing newest ticket %I64u fully, then reducing oldest ticket %I64u by %.2f.",
                  (type == POSITION_TYPE_BUY ? "Buy" : "Sell"), joint_profit, newest.ticket, oldest.ticket, close_volume);

      // Close the profitable (newest) leg FIRST. Since joint_profit >= Min_Profit and the
      // oldest slice is a loss, newest.profit alone already exceeds Min_Profit. If the second
      // leg then fails we have only secured profit and the losing leg stays open for a retry,
      // instead of realising the loss with the offsetting profit still floating.
      if(!ClosePositionVerified(newest.ticket, "Smart Loss pairing"))
      {
         PrintFormat("Smart Loss pairing aborted for %s: could not close newest ticket %I64u; oldest ticket %I64u left untouched.",
                     (type == POSITION_TYPE_BUY ? "Buy" : "Sell"), newest.ticket, oldest.ticket);
         return false;
      }

      bool oldest_success = false;
      if(oldest.volume > close_volume + 0.001)
      {
         oldest_success = ClosePositionPartialVerified(oldest.ticket, close_volume, "Smart Loss pairing");
      }
      else
      {
         oldest_success = ClosePositionVerified(oldest.ticket, "Smart Loss pairing");
      }

      if(!oldest_success)
      {
         // Non-critical: profit is already secured; the losing leg simply remains in the grid
         // and will be reduced again by the normal pairing logic on a later tick.
         string warn_msg = StringFormat("Smart Loss closed newest ticket %I64u but could NOT reduce oldest ticket %I64u (Retcode: %u). Profit secured; losing leg stays open and will be retried.",
                                        newest.ticket, oldest.ticket, trade.ResultRetcode());
         Print("ToTheMoonKI v1.04: " + warn_msg);
      }
      return true;
   }
   
   return false;
}


//+------------------------------------------------------------------+
//| Emergency drawdown stop: close all own positions if floating     |
//| loss of THIS EA exceeds Inp_Max_DD_Percent of account balance    |
//+------------------------------------------------------------------+
bool CheckRiskStop()
{
   if(Inp_Max_DD_Percent <= 0) return false;

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   if(balance <= 0) return false;

   double floating = 0.0;
   int own = 0;
   for(int i = 0; i < PositionsTotal(); i++)
   {
      if(pos_info.SelectByIndex(i))
      {
         if(pos_info.Symbol() == Symbol() && pos_info.Magic() == calculated_magic)
         {
            floating += pos_info.Profit() + GetPositionCommission(pos_info.Identifier()) + pos_info.Swap();
            own++;
         }
      }
   }

   if(own == 0 || floating >= 0) return false;

   double dd_pct = (-floating / balance) * 100.0;
   if(dd_pct >= Inp_Max_DD_Percent)
   {
      PrintFormat("RISK STOP: Floating loss %.2f (%.2f%% of balance, limit %.2f%%). Closing all %d positions.",
                  floating, dd_pct, Inp_Max_DD_Percent, own);
      CloseGrid(POSITION_TYPE_BUY);
      CloseGrid(POSITION_TYPE_SELL);
      last_buy_close_time  = TimeCurrent();   // triggers existing wait filter
      last_sell_close_time = TimeCurrent();
      // NOTE: with Inp_Halt_After_DD_Stop=false (default) only the wait filter is set, so the EA
      // rebuilds a grid afterwards and can re-trigger this DD stop repeatedly. Set
      // Inp_Halt_After_DD_Stop=true for a hard stop that blocks new entries until manual restart.
      if(Inp_Halt_After_DD_Stop) g_trading_halted = true;
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Manage Take Profit and Pairing close for active grids           |
//+------------------------------------------------------------------+
void ManageGrids(double bid, double ask)
{
   // --- Buy Grid Management ---
   double total_buy_vol = 0;
   double buy_weighted_price = 0;
   int buy_count = 0;
   
   for(int i = 0; i < PositionsTotal(); i++)
   {
      if(pos_info.SelectByIndex(i))
      {
         if(pos_info.Symbol() == Symbol() && pos_info.Magic() == calculated_magic && pos_info.PositionType() == POSITION_TYPE_BUY)
         {
            total_buy_vol += pos_info.Volume();
            buy_weighted_price += pos_info.PriceOpen() * pos_info.Volume();
            buy_count++;
         }
      }
   }
   
   if(buy_count > 0)
   {
      double buy_avg_price = buy_weighted_price / total_buy_vol;
      
      // --- Buy Break Even Check
      if(Inp_Use_BreakEven && buy_count >= 2)
      {
         double be_trigger_price = buy_avg_price + Inp_BE_Trigger_Points * Point();
         double be_sl_price = NormalizePrice(buy_avg_price + Inp_BE_Points * Point());
         if(bid >= be_trigger_price)
         {
            if(!IsBreakEvenStopAllowed(POSITION_TYPE_BUY, be_sl_price, bid, ask))
            {
               if(Inp_Debug_Mode)
                  PrintFormat("[DEBUG] Buy BreakEven SL %.5f rejected by stop/freeze distance. Bid: %.5f, Ask: %.5f", be_sl_price, bid, ask);
            }
            else
            {
               for(int i = PositionsTotal() - 1; i >= 0; i--)
               {
                  if(pos_info.SelectByIndex(i))
                  {
                     if(pos_info.Symbol() == Symbol() && pos_info.Magic() == calculated_magic && pos_info.PositionType() == POSITION_TYPE_BUY)
                     {
                        double current_sl = pos_info.StopLoss();
                        if(MathAbs(current_sl - be_sl_price) > 2 * Point() && current_sl < be_sl_price)
                        {
                           ulong ticket = pos_info.Ticket();
                           ModifyPositionVerified(ticket, be_sl_price, pos_info.TakeProfit(), "Buy BreakEven");
                        }
                     }
                  }
               }
            }
         }
      }
      
      double tp_points = Inp_TakeProfit - (buy_count - 1) * 10;
      if(tp_points < 30) tp_points = 30;
      
      double buy_tp_price = buy_avg_price + tp_points * Point();
      
      bool buy_closed = false;
      if(buy_basket_close_pending || bid >= buy_tp_price)
      {
         buy_basket_close_pending = true;
         Print("Buy Grid Take Profit reached (or close pending). Closing basket.");
         CloseGrid(POSITION_TYPE_BUY);
         
         // Recheck if we still have any buy positions left
         int remaining_buy = 0;
         for(int i = 0; i < PositionsTotal(); i++)
         {
            if(pos_info.SelectByIndex(i))
            {
               if(pos_info.Symbol() == Symbol() && pos_info.Magic() == calculated_magic && pos_info.PositionType() == POSITION_TYPE_BUY)
               {
                  remaining_buy++;
               }
            }
         }
         if(remaining_buy == 0)
         {
            buy_basket_close_pending = false;
         }
         buy_closed = true;
      }
      
      if(!buy_closed && buy_count >= 2)
      {
         CheckSmartLossPairing(POSITION_TYPE_BUY);
      }
   }
   
   // --- Sell Grid Management ---
   double total_sell_vol = 0;
   double sell_weighted_price = 0;
   int sell_count = 0;
   
   for(int i = 0; i < PositionsTotal(); i++)
   {
      if(pos_info.SelectByIndex(i))
      {
         if(pos_info.Symbol() == Symbol() && pos_info.Magic() == calculated_magic && pos_info.PositionType() == POSITION_TYPE_SELL)
         {
            total_sell_vol += pos_info.Volume();
            sell_weighted_price += pos_info.PriceOpen() * pos_info.Volume();
            sell_count++;
         }
      }
   }
   
   if(sell_count > 0)
   {
      double sell_avg_price = sell_weighted_price / total_sell_vol;
      
      // --- Sell Break Even Check
      if(Inp_Use_BreakEven && sell_count >= 2)
      {
         double be_trigger_price = sell_avg_price - Inp_BE_Trigger_Points * Point();
         double be_sl_price = NormalizePrice(sell_avg_price - Inp_BE_Points * Point());
         if(ask <= be_trigger_price)
         {
            if(!IsBreakEvenStopAllowed(POSITION_TYPE_SELL, be_sl_price, bid, ask))
            {
               if(Inp_Debug_Mode)
                  PrintFormat("[DEBUG] Sell BreakEven SL %.5f rejected by stop/freeze distance. Bid: %.5f, Ask: %.5f", be_sl_price, bid, ask);
            }
            else
            {
               for(int i = PositionsTotal() - 1; i >= 0; i--)
               {
                  if(pos_info.SelectByIndex(i))
                  {
                     if(pos_info.Symbol() == Symbol() && pos_info.Magic() == calculated_magic && pos_info.PositionType() == POSITION_TYPE_SELL)
                     {
                        double current_sl = pos_info.StopLoss();
                        if(MathAbs(current_sl - be_sl_price) > 2 * Point() && (current_sl == 0 || current_sl > be_sl_price))
                        {
                           ulong ticket = pos_info.Ticket();
                           ModifyPositionVerified(ticket, be_sl_price, pos_info.TakeProfit(), "Sell BreakEven");
                        }
                     }
                  }
               }
            }
         }
      }
      
      double tp_points = Inp_TakeProfit - (sell_count - 1) * 10;
      if(tp_points < 30) tp_points = 30;
      
      double sell_tp_price = sell_avg_price - tp_points * Point();
      
      bool sell_closed = false;
      if(sell_basket_close_pending || ask <= sell_tp_price)
      {
         sell_basket_close_pending = true;
         Print("Sell Grid Take Profit reached (or close pending). Closing basket.");
         CloseGrid(POSITION_TYPE_SELL);
         
         // Recheck if we still have any sell positions left
         int remaining_sell = 0;
         for(int i = 0; i < PositionsTotal(); i++)
         {
            if(pos_info.SelectByIndex(i))
            {
               if(pos_info.Symbol() == Symbol() && pos_info.Magic() == calculated_magic && pos_info.PositionType() == POSITION_TYPE_SELL)
               {
                  remaining_sell++;
               }
            }
         }
         if(remaining_sell == 0)
         {
            sell_basket_close_pending = false;
         }
         sell_closed = true;
      }
      
      if(!sell_closed && sell_count >= 2)
      {
         CheckSmartLossPairing(POSITION_TYPE_SELL);
      }
   }
}

//+------------------------------------------------------------------+
//| Check signals and trigger entries/grid additions                 |
//+------------------------------------------------------------------+
void CheckEntries(double close1_up, double close1_down, double bid, double ask, double env_up, double env_down)
{
   double lowest_buy_price = 999999.0;
   double highest_sell_price = 0.0;
   int buy_count = 0;
   int sell_count = 0;
   bool vol_spike = IsVolSpikeActive();
   
   int highest_buy_level = g_highest_buy_level;
   int highest_sell_level = g_highest_sell_level;
   
   for(int i = 0; i < PositionsTotal(); i++)
   {
      if(pos_info.SelectByIndex(i))
      {
         if(pos_info.Symbol() == Symbol() && pos_info.Magic() == calculated_magic)
         {
            int level = GetPositionLevel(pos_info.Comment(), 1);
            
            if(pos_info.PositionType() == POSITION_TYPE_BUY)
            {
               buy_count++;
               if(level > highest_buy_level) highest_buy_level = level;
               if(pos_info.PriceOpen() < lowest_buy_price)
                  lowest_buy_price = pos_info.PriceOpen();
            }
            else if(pos_info.PositionType() == POSITION_TYPE_SELL)
            {
               sell_count++;
               if(level > highest_sell_level) highest_sell_level = level;
               if(pos_info.PriceOpen() > highest_sell_price)
                  highest_sell_price = pos_info.PriceOpen();
            }
         }
      }
   }
   
   // Update tracking in memory
   if(buy_count == 0) g_highest_buy_level = 0;
   else g_highest_buy_level = (int)MathMax(g_highest_buy_level, highest_buy_level);

   if(sell_count == 0) g_highest_sell_level = 0;
   else g_highest_sell_level = (int)MathMax(g_highest_sell_level, highest_sell_level);

   // The signal-state enums below are consumed only by the debug log, so skip the
   // entire computation (filter calls + correlation scan) when debug logging is off.
   if(Inp_Debug_Mode)
   {
   // Determine current buy state
   ESignalState current_buy_state = STATE_READY;
   if(buy_count == 0)
   {
      if(last_buy_close_time > 0 && TimeCurrent() - last_buy_close_time < Inp_Wait_Open_Equal_Orders * 60)
      {
         current_buy_state = STATE_WAIT_FILTER;
      }
      else if(close1_down >= env_down)
      {
         current_buy_state = STATE_OUTSIDE_ENVELOPE;
      }
      else if(!IsTrendBuyAllowed())
      {
         current_buy_state = STATE_BLOCKED_BY_TREND;
      }
      else if(!IsRSIBuyAllowed())
      {
         current_buy_state = STATE_BLOCKED_BY_RSI;
      }
      else if(!IsADXEntryAllowed())
      {
         current_buy_state = STATE_BLOCKED_BY_ADX;
      }
      else if(!IsEREntryAllowed())
      {
         current_buy_state = STATE_BLOCKED_BY_ER;
      }
      else if(IsCorrelatedExposureOpen())
      {
         current_buy_state = STATE_BLOCKED_BY_CORRELATION;
      }
   }
   else
   {
      int next_level = (int)MathMax(highest_buy_level + 1, buy_count + 1); // count floor: cap stays enforced even if comments are stripped
      double base_step = GetBaseStep();
      double current_step = base_step * MathPow(Inp_Step_Multiplier, next_level - 2) * Point();
      double target_price = lowest_buy_price - current_step;
      
      bool wait_blocked = false;
      if(Inp_Wait_Next_Lot > 0 && next_level >= Inp_Start_Wait_Next_Lot && next_level <= Inp_Stop_Wait_Next_Lot)
      {
         if(last_buy_grid_time > 0 && TimeCurrent() - last_buy_grid_time < Inp_Wait_Next_Lot * 60)
         {
            wait_blocked = true;
         }
      }
      
      if(ask > target_price)
      {
         current_buy_state = STATE_DISTANCE_NOT_MET;
      }
      else if(close1_down >= env_down)
      {
         current_buy_state = STATE_OUTSIDE_ENVELOPE;
      }
      else if(wait_blocked)
      {
         current_buy_state = STATE_WAIT_NEXT_LOT;
      }
      else if(vol_spike)
      {
         current_buy_state = STATE_BLOCKED_BY_VOLATILITY;
      }
   }

   // Determine current sell state
   ESignalState current_sell_state = STATE_READY;
   if(sell_count == 0)
   {
      if(last_sell_close_time > 0 && TimeCurrent() - last_sell_close_time < Inp_Wait_Open_Equal_Orders * 60)
      {
         current_sell_state = STATE_WAIT_FILTER;
      }
      else if(close1_up <= env_up)
      {
         current_sell_state = STATE_OUTSIDE_ENVELOPE;
      }
      else if(!IsTrendSellAllowed())
      {
         current_sell_state = STATE_BLOCKED_BY_TREND;
      }
      else if(!IsRSISellAllowed())
      {
         current_sell_state = STATE_BLOCKED_BY_RSI;
      }
      else if(!IsADXEntryAllowed())
      {
         current_sell_state = STATE_BLOCKED_BY_ADX;
      }
      else if(!IsEREntryAllowed())
      {
         current_sell_state = STATE_BLOCKED_BY_ER;
      }
      else if(IsCorrelatedExposureOpen())
      {
         current_sell_state = STATE_BLOCKED_BY_CORRELATION;
      }
   }
   else
   {
      int next_level = (int)MathMax(highest_sell_level + 1, sell_count + 1); // count floor: cap stays enforced even if comments are stripped
      double base_step = GetBaseStep();
      double current_step = base_step * MathPow(Inp_Step_Multiplier, next_level - 2) * Point();
      double target_price = highest_sell_price + current_step;
      
      bool wait_blocked = false;
      if(Inp_Wait_Next_Lot > 0 && next_level >= Inp_Start_Wait_Next_Lot && next_level <= Inp_Stop_Wait_Next_Lot)
      {
         if(last_sell_grid_time > 0 && TimeCurrent() - last_sell_grid_time < Inp_Wait_Next_Lot * 60)
         {
            wait_blocked = true;
         }
      }
      
      if(bid < target_price)
      {
         current_sell_state = STATE_DISTANCE_NOT_MET;
      }
      else if(close1_up <= env_up)
      {
         current_sell_state = STATE_OUTSIDE_ENVELOPE;
      }
      else if(wait_blocked)
      {
         current_sell_state = STATE_WAIT_NEXT_LOT;
      }
      else if(vol_spike)
      {
         current_sell_state = STATE_BLOCKED_BY_VOLATILITY;
      }
   }

      if(buy_count != prev_buy_count_log || sell_count != prev_sell_count_log ||
         current_buy_state != prev_buy_state || current_sell_state != prev_sell_state)
      {
         PrintFormat("[DEBUG] Signal State Changed - Buy Count: %d (State: %s), Sell Count: %d (State: %s)",
                     buy_count, GetStateString(current_buy_state),
                     sell_count, GetStateString(current_sell_state));

         prev_buy_count_log = buy_count;
         prev_sell_count_log = sell_count;
         prev_buy_state = current_buy_state;
         prev_sell_state = current_sell_state;
      }
   }

   // --- Buy Grid Logic
   if(buy_count == 0)
   {
      if(last_buy_close_time == 0 || TimeCurrent() - last_buy_close_time >= Inp_Wait_Open_Equal_Orders * 60)
      {
         if(close1_down < env_down && IsTrendBuyAllowed() && IsRSIBuyAllowed() && IsADXEntryAllowed() && IsEREntryAllowed() && !IsCorrelatedExposureOpen() && IsONNXEntryAllowed(true))
         {
            double lot = GetScaledLot(Inp_Initial_Lot);
            string order_comment = StringFormat("%s_L1", Inp_Order_Comment);
            if(trade.Buy(lot, Symbol(), ask, 0, 0, order_comment) && IsTradeRetcodeSuccessful())
            {
               last_buy_grid_time = TimeCurrent();
               g_highest_buy_level = 1;
               PrintFormat("First Buy entry triggered. Lot: %.2f", lot);
            }
            else
            {
               PrintFormat("ERROR: Failed to execute first Buy entry. Lot: %.2f, Price: %.5f. Retcode: %u", lot, ask, trade.ResultRetcode());
            }
         }
      }
   }
   else
   {
      int next_level = (int)MathMax(highest_buy_level + 1, buy_count + 1); // count floor: cap stays enforced even if comments are stripped
      double base_step = GetBaseStep();
      double current_step = base_step * MathPow(Inp_Step_Multiplier, next_level - 2) * Point();
      double target_price = lowest_buy_price - current_step;
      
      bool wait_blocked = false;
      if(Inp_Wait_Next_Lot > 0 && next_level >= Inp_Start_Wait_Next_Lot && next_level <= Inp_Stop_Wait_Next_Lot)
      {
         if(last_buy_grid_time > 0 && TimeCurrent() - last_buy_grid_time < Inp_Wait_Next_Lot * 60)
         {
            wait_blocked = true;
         }
      }
      
      if(!wait_blocked && ask <= target_price && close1_down < env_down
         && (Inp_Max_Grid_Levels == 0 || next_level <= Inp_Max_Grid_Levels)
         && !vol_spike && !buy_basket_close_pending)
      {
         double multiplier = MathPow(Inp_Next_Lot_Multiplier, next_level - 1);
         if(multiplier < 1.0) multiplier = 1.0;
         double initial_scaled_lot = GetScaledLot(Inp_Initial_Lot);
         double max_scaled_lot = GetScaledLot(Inp_Max_Lot);
         double next_lot = NormalizeLot(initial_scaled_lot * multiplier);
         if(next_lot > max_scaled_lot) next_lot = max_scaled_lot;
         string order_comment = StringFormat("%s_L%d", Inp_Order_Comment, next_level);
         if(trade.Buy(next_lot, Symbol(), ask, 0, 0, order_comment) && IsTradeRetcodeSuccessful())
         {
            last_buy_grid_time = TimeCurrent();
            g_highest_buy_level = next_level;
            PrintFormat("Buy Grid addition triggered. Level: %d, Lot: %.2f, Distance: %.1f pips", next_level, next_lot, (lowest_buy_price - ask) / (10.0 * Point()));
         }
         else
         {
            PrintFormat("ERROR: Failed to execute Buy grid addition. Level: %d, Lot: %.2f, Price: %.5f. Retcode: %u", next_level, next_lot, ask, trade.ResultRetcode());
         }
      }
   }
   
   // --- Sell Grid Logic
   if(sell_count == 0)
   {
      if(last_sell_close_time == 0 || TimeCurrent() - last_sell_close_time >= Inp_Wait_Open_Equal_Orders * 60)
      {
         if(close1_up > env_up && IsTrendSellAllowed() && IsRSISellAllowed() && IsADXEntryAllowed() && IsEREntryAllowed() && !IsCorrelatedExposureOpen() && IsONNXEntryAllowed(false))
         {
            double lot = GetScaledLot(Inp_Initial_Lot);
            string order_comment = StringFormat("%s_L1", Inp_Order_Comment);
            if(trade.Sell(lot, Symbol(), bid, 0, 0, order_comment) && IsTradeRetcodeSuccessful())
            {
               last_sell_grid_time = TimeCurrent();
               g_highest_sell_level = 1;
               PrintFormat("First Sell entry triggered. Lot: %.2f", lot);
            }
            else
            {
               PrintFormat("ERROR: Failed to execute first Sell entry. Lot: %.2f, Price: %.5f. Retcode: %u", lot, bid, trade.ResultRetcode());
            }
         }
      }
   }
   else
   {
      int next_level = (int)MathMax(highest_sell_level + 1, sell_count + 1); // count floor: cap stays enforced even if comments are stripped
      double base_step = GetBaseStep();
      double current_step = base_step * MathPow(Inp_Step_Multiplier, next_level - 2) * Point();
      double target_price = highest_sell_price + current_step;
      
      bool wait_blocked = false;
      if(Inp_Wait_Next_Lot > 0 && next_level >= Inp_Start_Wait_Next_Lot && next_level <= Inp_Stop_Wait_Next_Lot)
      {
         if(last_sell_grid_time > 0 && TimeCurrent() - last_sell_grid_time < Inp_Wait_Next_Lot * 60)
         {
            wait_blocked = true;
         }
      }
      
      if(!wait_blocked && bid >= target_price && close1_up > env_up
         && (Inp_Max_Grid_Levels == 0 || next_level <= Inp_Max_Grid_Levels)
         && !vol_spike && !sell_basket_close_pending)
      {
         double multiplier = MathPow(Inp_Next_Lot_Multiplier, next_level - 1);
         if(multiplier < 1.0) multiplier = 1.0;
         double initial_scaled_lot = GetScaledLot(Inp_Initial_Lot);
         double max_scaled_lot = GetScaledLot(Inp_Max_Lot);
         double next_lot = NormalizeLot(initial_scaled_lot * multiplier);
         if(next_lot > max_scaled_lot) next_lot = max_scaled_lot;
         string order_comment = StringFormat("%s_L%d", Inp_Order_Comment, next_level);
         if(trade.Sell(next_lot, Symbol(), bid, 0, 0, order_comment) && IsTradeRetcodeSuccessful())
         {
            last_sell_grid_time = TimeCurrent();
            g_highest_sell_level = next_level;
            PrintFormat("Sell Grid addition triggered. Level: %d, Lot: %.2f, Distance: %.1f pips", next_level, next_lot, (bid - highest_sell_price) / (10.0 * Point()));
         }
         else
         {
            PrintFormat("ERROR: Failed to execute Sell grid addition. Level: %d, Lot: %.2f, Price: %.5f. Retcode: %u", next_level, next_lot, bid, trade.ResultRetcode());
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Get Trend EMA value                                              |
//+------------------------------------------------------------------+
double GetTrendEMA()
{
   if(!Inp_Use_Trend_Filter || handle_trend == INVALID_HANDLE) return 0;
   double ma[];
   ArraySetAsSeries(ma, true);
   if(CopyBuffer(handle_trend, 0, 1, 1, ma) > 0) return ma[0];
   return 0;
}

//+------------------------------------------------------------------+
//| Get RSI value                                                    |
//+------------------------------------------------------------------+
double GetRSI()
{
   if(!Inp_Use_RSI_Filter || handle_rsi == INVALID_HANDLE) return 0;
   double rsi[];
   ArraySetAsSeries(rsi, true);
   if(CopyBuffer(handle_rsi, 0, 1, 1, rsi) > 0) return rsi[0];
   return 0;
}

//+------------------------------------------------------------------+
//| Get ADX main-line value for dashboard display                   |
//+------------------------------------------------------------------+
double GetADX()
{
   if(!Inp_Use_ADX_Filter || handle_adx == INVALID_HANDLE) return 0;
   double adx[];
   ArraySetAsSeries(adx, true);
   if(CopyBuffer(handle_adx, 0, 1, 1, adx) > 0) return adx[0];
   return 0;
}

//+------------------------------------------------------------------+
//| Get Efficiency Ratio value for dashboard display                |
//+------------------------------------------------------------------+
double GetER()
{
   if(!Inp_Use_ER_Filter) return 0;
   double er = CalcEfficiencyRatio(Inp_ER_Period, Inp_ER_Timeframe);
   return (er < 0.0) ? 0.0 : er;
}

//+------------------------------------------------------------------+
//| Create or update dashboard label                                 |
//+------------------------------------------------------------------+
void DrawDashboardLabel(string name, string text, int x, int y, int size, color col)
{
   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
   }
   // Always update position to prevent overlapping when settings or spacing change
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetString(0, name, OBJPROP_FONT, "Consolas");
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, size);
   ObjectSetInteger(0, name, OBJPROP_COLOR, col);
}

//+------------------------------------------------------------------+
//| Draw a line on the dashboard                                     |
//+------------------------------------------------------------------+
void DrawDashboardLine(int line_num, string text, color col)
{
   string name = "TTM_Line_" + IntegerToString(line_num);
   int x = 15;
   // Increased line spacing multiplier to 1.8 to prevent text overlapping
   int y = 15 + line_num * (int)(Inp_Dashboard_Font_Size * 1.8);
   DrawDashboardLabel(name, text, x, y, Inp_Dashboard_Font_Size, col);
}

//+------------------------------------------------------------------+
//| Update Chart Visual Comment                                      |
//+------------------------------------------------------------------+
void UpdateChartComment(double bid, double ask, int spread)
{
   if(!g_visuals_enabled) return;   // skip dashboard in non-visual tester/optimizer
   // Throttling: Only update dashboard once per second (1000 ms) to save CPU resources
   static ulong last_update_time = 0;
   ulong current_time = GetTickCount64();
   if(current_time - last_update_time < 1000) return;
   last_update_time = current_time;

   // Check counts and floating profit
   int buy_count = 0;
   int sell_count = 0;
   double buy_last_price = 0;
   double sell_last_price = 0;
   int buy_highest_level = 0;
   int sell_highest_level = 0;
   double floating = 0.0;

   for(int i = 0; i < PositionsTotal(); i++)
   {
      if(pos_info.SelectByIndex(i))
      {
         if(pos_info.Symbol() == Symbol() && pos_info.Magic() == calculated_magic)
         {
            floating += pos_info.Profit() + GetPositionCommission(pos_info.Identifier()) + pos_info.Swap();
            int level = GetPositionLevel(pos_info.Comment(), 1);

            if(pos_info.PositionType() == POSITION_TYPE_BUY)
            {
               buy_count++;
               if(level > buy_highest_level) buy_highest_level = level;
               if(buy_last_price == 0 || pos_info.PriceOpen() < buy_last_price)
                  buy_last_price = pos_info.PriceOpen();
            }
            else if(pos_info.PositionType() == POSITION_TYPE_SELL)
            {
               sell_count++;
               if(level > sell_highest_level) sell_highest_level = level;
               if(sell_last_price == 0 || pos_info.PriceOpen() > sell_last_price)
                  sell_last_price = pos_info.PriceOpen();
            }
         }
      }
   }
   
   // Check indicators and filters
   double env_up = GetEnvelopeUpper(1);
   double env_down = GetEnvelopeLower(1);
   bool envelopes_ready = IsIndicatorValueReady(env_up) && IsIndicatorValueReady(env_down);
   bool vol_spike = IsVolSpikeActive();
   double close1 = iClose(Symbol(), PERIOD_M5, 1);
   
   bool trend_buy = IsTrendBuyAllowed();
   bool trend_sell = IsTrendSellAllowed();
   bool rsi_buy = IsRSIBuyAllowed();
   bool rsi_sell = IsRSISellAllowed();
   bool adx_allowed = IsADXEntryAllowed();
   bool er_allowed = IsEREntryAllowed();
   bool corr_open = IsCorrelatedExposureOpen();
   
   double trend_ma = GetTrendEMA();
   double rsi_val = GetRSI();
   double adx_val = GetADX();
   double er_val = GetER();
   
   string buy_status = "Waiting for signal";
   string sell_status = "Waiting for signal";
   
   color buy_col = clrOrange;
   color sell_col = clrOrange;
   
   // Check filters/reasons for not trading
   if(!envelopes_ready)
   {
      buy_status = "Waiting for Envelope data";
      sell_status = "Waiting for Envelope data";
      buy_col = clrOrange;
      sell_col = clrOrange;
   }
   else if(spread > Inp_Spread_Max)
   {
      buy_status = StringFormat("Spread too high (%d > %.1f)", spread, Inp_Spread_Max);
      sell_status = StringFormat("Spread too high (%d > %.1f)", spread, Inp_Spread_Max);
      buy_col = clrRed;
      sell_col = clrRed;
   }
   else
   {
      // Buy checks
      if(buy_count == 0)
      {
         if(last_buy_close_time > 0 && TimeCurrent() - last_buy_close_time < Inp_Wait_Open_Equal_Orders * 60)
         {
            int remaining = (int)(Inp_Wait_Open_Equal_Orders * 60 - (TimeCurrent() - last_buy_close_time));
            buy_status = StringFormat("Wait filter active (%d sec left)", remaining);
            buy_col = clrOrange;
         }
         else if(close1 >= env_down)
         {
            buy_status = StringFormat("Price above Lower Envelope (%.5f >= %.5f)", close1, env_down);
            buy_col = clrLightCoral;
         }
         else if(!trend_buy)
         {
            buy_status = StringFormat("Blocked by Trend Filter (Close1: %.5f <= EMA: %.5f)", close1, trend_ma);
            buy_col = clrLightCoral;
         }
         else if(!rsi_buy)
         {
            buy_status = StringFormat("Blocked by RSI Filter (RSI: %.1f >= Oversold: %.1f)", rsi_val, Inp_RSI_Oversold);
            buy_col = clrLightCoral;
         }
         else if(!adx_allowed)
         {
            buy_status = StringFormat("Blocked by ADX Filter (ADX: %.1f >= Max: %.1f)", adx_val, Inp_ADX_Max_Level);
            buy_col = clrLightCoral;
         }
         else if(!er_allowed)
         {
            buy_status = StringFormat("Blocked by Efficiency Ratio Filter (ER: %.2f >= Max: %.2f)", er_val, Inp_ER_Max_Level);
            buy_col = clrLightCoral;
         }
         else if(corr_open)
         {
            buy_status = "Blocked by Correlation Filter (correlated pair has open trades)";
            buy_col = clrLightCoral;
         }
         else
         {
            buy_status = "Ready / Triggering buy signal";
            buy_col = clrLime;
         }
      }
      else
      {
         int next_level = (int)MathMax(buy_highest_level + 1, buy_count + 1);
         double base_step = GetBaseStep();
         double current_step = base_step * MathPow(Inp_Step_Multiplier, next_level - 2) * Point();
         double target_price = buy_last_price - current_step;
         
         bool wait_blocked = false;
         int remaining = 0;
         if(Inp_Wait_Next_Lot > 0 && next_level >= Inp_Start_Wait_Next_Lot && next_level <= Inp_Stop_Wait_Next_Lot)
         {
            if(last_buy_grid_time > 0 && TimeCurrent() - last_buy_grid_time < Inp_Wait_Next_Lot * 60)
            {
               wait_blocked = true;
               remaining = (int)(Inp_Wait_Next_Lot * 60 - (TimeCurrent() - last_buy_grid_time));
            }
         }
         
         if(ask > target_price)
         {
            buy_status = StringFormat("Grid active (Level %d). Next buy at %.5f (current ask: %.5f, needs to drop %.1f pips)", 
                                      buy_count, target_price, ask, (ask - target_price) / (10.0 * Point()));
            buy_col = clrYellow;
         }
         else if(close1 >= env_down)
         {
            buy_status = StringFormat("Grid active (Level %d). Price above Lower Envelope (%.5f >= %.5f)", buy_count, close1, env_down);
            buy_col = clrYellow;
         }
         else if(wait_blocked)
         {
            buy_status = StringFormat("Grid active (Level %d). Blocked by Wait-Next-Lot (%d sec left)", buy_count, remaining);
            buy_col = clrOrange;
         }
         else if(vol_spike)
         {
            buy_status = StringFormat("Grid active (Level %d). Blocked by Volatility Filter (ATR spike)", buy_count);
            buy_col = clrOrange;
         }
         else
         {
            buy_status = StringFormat("Grid active (Level %d). Distance met, execution pending.", buy_count);
            buy_col = clrLime;
         }
      }
      
      // Sell checks
      if(sell_count == 0)
      {
         if(last_sell_close_time > 0 && TimeCurrent() - last_sell_close_time < Inp_Wait_Open_Equal_Orders * 60)
         {
            int remaining = (int)(Inp_Wait_Open_Equal_Orders * 60 - (TimeCurrent() - last_sell_close_time));
            sell_status = StringFormat("Wait filter active (%d sec left)", remaining);
            sell_col = clrOrange;
         }
         else if(close1 <= env_up)
         {
            sell_status = StringFormat("Price below Upper Envelope (%.5f <= %.5f)", close1, env_up);
            sell_col = clrLightCoral;
         }
         else if(!trend_sell)
         {
            sell_status = StringFormat("Blocked by Trend Filter (Close1: %.5f >= EMA: %.5f)", close1, trend_ma);
            sell_col = clrLightCoral;
         }
         else if(!rsi_sell)
         {
            sell_status = StringFormat("Blocked by RSI Filter (RSI: %.1f <= Overbought: %.1f)", rsi_val, Inp_RSI_Overbought);
            sell_col = clrLightCoral;
         }
         else if(!adx_allowed)
         {
            sell_status = StringFormat("Blocked by ADX Filter (ADX: %.1f >= Max: %.1f)", adx_val, Inp_ADX_Max_Level);
            sell_col = clrLightCoral;
         }
         else if(!er_allowed)
         {
            sell_status = StringFormat("Blocked by Efficiency Ratio Filter (ER: %.2f >= Max: %.2f)", er_val, Inp_ER_Max_Level);
            sell_col = clrLightCoral;
         }
         else if(corr_open)
         {
            sell_status = "Blocked by Correlation Filter (correlated pair has open trades)";
            sell_col = clrLightCoral;
         }
         else
         {
            sell_status = "Ready / Triggering sell signal";
            sell_col = clrLime;
         }
      }
      else
      {
         int next_level = (int)MathMax(sell_highest_level + 1, sell_count + 1);
         double base_step = GetBaseStep();
         double current_step = base_step * MathPow(Inp_Step_Multiplier, next_level - 2) * Point();
         double target_price = sell_last_price + current_step;
         
         bool wait_blocked = false;
         int remaining = 0;
         if(Inp_Wait_Next_Lot > 0 && next_level >= Inp_Start_Wait_Next_Lot && next_level <= Inp_Stop_Wait_Next_Lot)
         {
            if(last_sell_grid_time > 0 && TimeCurrent() - last_sell_grid_time < Inp_Wait_Next_Lot * 60)
            {
               wait_blocked = true;
               remaining = (int)(Inp_Wait_Next_Lot * 60 - (TimeCurrent() - last_sell_grid_time));
            }
         }
         
         if(bid < target_price)
         {
            sell_status = StringFormat("Grid active (Level %d). Next sell at %.5f (current bid: %.5f, needs to rise %.1f pips)", 
                                       sell_count, target_price, bid, (target_price - bid) / (10.0 * Point()));
            sell_col = clrYellow;
         }
         else if(close1 <= env_up)
         {
            sell_status = StringFormat("Grid active (Level %d). Price below Upper Envelope (%.5f <= %.5f)", sell_count, close1, env_up);
            sell_col = clrYellow;
         }
         else if(wait_blocked)
         {
            sell_status = StringFormat("Grid active (Level %d). Blocked by Wait-Next-Lot (%d sec left)", sell_count, remaining);
            sell_col = clrOrange;
         }
         else if(vol_spike)
         {
            sell_status = StringFormat("Grid active (Level %d). Blocked by Volatility Filter (ATR spike)", sell_count);
            sell_col = clrOrange;
         }
         else
         {
            sell_status = StringFormat("Grid active (Level %d). Distance met, execution pending.", sell_count);
            sell_col = clrLime;
         }
      }
   }
   
   // Calculate risk values for dashboard
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double dd_pct = (balance > 0 && floating < 0) ? (-floating / balance) * 100.0 : 0.0;

   string risk_status = "";
   color risk_col = clrWhite;
   if(g_trading_halted)
   {
      risk_status = "HALTED: Emergency DD Stop triggered! Restart EA to resume.";
      risk_col = clrRed;
   }
   else
   {
      string dd_info = "";
      if(Inp_Max_DD_Percent > 0)
      {
         dd_info = StringFormat("DD: %.2f%% (Limit: %.2f%%, Loss: %.2f USD)", dd_pct, Inp_Max_DD_Percent, floating);
         if(dd_pct >= Inp_Max_DD_Percent * 0.7) risk_col = clrOrange;
      }
      else
      {
         dd_info = "DD Stop: Off";
         risk_col = clrDarkGray;
      }
      
      string level_info = "";
      if(Inp_Max_Grid_Levels > 0)
      {
         level_info = StringFormat("Max Level: %d", Inp_Max_Grid_Levels);
      }
      else
      {
         level_info = "Max Level: Off";
      }
      
      risk_status = StringFormat("Risk Protection: %s | %s", dd_info, level_info);
   }

   // Draw graphical dashboard instead of small comment
   DrawDashboardLine(0,  "==========================================================================================", clrGray);
   DrawDashboardLine(1,  "                  TO THE MOON EA v1.04 - (c) by Thomas Nickel", clrLime);
   DrawDashboardLine(2,  "==========================================================================================", clrGray);
   DrawDashboardLine(3,  StringFormat(" Magic Number: %I64u", calculated_magic), clrWhite);
   
   color sp_col = (spread > Inp_Spread_Max) ? clrRed : clrWhite;
   DrawDashboardLine(4,  StringFormat(" Spread:       %d / %.1f Max", spread, Inp_Spread_Max), sp_col);
   DrawDashboardLine(5,  StringFormat(" Initial Lot:  %.2f (Min: %.2f, Max: %.2f)", Inp_Initial_Lot, Inp_Min_Lot, Inp_Max_Lot), clrWhite);
   DrawDashboardLine(6,  "------------------------------------------------------------------------------------------", clrDarkGray);
   DrawDashboardLine(7,  StringFormat(" Buy Grid Level: %d", buy_count), clrWhite);
   DrawDashboardLine(8,  " Buy Status:     " + buy_status, buy_col);
   DrawDashboardLine(9,  "------------------------------------------------------------------------------------------", clrDarkGray);
   DrawDashboardLine(10, StringFormat(" Sell Grid Level: %d", sell_count), clrWhite);
   DrawDashboardLine(11, " Sell Status:     " + sell_status, sell_col);
   DrawDashboardLine(12, "------------------------------------------------------------------------------------------", clrDarkGray);
   DrawDashboardLine(13, " " + risk_status, risk_col);
   DrawDashboardLine(14, "==========================================================================================", clrGray);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   double bid = SymbolInfoDouble(Symbol(), SYMBOL_BID);
   double ask = SymbolInfoDouble(Symbol(), SYMBOL_ASK);
   int spread = (int)SymbolInfoInteger(Symbol(), SYMBOL_SPREAD);

   g_comm_cache_count = 0;   // reset per-tick commission cache

   if(CheckRiskStop())
   {
      UpdateChartComment(bid, ask, spread);
      return;   // this tick: only close, no further actions
   }
   
   ManageGrids(bid, ask);
   
   int current_buy_count = 0;
   int current_sell_count = 0;
   for(int i = 0; i < PositionsTotal(); i++)
   {
      if(pos_info.SelectByIndex(i))
      {
         if(pos_info.Symbol() == Symbol() && pos_info.Magic() == calculated_magic)
         {
            if(pos_info.PositionType() == POSITION_TYPE_BUY) current_buy_count++;
            else if(pos_info.PositionType() == POSITION_TYPE_SELL) current_sell_count++;
         }
      }
   }
   
   if(current_buy_count == 0) buy_basket_close_pending = false;
   if(current_sell_count == 0) sell_basket_close_pending = false;
   
   if(prev_buy_count > 0 && current_buy_count == 0)
   {
      last_buy_close_time = TimeCurrent();
      Print("ToTheMoonKI v1.04: Buy basket closed. Setting wait filter.");
   }
   if(prev_sell_count > 0 && current_sell_count == 0)
   {
      last_sell_close_time = TimeCurrent();
      Print("ToTheMoonKI v1.04: Sell basket closed. Setting wait filter.");
   }
   
   prev_buy_count = current_buy_count;
   prev_sell_count = current_sell_count;
   
   // Update dashboard (throttled to 1x/sec internally; skipped in non-visual tester)
   UpdateChartComment(bid, ask, spread);

   // Draw the exact asymmetric Envelope lines on the chart (skipped in non-visual tester)
   DrawEnvelopeLines(false);
   
   if(!IsNewBar()) return;
   
   if(spread > Inp_Spread_Max)
   {
      if(Inp_Debug_Mode)
      {
         PrintFormat("[DEBUG] Spread (%d) exceeds max allowed (%.1f). Skipping entry check.", spread, Inp_Spread_Max);
      }
      return;
   }
   
   double env_up = GetEnvelopeUpper(1);
   double env_down = GetEnvelopeLower(1);
   
   // high1 and low1 are used strictly for debug logging below, not for entry signals
   double high1 = iHigh(Symbol(), PERIOD_M5, 1);
   double low1 = iLow(Symbol(), PERIOD_M5, 1);
   double close1 = iClose(Symbol(), PERIOD_M5, 1);
   
   datetime t = iTime(Symbol(), PERIOD_M5, 1);
   if(Inp_Debug_Mode && t < D'2024.01.10 00:00')
   {
      PrintFormat("[DEBUG] Time: %s | Close1: %.5f | High1: %.5f | Low1: %.5f | EnvUp: %.5f | EnvDown: %.5f", 
                  TimeToString(t), close1, high1, low1, env_up, env_down);
   }
   
   if(!IsIndicatorValueReady(env_up) || !IsIndicatorValueReady(env_down)) return;
   
   if(!g_trading_halted)
   {
      CheckEntries(close1, close1, bid, ask, env_up, env_down);
   }
}

//+------------------------------------------------------------------+
//| Draw exact asymmetric Envelope lines on chart                   |
//+------------------------------------------------------------------+
void DrawEnvelopeLines(bool force_redraw)
{
   if(!g_visuals_enabled) return;   // skip chart drawing in non-visual tester/optimizer
   if(handle_up == INVALID_HANDLE || handle_down == INVALID_HANDLE) return;
   
   static datetime last_drawn_bar_up = 0;
   static datetime last_drawn_bar_down = 0;
   
   ENUM_TIMEFRAMES tf_down = (Values_Envelopes_Lower == 0) ? TimeFrame_Envelopes : TimeFrame_Envelopes_Lower;
   datetime current_bar_up = iTime(Symbol(), TimeFrame_Envelopes, 0);
   datetime current_bar_down = iTime(Symbol(), tf_down, 0);
   
   int bars_to_draw = 100; // Visualizing the last 100 bars of the indicator timeframe
   
   bool redraw_up = (current_bar_up != last_drawn_bar_up) || force_redraw;
   bool redraw_down = (current_bar_down != last_drawn_bar_down) || force_redraw;
   
   // --- Upper Envelope Band (TimeFrame_Envelopes)
   int start_up = redraw_up ? 0 : 0;
   int end_up = redraw_up ? bars_to_draw - 1 : 0;
   
   double val_up[];
   ArraySetAsSeries(val_up, true);
   int req_up = end_up - start_up + 2;
   if(CopyBuffer(handle_up, 0, start_up, req_up, val_up) >= req_up)
   {
      if(redraw_up)
      {
         ObjectsDeleteAll(0, "TTM_Env_Up_");
         if(current_bar_up > 0)
         {
            last_drawn_bar_up = current_bar_up;
         }
      }
      for(int i = start_up; i <= end_up; i++)
      {
         datetime t1 = iTime(Symbol(), TimeFrame_Envelopes, i);
         datetime t2 = iTime(Symbol(), TimeFrame_Envelopes, i+1);
         if(t1 <= 0 || t2 <= 0) continue;
         
         string name_up = StringFormat("TTM_Env_Up_%d", i);
         double p1 = val_up[i - start_up];
         double p2 = val_up[i - start_up + 1];
         
         if(ObjectFind(0, name_up) < 0)
         {
            ObjectCreate(0, name_up, OBJ_TREND, 0, t2, p2, t1, p1);
            ObjectSetInteger(0, name_up, OBJPROP_RAY_RIGHT, false);
            ObjectSetInteger(0, name_up, OBJPROP_COLOR, clrDodgerBlue);
            ObjectSetInteger(0, name_up, OBJPROP_STYLE, STYLE_SOLID);
            ObjectSetInteger(0, name_up, OBJPROP_SELECTABLE, false);
            ObjectSetInteger(0, name_up, OBJPROP_HIDDEN, true);
         }
         else
         {
            ObjectSetDouble(0, name_up, OBJPROP_PRICE, 0, p2);
            ObjectSetDouble(0, name_up, OBJPROP_PRICE, 1, p1);
            ObjectSetInteger(0, name_up, OBJPROP_TIME, 0, t2);
            ObjectSetInteger(0, name_up, OBJPROP_TIME, 1, t1);
         }
         ObjectSetInteger(0, name_up, OBJPROP_WIDTH, Inp_Envelope_Width);
      }
   }
   
   // --- Lower Envelope Band (TimeFrame_Envelopes_Lower)
   int start_down = redraw_down ? 0 : 0;
   int end_down = redraw_down ? bars_to_draw - 1 : 0;
   
   double val_down[];
   ArraySetAsSeries(val_down, true);
   int req_down = end_down - start_down + 2;
   if(CopyBuffer(handle_down, 1, start_down, req_down, val_down) >= req_down)
   {
      if(redraw_down)
      {
         ObjectsDeleteAll(0, "TTM_Env_Down_");
         if(current_bar_down > 0)
         {
            last_drawn_bar_down = current_bar_down;
         }
      }
      for(int i = start_down; i <= end_down; i++)
      {
         datetime t1 = iTime(Symbol(), tf_down, i);
         datetime t2 = iTime(Symbol(), tf_down, i+1);
         if(t1 <= 0 || t2 <= 0) continue;
         
         string name_down = StringFormat("TTM_Env_Down_%d", i);
         double p1 = val_down[i - start_down];
         double p2 = val_down[i - start_down + 1];
         
         if(ObjectFind(0, name_down) < 0)
         {
            ObjectCreate(0, name_down, OBJ_TREND, 0, t2, p2, t1, p1);
            ObjectSetInteger(0, name_down, OBJPROP_RAY_RIGHT, false);
            ObjectSetInteger(0, name_down, OBJPROP_COLOR, clrOrangeRed);
            ObjectSetInteger(0, name_down, OBJPROP_STYLE, STYLE_SOLID);
            ObjectSetInteger(0, name_down, OBJPROP_SELECTABLE, false);
            ObjectSetInteger(0, name_down, OBJPROP_HIDDEN, true);
         }
         else
         {
            ObjectSetDouble(0, name_down, OBJPROP_PRICE, 0, p2);
            ObjectSetDouble(0, name_down, OBJPROP_PRICE, 1, p1);
            ObjectSetInteger(0, name_down, OBJPROP_TIME, 0, t2);
            ObjectSetInteger(0, name_down, OBJPROP_TIME, 1, t1);
         }
         ObjectSetInteger(0, name_down, OBJPROP_WIDTH, Inp_Envelope_Width);
      }
   }
}
