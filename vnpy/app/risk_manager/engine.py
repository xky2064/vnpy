""""""
from collections import defaultdict
from vnpy.trader.object import OrderRequest
from vnpy.event import Event, EventEngine, EVENT_TIMER
from vnpy.trader.engine import BaseEngine, MainEngine
from vnpy.trader.event import EVENT_TRADE, EVENT_ORDER, EVENT_LOG
from vnpy.trader.constant import Status
from vnpy.trader.utility import load_json, save_json


APP_NAME = "RiskManager"


class RiskManagerEngine(BaseEngine):
    """风控引擎"""
    setting_filename = "risk_manager_setting.json"
    
    def __init__(self, main_engine: MainEngine, event_engine: EventEngine):
        """"""
        self.main_engine = main_engine
        self.event_engine = event_engine
        main_engine.rmEngine = self

        self.active = False
        self.order_flow_count = 0    
        self.order_flow_limit = 50     
        self.order_flow_clear = 1     
        self.order_flow_timer = 0    
        self.order_size_limit = 100   
        self.trade_count = 0      
        self.trade_limit = 1000         
        self.order_cancel_limit = 10  
        self.order_cancel_counts = defaultdict(int)          
        self.active_order_limit = 20  
        
        self.load_setting()
        self.registerEvent()
  
    def load_setting(self):
        """"""
        setting = load_json(self.setting_filename)

        self.active = setting["active"]
        self.order_flow_limit = setting["order_flow_limit"]
        self.order_flow_clear = setting["order_flow_clear"]
        self.order_size_limit = setting["order_size_limit"]
        self.trade_limit = setting["trade_limit"]
        self.active_order_limit = setting["active_order_limit"]
        self.order_cancel_limit = setting["order_cancel_limit"]            
   
    def save_setting(self):
        """"""
        setting = {
            "active": self.active,
            "order_flow_limit": self.order_flow_limit,
            "order_flow_clear": self.order_flow_clear,
            "order_size_limit": self.order_size_limit,
            "trade_limit": self.trade_limit,
            "active_order_limit": self.active_order_limit,
            "order_cancel_limit": self.order_cancel_limit,
        }

        save_json(self.setting_filename, setting)
   
    def register_event(self):
        """"""
        self.event_engine.register(EVENT_TRADE, self.process_trade_event)
        self.event_engine.register(EVENT_TIMER, self.process_timer_event)
        self.event_engine.register(EVENT_ORDER, self.process_order_event)
            
    def process_order_event(self, event: Event):
        """"""
        order = event.data
        if order.status != Status.CANCELLED:
            return       
        self.order_cancel_counts[order.symbol] += 1
   
    def process_trade_event(self, event: Event):
        """"""
        trade = event.data
        self.trade_count += trade.volume
    
    def process_timer_event(self, event: Event):
        """"""
        self.order_flow_timer += 1

        if self.order_flow_timer >= self.order_flow_clear:
            self.order_flow_count = 0
            self.order_flow_timer = 0
   
    def write_risk_log(self, msg: str):
        """"""        
        event = Event(
            EVENT_LOG,
            msg
        )
        self.event_engine.put(event)

    def check_risk(self, req: OrderRequest, gateway_name: str):
        """"""
        if not self.active:
            return True

        # Check order volume
        if req.volume <= 0:
            self.write_risk_log("委托数量必须大于0")
            return False
        
        if req.volume > self.order_size_limit:
            self.write_risk_log(f"单笔委托数量{req.volume}，超过限制{self.order_size_limit}")
            return False

        # Check trade volume
        if self.trade_count >= self.trade_limit:
            self.write_risk_log(f"今日总成交合约数量{self.trade_count}，超过限制{self.trade_limit}")
            return False

        # Check flow count
        if self.order_flow_count >= self.order_flow_limit:
            self.write_risk_log(f"委托流数量{self.order_flow_count}，超过限制每{self.order_flow_clear}秒{self.order_flow_limit}")
            return False

        # Check all active orders
        active_order_count = len(self.main_engine.get_all_active_orders())
        if active_order_count >= self.active_order_limit:
            self.write_risk_log(f"当前活动委托数量{active_order_count}，超过限制{self.active_order_limit}")
            return False

        # Check order cancel counts
        if req.symbol in self.order_cancel_counts and self.order_cancel_counts[req.symbol] >= self.order_cancel_limit:
            self.write_risk_log(f"当日{req.symbol}撤单次数{self.order_cancel_counts[req.symbol]}，超过限制{self.order_cancel_limit}")
            return False

        # Add flow count if pass all checks
        self.order_flow_count += 1
        return True
    
    def clear_order_flow_count(self):
        """"""
        self.order_flow_count = 0
        self.write_risk_log("清空流控计数")
    
    def clear_trade_count(self):
        """"""
        self.trade_count = 0
        self.write_risk_log("清空总成交计数")
   
    def set_order_flow_limit(self, n):
        """"""
        self.order_flow_limit = n
   
    def set_order_flow_clear(self, n):
        """"""
        self.order_flow_clear = n
    
    def set_order_size_limit(self, n):
        """"""
        self.order_size_limit = n
   
    def set_trade_limit(self, n):
        """"""
        self.trade_limit = n
   
    def set_active_order_limit(self, n):
        """"""
        self.active_order_limit = n
   
    def set_order_cancel_limit(self, n):
        """"""
        self.order_cancel_limit = n
    
    def switch_engine_status(self):
        """"""
        self.active = not self.active

        if self.active:
            self.write_risk_log("风险管理功能启动")
        else:
            self.write_risk_log("风险管理功能停止")
                
    def stop(self):
        """"""
        self.save_setting()
        