"""
期货数据提供商基类和接口
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.futures import FuturesData

logger = logging.getLogger("futures_data_provider")


class FuturesDataProvider(ABC):
    """期货数据提供商基类"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.name = self.__class__.__name__

    @abstractmethod
    async def get_futures_data(self, symbol: str) -> Optional[FuturesData]:
        """获取单个期货的实时数据"""
        pass

    @abstractmethod
    async def get_multiple_futures_data(self, symbols: List[str]) -> List[FuturesData]:
        """获取多个期货的实时数据"""
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """检查数据源是否可用"""
        pass


class TushareFuturesAdapter(FuturesDataProvider):
    """Tushare期货数据适配器"""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        try:
            import tushare as ts
            self.ts = ts
            if api_key:
                self.ts.set_token(api_key)
            self.pro = self.ts.pro_api()
        except ImportError:
            logger.error("Tushare库未安装")
            self.ts = None
            self.pro = None

    async def get_futures_data(self, symbol: str) -> Optional[FuturesData]:
        """获取单个期货的实时数据"""
        try:
            if not self.pro:
                logger.error("Tushare API未初始化")
                return None

            # Tushare期货代码格式：IF2412.CFX
            ts_symbol = f"{symbol}.CFX"

            # 获取实时行情
            df = self.pro.fut_daily(ts_code=ts_symbol, fields='ts_code,trade_date,open,high,low,close,vol,oi')

            if df is None or df.empty:
                logger.warning(f"未获取到期货数据: {symbol}")
                return None

            row = df.iloc[0]

            return FuturesData(
                symbol=symbol,
                name=self._get_futures_name(symbol),
                price=float(row.get('close', 0)),
                bid=float(row.get('close', 0)) - 0.5,  # 简化处理
                ask=float(row.get('close', 0)) + 0.5,
                volume=int(row.get('vol', 0)),
                open_interest=int(row.get('oi', 0)),
                timestamp=datetime.now()
            )
        except Exception as e:
            logger.error(f"获取Tushare期货数据失败 ({symbol}): {e}")
            return None

    async def get_multiple_futures_data(self, symbols: List[str]) -> List[FuturesData]:
        """获取多个期货的实时数据"""
        results = []
        for symbol in symbols:
            try:
                data = await self.get_futures_data(symbol)
                if data:
                    results.append(data)
            except Exception as e:
                logger.error(f"获取期货数据失败 ({symbol}): {e}")
                continue
        return results

    async def is_available(self) -> bool:
        """检查数据源是否可用"""
        try:
            if not self.pro:
                return False
            # 尝试获取一个简单的数据来验证连接
            df = self.pro.fut_daily(ts_code="IF2412.CFX", fields='ts_code', limit=1)
            return df is not None and not df.empty
        except Exception as e:
            logger.error(f"Tushare数据源不可用: {e}")
            return False

    @staticmethod
    def _get_futures_name(symbol: str) -> str:
        """根据代码获取期货名称"""
        names = {
            "IF": "沪深300指数期货",
            "IC": "中证500指数期货",
            "IH": "上证50指数期货",
            "T": "10年期国债期货",
            "TF": "5年期国债期货",
            "TS": "2年期国债期货",
            "CU": "铜期货",
            "AL": "铝期货",
            "ZN": "锌期货",
            "PB": "铅期货",
            "RB": "螺纹钢期货",
            "HC": "热轧卷板期货",
            "I": "铁矿石期货",
            "J": "焦炭期货",
            "M": "豆粕期货",
            "A": "豆一期货",
            "B": "豆二期货",
            "Y": "豆油期货",
            "P": "棕榈油期货",
            "OI": "菜籽油期货",
            "RM": "菜籽粕期货",
            "C": "玉米期货",
            "CF": "棉花期货",
            "SR": "白糖期货",
            "OI": "菜籽油期货",
            "TA": "PTA期货",
            "V": "聚氯乙烯期货",
            "PP": "聚丙烯期货",
            "L": "塑料期货",
            "EG": "乙二醇期货",
            "RU": "天然橡胶期货",
            "NR": "20号胶期货",
            "SC": "原油期货",
            "LU": "低硫燃料油期货",
            "NI": "镍期货",
            "SN": "锡期货",
            "AU": "黄金期货",
            "AG": "白银期货",
        }
        return names.get(symbol, f"{symbol}期货")


class AKShareFuturesAdapter(FuturesDataProvider):
    """AKShare期货数据适配器"""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        try:
            import akshare as ak
            self.ak = ak
        except ImportError:
            logger.error("AKShare库未安装")
            self.ak = None

    async def get_futures_data(self, symbol: str) -> Optional[FuturesData]:
        """获取单个期货的实时数据"""
        try:
            if not self.ak:
                logger.error("AKShare API未初始化")
                return None

            # AKShare期货代码格式：IF2412
            # 获取实时行情
            df = self.ak.futures_main_sina(symbol=symbol)

            if df is None or df.empty:
                logger.warning(f"未获取到期货数据: {symbol}")
                return None

            row = df.iloc[0]

            return FuturesData(
                symbol=symbol,
                name=self._get_futures_name(symbol),
                price=float(row.get('price', 0)),
                bid=float(row.get('bid', 0)),
                ask=float(row.get('ask', 0)),
                volume=int(row.get('volume', 0)),
                open_interest=int(row.get('open_interest', 0)),
                timestamp=datetime.now()
            )
        except Exception as e:
            logger.error(f"获取AKShare期货数据失败 ({symbol}): {e}")
            return None

    async def get_multiple_futures_data(self, symbols: List[str]) -> List[FuturesData]:
        """获取多个期货的实时数据"""
        results = []
        for symbol in symbols:
            try:
                data = await self.get_futures_data(symbol)
                if data:
                    results.append(data)
            except Exception as e:
                logger.error(f"获取期货数据失败 ({symbol}): {e}")
                continue
        return results

    async def is_available(self) -> bool:
        """检查数据源是否可用"""
        try:
            if not self.ak:
                return False
            # 尝试获取一个简单的数据来验证连接
            df = self.ak.futures_main_sina(symbol="IF2412")
            return df is not None and not df.empty
        except Exception as e:
            logger.error(f"AKShare数据源不可用: {e}")
            return False

    @staticmethod
    def _get_futures_name(symbol: str) -> str:
        """根据代码获取期货名称"""
        names = {
            "IF": "沪深300指数期货",
            "IC": "中证500指数期货",
            "IH": "上证50指数期货",
            "T": "10年期国债期货",
            "TF": "5年期国债期货",
            "TS": "2年期国债期货",
            "CU": "铜期货",
            "AL": "铝期货",
            "ZN": "锌期货",
            "PB": "铅期货",
            "RB": "螺纹钢期货",
            "HC": "热轧卷板期货",
            "I": "铁矿石期货",
            "J": "焦炭期货",
            "M": "豆粕期货",
            "A": "豆一期货",
            "B": "豆二期货",
            "Y": "豆油期货",
            "P": "棕榈油期货",
            "OI": "菜籽油期货",
            "RM": "菜籽粕期货",
            "C": "玉米期货",
            "CF": "棉花期货",
            "SR": "白糖期货",
            "OI": "菜籽油期货",
            "TA": "PTA期货",
            "V": "聚氯乙烯期货",
            "PP": "聚丙烯期货",
            "L": "塑料期货",
            "EG": "乙二醇期货",
            "RU": "天然橡胶期货",
            "NR": "20号胶期货",
            "SC": "原油期货",
            "LU": "低硫燃料油期货",
            "NI": "镍期货",
            "SN": "锡期货",
            "AU": "黄金期货",
            "AG": "白银期货",
        }
        return names.get(symbol, f"{symbol}期货")


class FuturesDataManager:
    """期货数据管理器 - 支持多数据源降级"""

    def __init__(self):
        self.providers: List[FuturesDataProvider] = []
        self.current_provider_index = 0

    def add_provider(self, provider: FuturesDataProvider) -> None:
        """添加数据提供商"""
        self.providers.append(provider)
        logger.info(f"添加期货数据提供商: {provider.name}")

    async def get_futures_data(self, symbol: str) -> Optional[FuturesData]:
        """获取期货数据，支持自动降级"""
        for i, provider in enumerate(self.providers):
            try:
                if await provider.is_available():
                    data = await provider.get_futures_data(symbol)
                    if data:
                        logger.debug(f"从 {provider.name} 获取期货数据: {symbol}")
                        return data
            except Exception as e:
                logger.warning(f"从 {provider.name} 获取期货数据失败: {e}")
                continue

        logger.error(f"无法从任何数据源获取期货数据: {symbol}")
        return None

    async def get_multiple_futures_data(self, symbols: List[str]) -> List[FuturesData]:
        """获取多个期货的数据"""
        results = []
        for symbol in symbols:
            data = await self.get_futures_data(symbol)
            if data:
                results.append(data)
        return results


# 全局数据管理器实例
_futures_data_manager: Optional[FuturesDataManager] = None


def get_futures_data_manager() -> FuturesDataManager:
    """获取期货数据管理器实例"""
    global _futures_data_manager
    if _futures_data_manager is None:
        _futures_data_manager = FuturesDataManager()
        # 添加默认提供商
        _futures_data_manager.add_provider(TushareFuturesAdapter())
        _futures_data_manager.add_provider(AKShareFuturesAdapter())
    return _futures_data_manager
