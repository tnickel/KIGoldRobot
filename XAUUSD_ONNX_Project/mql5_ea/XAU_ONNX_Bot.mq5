//+------------------------------------------------------------------+
//|                                               XAU_ONNX_Bot.mq5   |
//|                                  Copyright 2026, Antigravity AI  |
//|                               https://github.com/google-deepmind |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Antigravity AI"
#property link      "https://github.com/google-deepmind"
#property version   "1.00"
#property description "Machine Learning Algorithmic Trading Robot for XAUUSD (Gold)"
#property description "Natively executes a RandomForest ONNX model for H1 predictions."

// Include trading class
#include <Trade\Trade.mqh>

//+------------------------------------------------------------------+
//| Resource Definition                                              |
//+------------------------------------------------------------------+
// The ONNX model file must be in the same folder as this EA
#resource "model.onnx" as uchar model_onnx_data[]

//+------------------------------------------------------------------+
//| Input Parameters                                                 |
//+------------------------------------------------------------------+
input group "--- Risk & Money Management ---"
input double   InpLotSize                 = 0.1;       // Fixed Lot Size (if dynamic risk disabled)
input bool     InpUseDynamicRisk          = false;     // Enable Dynamic Risk (% of Equity)
input double   InpRiskPercent             = 1.0;       // Risk percentage of Equity per trade
input double   InpStopLossATRMultiplier   = 2.0;       // Stop Loss ATR Multiplier
input double   InpTakeProfitATRMultiplier = 3.0;       // Take Profit ATR Multiplier
input double   InpCommissionPerLot        = 6.0;       // Round-turn commission per 1 Lot (in $)

input group "--- Model Strategy Settings ---"
input ENUM_TIMEFRAMES InpTimeFrame               = PERIOD_M15;     // Strategy Execution Timeframe
input double   InpMinProbability          = 0.55;      // Minimum model confidence (0.50 to 1.00)
input bool     InpCloseOnOppositeSignal   = true;      // Close active position on opposite signal

input group "--- Execution Filters ---"
input int      InpMaxSpreadPoints         = 50;        // Maximum allowed spread in Points ($0.50)
input ulong    InpMagicNumber             = 881209;    // Unique Magic Number for this EA

//+------------------------------------------------------------------+
//| Global Variables & Handles                                       |
//+------------------------------------------------------------------+
long     onnx_handle = INVALID_HANDLE;
CTrade   trade;

// Indicator Handles
int      handle_atr     = INVALID_HANDLE;
int      handle_rsi     = INVALID_HANDLE;
int      handle_ema20   = INVALID_HANDLE;
int      handle_ema50   = INVALID_HANDLE;
int      handle_sma200  = INVALID_HANDLE;
int      handle_macd    = INVALID_HANDLE;

// Model tensor definitions
#define INPUT_FEATURES_COUNT 10
#define OUTPUT_CLASSES_COUNT 3

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   // 1. Initialize Trade Magic Number
   trade.SetExpertMagicNumber(InpMagicNumber);
   
   // 2. Validate inputs
   if(InpMinProbability < 0.34 || InpMinProbability > 1.0)
   {
      Alert("Error: Min Probability must be between 0.34 and 1.00.");
      return(INIT_PARAMETERS_INCORRECT);
   }
   
   // 3. Create ONNX Session from resource buffer
   onnx_handle = OnnxCreateFromBuffer(model_onnx_data, ONNX_DEFAULT);
   if(onnx_handle == INVALID_HANDLE)
   {
      Print("ONNX Initialization failed. Error code: ", GetLastError());
      return(INIT_FAILED);
   }
   
   // 4. Set ONNX Input & Output Shapes
   // Input shape: [1, 10] -> Batch size = 1, Features = 10
   const long input_shape[] = {1, INPUT_FEATURES_COUNT};
   if(!OnnxSetInputShape(onnx_handle, 0, input_shape))
   {
      Print("ONNX: Failed to set input shape. Error code: ", GetLastError());
      OnnxRelease(onnx_handle);
      return(INIT_FAILED);
   }
   
   // Output index 0 shape: [1] -> Class Label (int64)
   const long label_shape[] = {1};
   if(!OnnxSetOutputShape(onnx_handle, 0, label_shape))
   {
      Print("ONNX: Failed to set output shape for Labels (index 0). Error code: ", GetLastError());
      OnnxRelease(onnx_handle);
      return(INIT_FAILED);
   }
   
   // Output index 1 shape: [1, 3] -> Class Probabilities (float)
   const long prob_shape[] = {1, OUTPUT_CLASSES_COUNT};
   if(!OnnxSetOutputShape(onnx_handle, 1, prob_shape))
   {
      Print("ONNX: Failed to set output shape for Probabilities (index 1). Error code: ", GetLastError());
      OnnxRelease(onnx_handle);
      return(INIT_FAILED);
   }
   
   // 5. Initialize Indicator Handles (aligned with Python feature definitions)
   handle_atr    = iATR(Symbol(), InpTimeFrame, 14);
   handle_rsi    = iRSI(Symbol(), InpTimeFrame, 14, PRICE_CLOSE);
   handle_ema20  = iMA(Symbol(), InpTimeFrame, 20, 0, MODE_EMA, PRICE_CLOSE);
   handle_ema50  = iMA(Symbol(), InpTimeFrame, 50, 0, MODE_EMA, PRICE_CLOSE);
   handle_sma200 = iMA(Symbol(), InpTimeFrame, 200, 0, MODE_SMA, PRICE_CLOSE);
   handle_macd   = iMACD(Symbol(), InpTimeFrame, 12, 26, 9, PRICE_CLOSE);
   
   if(handle_atr == INVALID_HANDLE || handle_rsi == INVALID_HANDLE ||
      handle_ema20 == INVALID_HANDLE || handle_ema50 == INVALID_HANDLE ||
      handle_sma200 == INVALID_HANDLE || handle_macd == INVALID_HANDLE)
   {
      Print("Failed to initialize indicator handles. Error code: ", GetLastError());
      OnnxRelease(onnx_handle);
      return(INIT_FAILED);
   }
   
   // Calculate and log the break-even markup requirements
   double contract_size = SymbolInfoDouble(Symbol(), SYMBOL_TRADE_CONTRACT_SIZE);
   double point_val = SymbolInfoDouble(Symbol(), SYMBOL_POINT);
   double break_even_price_diff = InpCommissionPerLot / contract_size;
   double commission_points = break_even_price_diff / point_val;
   
   Print("XAUUSD ONNX Bot initialized successfully.");
   Print("  Commission Point Offset: ", DoubleToString(commission_points, 1), " points (~$", DoubleToString(break_even_price_diff, 2), ")");
   
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   // Release ONNX session handle
   if(onnx_handle != INVALID_HANDLE)
   {
      OnnxRelease(onnx_handle);
      onnx_handle = INVALID_HANDLE;
   }
   
   // Release indicator handles
   IndicatorRelease(handle_atr);
   IndicatorRelease(handle_rsi);
   IndicatorRelease(handle_ema20);
   IndicatorRelease(handle_ema50);
   IndicatorRelease(handle_sma200);
   IndicatorRelease(handle_macd);
}

//+------------------------------------------------------------------+
//| Check if a new bar has opened                                    |
//+------------------------------------------------------------------+
bool IsNewBar()
{
   static datetime last_bar_time = 0;
   datetime current_bar_time = iTime(Symbol(), InpTimeFrame, 0);
   
   if(current_bar_time == 0)
      return false;
      
   if(current_bar_time != last_bar_time)
   {
      // First run check
      if(last_bar_time == 0)
      {
         last_bar_time = current_bar_time;
         return false; // Skip execution on first attachment to avoid trading historical signals
      }
      last_bar_time = current_bar_time;
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Count active positions for this EA's symbol and magic number      |
//+------------------------------------------------------------------+
int CountActivePositions(int &position_type)
{
   int count = 0;
   position_type = -1; // -1 = None, 0 = Buy, 1 = Sell
   
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(PositionGetSymbol(i) == Symbol() && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
      {
         count++;
         position_type = (int)PositionGetInteger(POSITION_TYPE);
      }
   }
   return count;
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Only execute predictions and checks at the open of a new bar
   if(!IsNewBar())
      return;
      
   // 1. Check Spread Filter
   int current_spread = (int)SymbolInfoInteger(Symbol(), SYMBOL_SPREAD);
   if(current_spread > InpMaxSpreadPoints)
   {
      Print("Trade skipped: current spread (", current_spread, ") exceeds max spread (", InpMaxSpreadPoints, ").");
      return;
   }
   
   // 2. Fetch completed bar price and indicators (Index 1)
   MqlRates rates[];
   if(CopyRates(Symbol(), InpTimeFrame, 1, 20, rates) < 20)
   {
      Print("Failed to copy bar data. Not enough bars loaded.");
      return;
   }
   
   double atr_val[1], rsi_val[1], ema20_val[1], ema50_val[1], sma200_val[1], macd_main[1], macd_sig[1];
   
   if(CopyBuffer(handle_atr, 0, 1, 1, atr_val) < 1 ||
      CopyBuffer(handle_rsi, 0, 1, 1, rsi_val) < 1 ||
      CopyBuffer(handle_ema20, 0, 1, 1, ema20_val) < 1 ||
      CopyBuffer(handle_ema50, 0, 1, 1, ema50_val) < 1 ||
      CopyBuffer(handle_sma200, 0, 1, 1, sma200_val) < 1 ||
      CopyBuffer(handle_macd, 0, 1, 1, macd_main) < 1 ||
      CopyBuffer(handle_macd, 1, 1, 1, macd_sig) < 1)
   {
      Print("Failed to copy indicator buffer values.");
      return;
   }
   
   // Index 19 is the last completed bar in our 20-length rates copy (Index 1)
   double atr_v = atr_val[0];
   double rsi_v = rsi_val[0];
   
   if(atr_v <= 0.0)
   {
      Print("ATR is 0 or negative. Calculation skipped.");
      return;
   }
   
   // 3. Compute Volume Ratio (current real volume / average of last 20)
   double volume_sum = 0;
   for(int i = 0; i < 20; i++)
   {
      volume_sum += (double)rates[i].real_volume;
   }
   double volume_avg = volume_sum / 20.0;
   double vol_ratio = (double)rates[19].real_volume / (volume_avg + 1e-10);
   
   // 4. Feature Calculations (normalized by ATR for scale invariance)
   float input_features[INPUT_FEATURES_COUNT];
   input_features[0] = (float)atr_v;
   input_features[1] = (float)rsi_v;
   input_features[2] = (float)((rates[19].close - ema20_val[0]) / atr_v);
   input_features[3] = (float)((rates[19].close - ema50_val[0]) / atr_v);
   input_features[4] = (float)((rates[19].close - sma200_val[0]) / atr_v);
   input_features[5] = (float)((macd_main[0] - macd_sig[0]) / atr_v);
   input_features[6] = (float)((rates[19].close - rates[19].open) / atr_v);
   input_features[7] = (float)((rates[19].high - MathMax(rates[19].close, rates[19].open)) / atr_v);
   input_features[8] = (float)((MathMin(rates[19].close, rates[19].open) - rates[19].low) / atr_v);
   input_features[9] = (float)vol_ratio;
   
   // 5. Execute ONNX Model Inference
   long  output_label[1];
   float output_probabilities[OUTPUT_CLASSES_COUNT];
   
   // Set outputs to zero/default before run
   output_label[0] = 0;
   ArrayInitialize(output_probabilities, 0.0f);
   
   if(!OnnxRun(onnx_handle, ONNX_NO_CONVERSION, input_features, output_label, output_probabilities))
   {
      Print("ONNX model execution failed. Error: ", GetLastError());
      return;
   }
   
   // Map class output probabilities:
   // Index 0 -> Sell (-1)
   // Index 1 -> Hold (0)
   // Index 2 -> Buy (1)
   float prob_sell = output_probabilities[0];
   float prob_hold = output_probabilities[1];
   float prob_buy  = output_probabilities[2];
   
   long prediction = output_label[0];
   
   // Log model state
   PrintFormat("ONNX Inference Results: Class Pred: %d | Probabilities: [SELL: %.4f, HOLD: %.4f, BUY: %.4f]", 
               prediction, prob_sell, prob_hold, prob_buy);
               
   // 6. Action Signals & Validation
   int active_type = -1;
   int active_count = CountActivePositions(active_type);
   
   bool open_buy  = (prediction == 1  && prob_buy  >= InpMinProbability);
   bool open_sell = (prediction == -1 && prob_sell >= InpMinProbability);
   
   // 7. Manage Active Positions (opposite signals close existing trades)
   if(active_count > 0)
   {
      if(InpCloseOnOppositeSignal)
      {
         // If Buy position active and Sell signal occurs
         if(active_type == POSITION_TYPE_BUY && open_sell)
         {
            Print("Closing active Buy position due to opposite Sell signal.");
            trade.PositionClose(Symbol());
            active_count = 0;
         }
         // If Sell position active and Buy signal occurs
         else if(active_type == POSITION_TYPE_SELL && open_buy)
         {
            Print("Closing active Sell position due to opposite Buy signal.");
            trade.PositionClose(Symbol());
            active_count = 0;
         }
      }
   }
   
   // 8. Open New Trades with Risk Management
   if(active_count == 0 && (open_buy || open_sell))
   {
      double ask = SymbolInfoDouble(Symbol(), SYMBOL_ASK);
      double bid = SymbolInfoDouble(Symbol(), SYMBOL_BID);
      double point = SymbolInfoDouble(Symbol(), SYMBOL_POINT);
      double tick_size = SymbolInfoDouble(Symbol(), SYMBOL_TRADE_TICK_SIZE);
      double tick_value = SymbolInfoDouble(Symbol(), SYMBOL_TRADE_TICK_VALUE);
      
      // Stop Loss & Take Profit Price Targets (Volatility Adjusted)
      double sl_distance = atr_v * InpStopLossATRMultiplier;
      double tp_distance = atr_v * InpTakeProfitATRMultiplier;
      
      // Adjust TP to account for commission and spread markup
      double min_price_markup = (current_spread * point) + (InpCommissionPerLot / SymbolInfoDouble(Symbol(), SYMBOL_TRADE_CONTRACT_SIZE));
      if(tp_distance < min_price_markup * 1.5)
      {
         // Pad Take Profit to ensure we can exceed commissions & spreads profitably
         tp_distance = min_price_markup * 2.0;
         Print("Warning: Calculated ATR TP was too close to cover commissions. Adjusted to: ", tp_distance);
      }
      
      // Calculate Lot Size
      double final_lots = InpLotSize;
      if(InpUseDynamicRisk)
      {
         double equity = AccountInfoDouble(ACCOUNT_EQUITY);
         double risk_amount = equity * (InpRiskPercent / 100.0);
         
         // Calculate lot size based on Stop Loss distance
         double risk_per_lot = (sl_distance / tick_size) * tick_value;
         if(risk_per_lot > 0)
         {
            final_lots = risk_amount / risk_per_lot;
         }
      }
      
      // Normalize Lot Size to broker contract rules
      double min_lot = SymbolInfoDouble(Symbol(), SYMBOL_VOLUME_MIN);
      double max_lot = SymbolInfoDouble(Symbol(), SYMBOL_VOLUME_MAX);
      double step_lot = SymbolInfoDouble(Symbol(), SYMBOL_VOLUME_STEP);
      
      final_lots = MathFloor(final_lots / step_lot) * step_lot;
      if(final_lots < min_lot) final_lots = min_lot;
      if(final_lots > max_lot) final_lots = max_lot;
      
      if(open_buy)
      {
         double sl_price = ask - sl_distance;
         double tp_price = ask + tp_distance;
         
         PrintFormat("Opening Buy Trade. Lots: %.2f | Ask: %.2f | SL: %.2f | TP: %.2f", final_lots, ask, sl_price, tp_price);
         trade.Buy(final_lots, Symbol(), ask, sl_price, tp_price, "ONNX Native Buy");
      }
      else if(open_sell)
      {
         double sl_price = bid + sl_distance;
         double tp_price = bid - tp_distance;
         
         PrintFormat("Opening Sell Trade. Lots: %.2f | Bid: %.2f | SL: %.2f | TP: %.2f", final_lots, bid, sl_price, tp_price);
         trade.Sell(final_lots, Symbol(), bid, sl_price, tp_price, "ONNX Native Sell");
      }
   }
}
//+------------------------------------------------------------------+
