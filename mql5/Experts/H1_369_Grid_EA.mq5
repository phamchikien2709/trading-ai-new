//+------------------------------------------------------------------+
//|  H1_369_Grid_EA.mq5                                              |
//|                                                                  |
//|  Mốc "số 9" = giá chia hết cho 9 (digital root = 9, vd 4113).    |
//|  Mỗi khi nến H1 mới mở:                                          |
//|   1. Xoá hết lệnh chờ của EA (theo magic + symbol)               |
//|   2. Trend H1 nến đã đóng: EMA9(RSI14) > WMA45(RSI14) => BULLISH |
//|   3. Mốc từ Open H1 mới: S1 = mốc số 9 ngay dưới Open, R1 = S1+9 |
//|      S2,S3 / R2,R3 cách nhau 9                                   |
//|   4. BULLISH: Buy Limit S1/S2/S3 + offset                        |
//|        TP mốc ngay trên - offset: S1->R1, S2->S1, S3->S2         |
//|      BEARISH: Sell Limit R1/R2/R3 - offset                       |
//|        TP mốc ngay dưới + offset: R1->S1, R2->R1, R3->R2         |
//|  Lệnh đã khớp giữ nguyên TP. KHÔNG stoploss.                     |
//|  Mốc đã có lệnh cùng chiều đang mở (của EA hoặc đặt tay)         |
//|  => không đặt limit trùng.                                       |
//|  Trong giờ: lệnh EA chạm TP => đặt lại limit ở mốc còn trống     |
//|  của giờ hiện tại (cùng trend, cùng mốc).                        |
//|  Kéo TP (InpTpPull): lệnh EA khớp sâu hơn (S2, S3 / R2, R3)      |
//|  => mọi lệnh EA cùng chiều lấy TP của lệnh sâu nhất.             |
//|  Tối đa InpMaxPositions lệnh mở (EA + lệnh tay): mở + limit mới  |
//|  không vượt giới hạn (0 = không giới hạn).                       |
//|  Bảng trên chart: trend, mốc, lệnh mở (EA + tay), lệnh chờ,      |
//|  tổng lời/lỗ, equity, DD; vẽ đường mốc của giờ hiện tại.         |
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
input ENUM_TP_MODE    InpTpMode    = TP_NEXT_LEVEL;  // Cách đặt TP
input bool            InpTpPull    = true;           // Khớp mốc sâu hơn => kéo TP mọi lệnh EA cùng chiều về TP lệnh sâu nhất
input ENUM_TIMEFRAMES InpLevelTf   = PERIOD_H1;      // Khung lấy Open / reset lệnh
input bool            InpPlaceOnStart = true;        // Đặt lệnh ngay khi gắn EA (theo Open giờ hiện tại)
input double          InpDupTol    = 1.0;            // Coi là trùng mốc nếu lệnh mở cách mốc <= (giá)
input bool            InpDupAllOrders = true;        // Tính cả lệnh đặt tay / EA khác khi kiểm tra trùng mốc
input int             InpMaxPositions = 6;           // Số lệnh mở tối đa (0 = không giới hạn)
input bool            InpMaxCountAll  = true;        // Giới hạn tính cả lệnh đặt tay / EA khác trên symbol
input ulong           InpMagic     = 369369;         // Magic number

input group "Filter trend"
input ENUM_TIMEFRAMES InpTrendTf   = PERIOD_H1;      // Khung trend
input int             InpRsiLen    = 14;             // RSI length
input int             InpEmaLen    = 9;              // EMA (trên RSI)
input int             InpWmaLen    = 45;             // WMA (trên RSI)

input group "Bảng hiển thị"
input bool            InpShowPanel    = true;        // Hiện bảng trên chart
input bool            InpShowLevels   = true;        // Vẽ đường mốc của giờ hiện tại
input int             InpPanelX       = 10;          // Vị trí X (px từ trái)
input int             InpPanelY       = 25;          // Vị trí Y (px từ trên)
input int             InpPanelFont    = 9;           // Cỡ chữ
input int             InpPanelMaxPos  = 8;           // Số lệnh mở tối đa hiển thị
input int             InpPanelMaxPend = 6;           // Số lệnh chờ tối đa hiển thị

CTrade   trade;
int      hRsi = INVALID_HANDLE, hEma = INVALID_HANDLE, hWma = INVALID_HANDLE;
datetime lastBar = 0;
int      curTrend = 0;       // trend của giờ hiện tại (chốt lúc mở giờ)
bool     needRefill = false; // có lệnh EA vừa chạm TP -> đặt lại mốc trống
double   curS1 = 0, curR1 = 0;   // mốc của giờ hiện tại (cho bảng / đường mốc)
bool     dirty = true;           // cần vẽ lại bảng ngay
datetime lastDraw = 0;
datetime pullFailAt = 0;         // lần sửa TP lỗi gần nhất (tránh gửi lại mỗi tick)

// ------------------------------------------------------------ panel ----
#define PFX   "H369_"
#define PAD   8
color    CLR_BG   = C'22,26,34';
color    CLR_EDGE = C'60,70,90';
color    CLR_TXT  = C'230,233,240';
color    CLR_DIM  = C'140,150,165';
color    CLR_BUY  = C'38,166,154';
color    CLR_SELL = C'239,83,80';
color    CLR_POS  = C'102,187,106';
color    CLR_NEG  = C'239,83,80';
color    CLR_WARN = C'255,183,77';
string   touched[];
int      bgH = 0;                // chiều cao nền bảng hiện tại

struct PosRow
  {
   long   type;
   bool   ea;
   double lot;
   double price;
   double tp;
   double pl;
  };

struct PendRow
  {
   long   type;
   bool   ea;
   double lot;
   double price;
   double tp;
  };

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
   EventSetTimer(1);
   Redraw();
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   IndicatorRelease(hEma);
   IndicatorRelease(hWma);
   IndicatorRelease(hRsi);
   EventKillTimer();
   ObjectsDeleteAll(0, PFX);
   bgH = 0;
   ChartRedraw();
  }

//+------------------------------------------------------------------+
void OnTimer()
  {
   Redraw();              // đồng hồ reset chạy cả khi không có tick
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   RunLogic();
   if(dirty)
      Redraw();           // có lệnh thay đổi -> vẽ ngay; còn lại timer 1s lo
  }

//+------------------------------------------------------------------+
void RunLogic()
  {
   if(InpTpPull)
      PullTp();

   datetime t = iTime(_Symbol, InpLevelTf, 0);
   if(t == 0)
      return;

   if(t == lastBar)
     {
      // cùng giờ: lệnh vừa chốt TP -> đặt lại limit ở các mốc còn trống
      if(needRefill && curTrend != 0)
        {
         needRefill = false;
         PlaceGrid(curTrend);
        }
      return;
     }

   int trend = GetTrend();
   if(trend == 0)
      return;             // dữ liệu indicator chưa sẵn sàng -> thử lại tick sau

   DeletePendings();
   curTrend   = trend;
   needRefill = false;
   PlaceGrid(trend);
   lastBar = t;
  }

//+------------------------------------------------------------------+
//| Lệnh của EA đóng do chạm TP => bật cờ đặt lại limit              |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD || !HistoryDealSelect(trans.deal))
      return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol)
      return;
   dirty = true;          // có giao dịch trên symbol -> vẽ lại bảng
   if((ulong)HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != InpMagic)
      return;
   if(HistoryDealGetInteger(trans.deal, DEAL_ENTRY) == DEAL_ENTRY_OUT
      && HistoryDealGetInteger(trans.deal, DEAL_REASON) == DEAL_REASON_TP)
      needRefill = true;
  }

//+------------------------------------------------------------------+
//| Kéo TP: lệnh EA sâu nhất mỗi chiều (buy giá vào thấp nhất,       |
//| sell cao nhất) quyết định TP chung cho mọi lệnh EA cùng chiều.   |
//| vd S1 + S2 khớp => TP S1 = TP S2 (S1 - 0.2);                     |
//|    S3 khớp => TP S1, S2 = TP S3 (S2 - 0.2).                      |
//+------------------------------------------------------------------+
void PullTp()
  {
   if(TimeCurrent() - pullFailAt < 10)
      return;
   PullTpSide(POSITION_TYPE_BUY);
   PullTpSide(POSITION_TYPE_SELL);
  }

void PullTpSide(const ENUM_POSITION_TYPE type)
  {
   bool   isBuy = type == POSITION_TYPE_BUY;
   double deep  = 0, target = 0;
   bool   found = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(!SelectEaPosition(i, type))
         continue;
      double op = PositionGetDouble(POSITION_PRICE_OPEN);
      if(!found || (isBuy ? op < deep : op > deep))
        {
         deep   = op;
         target = PositionGetDouble(POSITION_TP);
         found  = true;
        }
     }
   if(!found || target <= 0)
      return;             // không có lệnh / lệnh sâu nhất không có TP

   // TP phải cách giá hiện tại >= stops level, không thì để lệnh sâu nhất tự chốt
   double minDist = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   if(isBuy ? target < SymbolInfoDouble(_Symbol, SYMBOL_BID) + minDist
            : target > SymbolInfoDouble(_Symbol, SYMBOL_ASK) - minDist)
      return;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(!SelectEaPosition(i, type))
         continue;
      if(MathAbs(PositionGetDouble(POSITION_TP) - target) < _Point / 2)
         continue;
      ulong tk = (ulong)PositionGetInteger(POSITION_TICKET);
      double op = PositionGetDouble(POSITION_PRICE_OPEN);
      if(trade.PositionModify(tk, PositionGetDouble(POSITION_SL), target))
        {
         PrintFormat("Kéo TP %s #%I64u (vào %.2f) về %.2f theo lệnh sâu nhất %.2f",
                     isBuy ? "BUY" : "SELL", tk, op, target, deep);
         dirty = true;
        }
      else
        {
         pullFailAt = TimeCurrent();
         PrintFormat("Kéo TP #%I64u lỗi: %d %s", tk, trade.ResultRetcode(), trade.ResultRetcodeDescription());
         return;
        }
     }
  }

bool SelectEaPosition(const int i, const ENUM_POSITION_TYPE type)
  {
   ulong tk = PositionGetTicket(i);
   return tk != 0
          && PositionGetString(POSITION_SYMBOL) == _Symbol
          && (ulong)PositionGetInteger(POSITION_MAGIC) == InpMagic
          && (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == type;
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
   curS1 = s1;
   curR1 = r1;
   dirty = true;

   // lệnh mở + lệnh chờ của EA + limit mới không vượt InpMaxPositions
   int openCnt = CountPositions();
   int pendCnt = CountEaPendings();
   int slots   = InpMaxPositions > 0 ? InpMaxPositions - openCnt - pendCnt : InpLevels;
   int placed  = 0;
   if(slots <= 0)
      PrintFormat("Đã đủ %d/%d lệnh mở, không đặt limit giờ này", openCnt, InpMaxPositions);

   for(int k = 0; k < InpLevels && placed < slots; k++)
     {
      if(trend > 0)
        {
         double lv    = s1 - k * InpStep;
         double price = NormPrice(lv + InpOffset);
         double tp    = NormPrice((InpTpMode == TP_R1_COMMON ? r1 : lv + InpStep) - InpOffset);
         if(HasPendingAt(ORDER_TYPE_BUY_LIMIT, price))
            continue;                     // mốc này đã có limit (lần đặt lại trong giờ)
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
         if(trade.BuyLimit(lot, price, _Symbol, 0, tp, ORDER_TIME_GTC, 0, cmt))
            placed++;
         else
            PrintFormat("Buy Limit %.2f lỗi: %d %s", price, trade.ResultRetcode(), trade.ResultRetcodeDescription());
        }
      else
        {
         double lv    = r1 + k * InpStep;
         double price = NormPrice(lv - InpOffset);
         double tp    = NormPrice((InpTpMode == TP_R1_COMMON ? s1 : lv - InpStep) + InpOffset);
         if(HasPendingAt(ORDER_TYPE_SELL_LIMIT, price))
            continue;
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
         if(trade.SellLimit(lot, price, _Symbol, 0, tp, ORDER_TIME_GTC, 0, cmt))
            placed++;
         else
            PrintFormat("Sell Limit %.2f lỗi: %d %s", price, trade.ResultRetcode(), trade.ResultRetcodeDescription());
        }
     }
  }

//+------------------------------------------------------------------+
//| Lệnh chờ của EA                                                  |
//+------------------------------------------------------------------+
int CountEaPendings()
  {
   int n = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong tk = OrderGetTicket(i);
      if(tk != 0 && OrderGetString(ORDER_SYMBOL) == _Symbol && (ulong)OrderGetInteger(ORDER_MAGIC) == InpMagic)
         n++;
     }
   return n;
  }

bool HasPendingAt(const ENUM_ORDER_TYPE type, const double price)
  {
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong tk = OrderGetTicket(i);
      if(tk == 0 || OrderGetString(ORDER_SYMBOL) != _Symbol || (ulong)OrderGetInteger(ORDER_MAGIC) != InpMagic)
         continue;
      if((ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE) == type
         && MathAbs(OrderGetDouble(ORDER_PRICE_OPEN) - price) <= InpDupTol)
         return true;
     }
   return false;
  }

//+------------------------------------------------------------------+
//| Số lệnh đang mở trên symbol, cả buy lẫn sell                     |
//| (chỉ của EA nếu InpMaxCountAll = false)                          |
//+------------------------------------------------------------------+
int CountPositions()
  {
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;
      if(!InpMaxCountAll && (ulong)PositionGetInteger(POSITION_MAGIC) != InpMagic)
         continue;
      n++;
     }
   return n;
  }

//+------------------------------------------------------------------+
//| Có lệnh cùng chiều đang mở (EA, + lệnh tay nếu InpDupAllOrders), |
//| giá vào cách mốc lv <= tol                                       |
//+------------------------------------------------------------------+
bool HasPositionAt(const ENUM_POSITION_TYPE type, const double lv)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;
      if(!InpDupAllOrders && (ulong)PositionGetInteger(POSITION_MAGIC) != InpMagic)
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

//====================================================================
//  BẢNG HIỂN THỊ
//====================================================================
int    Sx(const int x)    { return x * InpPanelFont / 9; }
int    RowH()             { return (int)MathRound(InpPanelFont * 2.0); }
string Px(const double p) { return DoubleToString(p, _Digits); }

// ghi thuộc tính chỉ khi thay đổi (ghi lại liên tục làm chart nháy)
void SetI(const string n, const ENUM_OBJECT_PROPERTY_INTEGER prop, const long v)
  {
   if(ObjectGetInteger(0, n, prop) != v)
      ObjectSetInteger(0, n, prop, v);
  }

void SetS(const string n, const ENUM_OBJECT_PROPERTY_STRING prop, const string v)
  {
   if(ObjectGetString(0, n, prop) != v)
      ObjectSetString(0, n, prop, v);
  }

void MoveIf(const string n, const int point, const datetime t, const double price)
  {
   if((datetime)ObjectGetInteger(0, n, OBJPROP_TIME, point) != t
      || MathAbs(ObjectGetDouble(0, n, OBJPROP_PRICE, point) - price) > _Point / 2)
      ObjectMove(0, n, point, t, price);
  }

void Touch(const string name)
  {
   int n = ArraySize(touched);
   ArrayResize(touched, n + 1);
   touched[n] = name;
  }

void Rect(const string name, const int x, const int y, const int w, const int h, const color bg, const color edge)
  {
   if(ObjectFind(0, name) < 0)
     {
      ObjectCreate(0, name, OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_BORDER_TYPE, BORDER_FLAT);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
     }
   SetI(name, OBJPROP_XDISTANCE, x);
   SetI(name, OBJPROP_YDISTANCE, y);
   SetI(name, OBJPROP_XSIZE, w);
   if(h > 0)
      SetI(name, OBJPROP_YSIZE, h);
   SetI(name, OBJPROP_BGCOLOR, bg);
   SetI(name, OBJPROP_COLOR, edge);
   Touch(name);
  }

void Cell(const int row, const int col, const int x, const string text, const color clr)
  {
   string name = PFX + "c" + IntegerToString(row) + "_" + IntegerToString(col);
   if(ObjectFind(0, name) < 0)
     {
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_ANCHOR, ANCHOR_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetString(0, name, OBJPROP_FONT, "Consolas");
     }
   SetI(name, OBJPROP_XDISTANCE, InpPanelX + PAD + Sx(x));
   SetI(name, OBJPROP_YDISTANCE, InpPanelY + PAD + row * RowH());
   SetI(name, OBJPROP_FONTSIZE, InpPanelFont);
   SetI(name, OBJPROP_COLOR, clr);
   SetS(name, OBJPROP_TEXT, text);
   Touch(name);
  }

// đường kẻ ngang phân cách phía trên hàng `row`
void Sep(const int row, const int w)
  {
   Rect(PFX + "s" + IntegerToString(row), InpPanelX + PAD, InpPanelY + PAD + row * RowH() - 3,
        w - 2 * PAD, 1, CLR_EDGE, CLR_EDGE);
  }

string Countdown()
  {
   if(lastBar == 0)
      return "--:--";
   long s = (long)(lastBar + PeriodSeconds(InpLevelTf) - TimeTradeServer());
   if(s < 0)
      s = 0;
   return StringFormat("%02d:%02d", (int)(s / 60), (int)(s % 60));
  }

string PendName(const long type)
  {
   if(type == ORDER_TYPE_BUY_LIMIT)
      return "BUY LIMIT";
   if(type == ORDER_TYPE_SELL_LIMIT)
      return "SELL LIMIT";
   if(type == ORDER_TYPE_BUY_STOP)
      return "BUY STOP";
   if(type == ORDER_TYPE_SELL_STOP)
      return "SELL STOP";
   return "KHÁC";
  }

bool IsBuyPend(const long type)
  {
   return type == ORDER_TYPE_BUY_LIMIT || type == ORDER_TYPE_BUY_STOP || type == ORDER_TYPE_BUY_STOP_LIMIT;
  }

//+------------------------------------------------------------------+
void Redraw()
  {
   dirty    = false;
   lastDraw = TimeCurrent();
   if(MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE))
      return;             // tester không hiển thị -> bỏ qua cho nhanh

   ArrayResize(touched, 0);
   if(InpShowPanel)
      DrawPanel();
   if(InpShowLevels)
      DrawLevels();

   // xoá object cũ không còn dùng (vd dòng lệnh đã đóng)
   for(int i = ObjectsTotal(0, -1, -1) - 1; i >= 0; i--)
     {
      string nm = ObjectName(0, i, -1, -1);
      if(StringFind(nm, PFX) != 0)
         continue;
      bool keep = false;
      for(int j = 0; j < ArraySize(touched) && !keep; j++)
         keep = (touched[j] == nm);
      if(!keep)
         ObjectDelete(0, nm);
     }
   ChartRedraw();
  }

//+------------------------------------------------------------------+
void DrawPanel()
  {
   int    W   = Sx(450);
   string cur = AccountInfoString(ACCOUNT_CURRENCY);
   if(ObjectFind(0, PFX + "bg") < 0)
      bgH = 0;            // nền bị xoá (vd người dùng xoá object) -> đặt lại chiều cao
   Rect(PFX + "bg", InpPanelX, InpPanelY, W, bgH > 0 ? 0 : 10, CLR_BG, CLR_EDGE);   // giữ chiều cao cũ

   int r = 0;
   // ---- tiêu đề
   Cell(r, 0, 0, "H1 369 GRID  " + _Symbol, CLR_TXT);
   Cell(r, 1, 220, curTrend > 0 ? "▲ BULLISH" : curTrend < 0 ? "▼ BEARISH" : "… chờ dữ liệu",
        curTrend > 0 ? CLR_BUY : curTrend < 0 ? CLR_SELL : CLR_DIM);
   Cell(r, 2, 330, "reset sau " + Countdown(), CLR_DIM);
   r++;

   // ---- mốc giờ hiện tại (theo chiều lưới)
   string lv = "";
   if(curS1 > 0)
     {
      if(curTrend < 0)
        {
         for(int k = InpLevels - 1; k >= 0; k--)
            lv += StringFormat("R%d %s  ", k + 1, Px(curR1 + k * InpStep));
         lv += "S1 " + Px(curS1);
        }
      else
        {
         lv = "R1 " + Px(curR1);
         for(int k = 0; k < InpLevels; k++)
            lv += StringFormat("  S%d %s", k + 1, Px(curS1 - k * InpStep));
        }
     }
   Cell(r, 0, 0, lv == "" ? "Mốc: chờ nến H1" : lv, CLR_DIM);
   r++;

   // ---- lệnh đang mở (mọi lệnh trên symbol)
   PosRow pos[];
   double totPl = 0;
   int    nPos  = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;
      ArrayResize(pos, nPos + 1);
      pos[nPos].type  = PositionGetInteger(POSITION_TYPE);
      pos[nPos].ea    = (ulong)PositionGetInteger(POSITION_MAGIC) == InpMagic;
      pos[nPos].lot   = PositionGetDouble(POSITION_VOLUME);
      pos[nPos].price = PositionGetDouble(POSITION_PRICE_OPEN);
      pos[nPos].tp    = PositionGetDouble(POSITION_TP);
      pos[nPos].pl    = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
      totPl += pos[nPos].pl;
      nPos++;
     }
   for(int a = 1; a < nPos; a++)               // giá vào cao -> thấp
      for(int b = a; b > 0 && pos[b].price > pos[b - 1].price; b--)
        {
         PosRow tmp = pos[b];
         pos[b] = pos[b - 1];
         pos[b - 1] = tmp;
        }

   Sep(r, W);
   Cell(r, 0, 0, "LỆNH ĐANG MỞ", CLR_TXT);
   Cell(r, 1, 360, IntegerToString(CountPositions()) + " / "
        + (InpMaxPositions > 0 ? IntegerToString(InpMaxPositions) : "∞"), CLR_DIM);
   r++;
   if(nPos == 0)
     {
      Cell(r, 0, 0, "— không có —", CLR_DIM);
      r++;
     }
   else
     {
      Cell(r, 0, 0, "Loại", CLR_DIM);
      Cell(r, 1, 55, "Nguồn", CLR_DIM);
      Cell(r, 2, 105, "Lot", CLR_DIM);
      Cell(r, 3, 160, "Giá vào", CLR_DIM);
      Cell(r, 4, 250, "TP", CLR_DIM);
      Cell(r, 5, 340, "Lời/lỗ", CLR_DIM);
      r++;
      int show = MathMin(nPos, InpPanelMaxPos);
      for(int i = 0; i < show; i++, r++)
        {
         bool buy = pos[i].type == POSITION_TYPE_BUY;
         Cell(r, 0, 0, buy ? "BUY" : "SELL", buy ? CLR_BUY : CLR_SELL);
         Cell(r, 1, 55, pos[i].ea ? "EA" : "Tay", pos[i].ea ? CLR_TXT : CLR_WARN);
         Cell(r, 2, 105, DoubleToString(pos[i].lot, 2), CLR_TXT);
         Cell(r, 3, 160, Px(pos[i].price), CLR_TXT);
         Cell(r, 4, 250, pos[i].tp > 0 ? Px(pos[i].tp) : "—", CLR_TXT);
         Cell(r, 5, 340, StringFormat("%+.2f", pos[i].pl), pos[i].pl >= 0 ? CLR_POS : CLR_NEG);
        }
      if(nPos > show)
        {
         Cell(r, 0, 0, StringFormat("+ %d lệnh khác", nPos - show), CLR_DIM);
         r++;
        }
     }

   // ---- lệnh chờ (mọi lệnh chờ trên symbol)
   PendRow pd[];
   int nPd = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong tk = OrderGetTicket(i);
      if(tk == 0 || OrderGetString(ORDER_SYMBOL) != _Symbol)
         continue;
      ArrayResize(pd, nPd + 1);
      pd[nPd].type  = OrderGetInteger(ORDER_TYPE);
      pd[nPd].ea    = (ulong)OrderGetInteger(ORDER_MAGIC) == InpMagic;
      pd[nPd].lot   = OrderGetDouble(ORDER_VOLUME_CURRENT);
      pd[nPd].price = OrderGetDouble(ORDER_PRICE_OPEN);
      pd[nPd].tp    = OrderGetDouble(ORDER_TP);
      nPd++;
     }
   for(int a = 1; a < nPd; a++)
      for(int b = a; b > 0 && pd[b].price > pd[b - 1].price; b--)
        {
         PendRow tmp = pd[b];
         pd[b] = pd[b - 1];
         pd[b - 1] = tmp;
        }

   Sep(r, W);
   Cell(r, 0, 0, "LỆNH CHỜ", CLR_TXT);
   Cell(r, 1, 360, IntegerToString(nPd), CLR_DIM);
   r++;
   if(nPd == 0)
     {
      Cell(r, 0, 0, "— không có —", CLR_DIM);
      r++;
     }
   else
     {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      int show = MathMin(nPd, InpPanelMaxPend);
      for(int i = 0; i < show; i++, r++)
        {
         bool   buy  = IsBuyPend(pd[i].type);
         double dist = pd[i].price - (buy ? ask : bid);
         Cell(r, 0, 0, PendName(pd[i].type), buy ? CLR_BUY : CLR_SELL);
         Cell(r, 1, 90, pd[i].ea ? "EA" : "Tay", pd[i].ea ? CLR_TXT : CLR_WARN);
         Cell(r, 2, 130, Px(pd[i].price), CLR_TXT);
         Cell(r, 3, 215, pd[i].tp > 0 ? "TP " + Px(pd[i].tp) : "TP —", CLR_TXT);
         Cell(r, 4, 330, StringFormat("cách %+.1f", dist), CLR_DIM);
        }
      if(nPd > show)
        {
         Cell(r, 0, 0, StringFormat("+ %d lệnh khác", nPd - show), CLR_DIM);
         r++;
        }
     }

   // ---- tổng
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   double eq  = AccountInfoDouble(ACCOUNT_EQUITY);
   double dd  = bal > 0 ? MathMax(0.0, (bal - eq) / bal * 100.0) : 0.0;
   Sep(r, W);
   Cell(r, 0, 0, "Lời/lỗ", CLR_DIM);
   Cell(r, 1, 55, StringFormat("%+.2f", totPl), totPl >= 0 ? CLR_POS : CLR_NEG);
   Cell(r, 2, 160, "Equity " + DoubleToString(eq, 2) + " " + cur, CLR_TXT);
   Cell(r, 3, 340, StringFormat("DD %.1f%%", dd), dd > 20 ? CLR_NEG : dd > 0 ? CLR_WARN : CLR_DIM);
   r++;

   int h = PAD * 2 + r * RowH() - 4;
   if(h != bgH)
     {
      bgH = h;
      ObjectSetInteger(0, PFX + "bg", OBJPROP_YSIZE, h);
     }
  }

//+------------------------------------------------------------------+
//| Đường mốc của giờ hiện tại: từ đầu giờ tới cuối giờ              |
//+------------------------------------------------------------------+
void LevelLine(const string id, const double price, const color clr, const ENUM_LINE_STYLE st,
               const datetime t0, const datetime t1)
  {
   string ln = PFX + "L_" + id;
   if(ObjectFind(0, ln) < 0)
     {
      ObjectCreate(0, ln, OBJ_TREND, 0, t0, price, t1, price);
      ObjectSetInteger(0, ln, OBJPROP_RAY_RIGHT, false);
      ObjectSetInteger(0, ln, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, ln, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, ln, OBJPROP_BACK, true);
     }
   MoveIf(ln, 0, t0, price);
   MoveIf(ln, 1, t1, price);
   SetI(ln, OBJPROP_COLOR, clr);
   SetI(ln, OBJPROP_STYLE, st);
   SetI(ln, OBJPROP_WIDTH, 1);
   Touch(ln);

   string tx = PFX + "T_" + id;
   if(ObjectFind(0, tx) < 0)
     {
      ObjectCreate(0, tx, OBJ_TEXT, 0, t1, price);
      ObjectSetInteger(0, tx, OBJPROP_ANCHOR, ANCHOR_LEFT);
      ObjectSetInteger(0, tx, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, tx, OBJPROP_HIDDEN, true);
      ObjectSetString(0, tx, OBJPROP_FONT, "Consolas");
     }
   MoveIf(tx, 0, t1, price);
   SetI(tx, OBJPROP_FONTSIZE, MathMax(6, InpPanelFont - 1));
   SetI(tx, OBJPROP_COLOR, clr);
   SetS(tx, OBJPROP_TEXT, " " + id + " " + Px(price));
   Touch(tx);
  }

void DrawLevels()
  {
   if(curS1 <= 0 || lastBar == 0)
      return;
   datetime t0 = lastBar;
   datetime t1 = t0 + PeriodSeconds(InpLevelTf);
   for(int k = 0; k < InpLevels; k++)
     {
      ENUM_LINE_STYLE st = k == 0 ? STYLE_SOLID : STYLE_DASH;
      LevelLine("S" + IntegerToString(k + 1), curS1 - k * InpStep, CLR_BUY, st, t0, t1);
      LevelLine("R" + IntegerToString(k + 1), curR1 + k * InpStep, CLR_SELL, st, t0, t1);
     }
  }
//+------------------------------------------------------------------+
