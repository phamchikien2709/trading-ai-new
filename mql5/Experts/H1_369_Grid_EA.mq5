//+------------------------------------------------------------------+
//|  H1_369_Grid_EA.mq5                                              |
//|                                                                  |
//|  Mốc "số 9" = giá chia hết cho 9 (digital root = 9, vd 4113).    |
//|  Mỗi khi nến H1 mới mở:                                          |
//|   1. Xoá hết lệnh chờ của EA (theo magic + symbol)               |
//|   2. Trend H1 nến đã đóng: EMA9(RSI14) > WMA45(RSI14) => BULLISH |
//|   3. Mốc từ Open H1 mới: S1 = mốc số 9 ngay dưới Open, R1 = S1+9 |
//|      S2,S3 / R2,R3 cách nhau 9                                   |
//|   4. BULLISH: Buy Limit S1/S2/S3 + offset, TP = R1 - offset      |
//|      BEARISH: Sell Limit R1/R2/R3 - offset, TP = S1 + offset     |
//|  Lệnh đã khớp giữ nguyên TP. KHÔNG stoploss.                     |
//|  Mốc đã có lệnh cùng chiều đang mở => không đặt limit trùng.     |
//+------------------------------------------------------------------+
#property copyright "KienPC98"
#property version   "1.00"
#property description "H1 369 Grid: limit tại mốc số 9 theo trend EMA9/WMA45 của RSI14 (H1). Không SL."

#include <Trade\Trade.mqh>

enum ENUM_TP_MODE
  {
   TP_R1_COMMON  = 0, // TP chung: R1 (buy) / S1 (sell)
   TP_NEXT_LEVEL = 1  // TP: mốc ngay trên (buy) / dưới (sell) từng lệnh
  };

input group "Mốc & lệnh"
input double          InpLot       = 0.1;            // Khối lượng mỗi lệnh (lot)
input double          InpStep      = 9.0;            // Bước mốc (9 = số 9)
input int             InpLevels    = 3;              // Số lệnh limit mỗi giờ
input double          InpOffset    = 0.2;            // Offset spread (giá)
input ENUM_TP_MODE    InpTpMode    = TP_R1_COMMON;   // Cách đặt TP
input ENUM_TIMEFRAMES InpLevelTf   = PERIOD_H1;      // Khung lấy Open / reset lệnh
input bool            InpPlaceOnStart = true;        // Đặt lệnh ngay khi gắn EA (theo Open giờ hiện tại)
input double          InpDupTol    = 1.0;            // Coi là trùng mốc nếu lệnh mở cách mốc <= (giá)
input ulong           InpMagic     = 369369;         // Magic number

input group "Filter trend"
input ENUM_TIMEFRAMES InpTrendTf   = PERIOD_H1;      // Khung trend
input int             InpRsiLen    = 14;             // RSI length
input int             InpEmaLen    = 9;              // EMA (trên RSI)
input int             InpWmaLen    = 45;             // WMA (trên RSI)

CTrade   trade;
int      hRsi = INVALID_HANDLE, hEma = INVALID_HANDLE, hWma = INVALID_HANDLE;
datetime lastBar = 0;

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpStep <= 0 || InpLevels < 1 || InpLot <= 0)
     {
      Print("Input không hợp lệ (step/levels/lot)");
      return INIT_PARAMETERS_INCORRECT;
     }

   hRsi = iRSI(_Symbol, InpTrendTf, InpRsiLen, PRICE_CLOSE);
   if(hRsi == INVALID_HANDLE)
      return INIT_FAILED;
   hEma = iMA(_Symbol, InpTrendTf, InpEmaLen, 0, MODE_EMA, hRsi);    // EMA trên RSI
   hWma = iMA(_Symbol, InpTrendTf, InpWmaLen, 0, MODE_LWMA, hRsi);   // WMA = LWMA trên RSI
   if(hEma == INVALID_HANDLE || hWma == INVALID_HANDLE)
      return INIT_FAILED;

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetTypeFillingBySymbol(_Symbol);

   // không đặt ngay => chờ tới nến mới
   lastBar = InpPlaceOnStart ? 0 : iTime(_Symbol, InpLevelTf, 0);
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   IndicatorRelease(hEma);
   IndicatorRelease(hWma);
   IndicatorRelease(hRsi);
   Comment("");
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   datetime t = iTime(_Symbol, InpLevelTf, 0);
   if(t == 0 || t == lastBar)
      return;

   int trend = GetTrend();
   if(trend == 0)
      return;             // dữ liệu indicator chưa sẵn sàng -> thử lại tick sau

   DeletePendings();
   PlaceGrid(trend);
   lastBar = t;
  }

//+------------------------------------------------------------------+
//| 1 = bullish, -1 = bearish, 0 = chưa sẵn sàng / bằng nhau         |
//+------------------------------------------------------------------+
int GetTrend()
  {
   int bars = iBars(_Symbol, InpTrendTf);
   if(BarsCalculated(hEma) < bars || BarsCalculated(hWma) < bars)
      return 0;

   double e[1], w[1];
   if(CopyBuffer(hEma, 0, 1, 1, e) != 1 || CopyBuffer(hWma, 0, 1, 1, w) != 1)   // shift 1 = nến đã đóng
      return 0;
   if(e[0] == EMPTY_VALUE || w[0] == EMPTY_VALUE)
      return 0;
   return e[0] > w[0] ? 1 : e[0] < w[0] ? -1 : 0;
  }

//+------------------------------------------------------------------+
void DeletePendings()
  {
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong tk = OrderGetTicket(i);
      if(tk == 0)
         continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol || (ulong)OrderGetInteger(ORDER_MAGIC) != InpMagic)
         continue;
      if(!trade.OrderDelete(tk))
         PrintFormat("Xoá lệnh chờ #%I64u lỗi: %d %s", tk, trade.ResultRetcode(), trade.ResultRetcodeDescription());
     }
  }

//+------------------------------------------------------------------+
void PlaceGrid(const int trend)
  {
   double o   = iOpen(_Symbol, InpLevelTf, 0);
   double s1  = MathFloor(o / InpStep + 1e-9) * InpStep;
   double r1  = s1 + InpStep;
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double minDist = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   double lot = NormLot(InpLot);
   string cmt = "H1 369";

   for(int k = 0; k < InpLevels; k++)
     {
      if(trend > 0)
        {
         double lv    = s1 - k * InpStep;
         double price = NormPrice(lv + InpOffset);
         double tp    = NormPrice((InpTpMode == TP_R1_COMMON ? r1 : lv + InpStep) - InpOffset);
         if(HasPositionAt(POSITION_TYPE_BUY, lv))
           {
            PrintFormat("Bỏ Buy Limit %.2f: đã có lệnh BUY đang mở tại mốc %.2f", price, lv);
            continue;
           }
         if(price > ask - minDist)
           {
            PrintFormat("Bỏ Buy Limit %.2f: sát/vượt Ask %.2f", price, ask);
            continue;
           }
         if(!trade.BuyLimit(lot, price, _Symbol, 0, tp, ORDER_TIME_GTC, 0, cmt))
            PrintFormat("Buy Limit %.2f lỗi: %d %s", price, trade.ResultRetcode(), trade.ResultRetcodeDescription());
        }
      else
        {
         double lv    = r1 + k * InpStep;
         double price = NormPrice(lv - InpOffset);
         double tp    = NormPrice((InpTpMode == TP_R1_COMMON ? s1 : lv - InpStep) + InpOffset);
         if(HasPositionAt(POSITION_TYPE_SELL, lv))
           {
            PrintFormat("Bỏ Sell Limit %.2f: đã có lệnh SELL đang mở tại mốc %.2f", price, lv);
            continue;
           }
         if(price < bid + minDist)
           {
            PrintFormat("Bỏ Sell Limit %.2f: sát/vượt Bid %.2f", price, bid);
            continue;
           }
         if(!trade.SellLimit(lot, price, _Symbol, 0, tp, ORDER_TIME_GTC, 0, cmt))
            PrintFormat("Sell Limit %.2f lỗi: %d %s", price, trade.ResultRetcode(), trade.ResultRetcodeDescription());
        }
     }

   Comment(StringFormat("H1 369 Grid | Trend %s | Open %.2f | S1 %.2f  R1 %.2f | %d limit %s",
                        trend > 0 ? "BULLISH" : "BEARISH", o, s1, r1, InpLevels, trend > 0 ? "BUY" : "SELL"));
  }

//+------------------------------------------------------------------+
//| Có lệnh (của EA) cùng chiều đang mở, giá vào cách mốc lv <= tol  |
//+------------------------------------------------------------------+
bool HasPositionAt(const ENUM_POSITION_TYPE type, const double lv)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || (ulong)PositionGetInteger(POSITION_MAGIC) != InpMagic)
         continue;
      if((ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) != type)
         continue;
      if(MathAbs(PositionGetDouble(POSITION_PRICE_OPEN) - lv) <= InpDupTol)
         return true;
     }
   return false;
  }

//+------------------------------------------------------------------+
double NormPrice(const double p)
  {
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(ts <= 0)
      ts = _Point;
   return NormalizeDouble(MathRound(p / ts) * ts, _Digits);
  }

//+------------------------------------------------------------------+
double NormLot(const double v)
  {
   double mn = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double mx = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double st = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double l  = MathFloor(v / st + 1e-9) * st;
   return MathMax(mn, MathMin(mx, l));
  }
//+------------------------------------------------------------------+
