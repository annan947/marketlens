"""Yahoo adapter and bounded process-local cache. No downloads at import time."""
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
import logging
import re
from threading import RLock
from time import monotonic
import numpy as np
import pandas as pd
import yfinance as yf
from yfinance.exceptions import YFPricesMissingError, YFRateLimitError, YFTzMissingError
from backend.api.schemas import PriceBar, SearchResult

logger = logging.getLogger(__name__)
SYMBOL_PATTERN = r'^[A-Z0-9^][A-Z0-9.^=\-]{0,19}$'


class MarketDataError(Exception):
    def __init__(self, code, message, status=502):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


class YahooProvider:
    def __init__(self, timeout=10):
        self.timeout = timeout

    def search(self, query, limit):
        return yf.Search(query, max_results=limit, news_count=0, lists_count=0,
                         timeout=self.timeout, raise_errors=True).quotes

    def history(self, symbol, start, end):
        return yf.Ticker(symbol).history(start=start.isoformat(), end=end.isoformat(),
            interval='1d', auto_adjust=True, actions=False, keepna=True,
            timeout=self.timeout, raise_errors=True)


class MarketDataService:
    def __init__(self, provider, ttl=300, max_entries=128, clock=monotonic):
        self.provider, self.ttl, self.max_entries, self.clock = provider, ttl, max_entries, clock
        self._cache = OrderedDict()
        self._lock = RLock()

    def _cached(self, key, loader):
        # Serialize misses to avoid duplicate downloads and concurrent yfinance state changes.
        with self._lock:
            now = self.clock()
            for old_key in list(self._cache):
                if self._cache[old_key][0] <= now:
                    del self._cache[old_key]
            if key in self._cache:
                self._cache.move_to_end(key)
                return deepcopy(self._cache[key][1])
            try:
                result = loader()
            except MarketDataError:
                raise
            except YFRateLimitError as exc:
                raise MarketDataError('provider_rate_limited', 'Market-data provider is rate limited; retry later.', 503) from exc
            except (YFPricesMissingError, YFTzMissingError) as exc:
                raise MarketDataError('no_market_data', 'No price data is available for this symbol and date range.', 404) from exc
            except Exception as exc:
                logger.warning('Market-data request failed (%s)', type(exc).__name__)
                raise MarketDataError('provider_unavailable', 'Market-data provider returned an invalid response or is unavailable.', 502) from exc
            if self.ttl > 0:
                self._cache[key] = (self.clock() + self.ttl, deepcopy(result))
                while len(self._cache) > self.max_entries:
                    self._cache.popitem(last=False)
            return result

    def search(self, query, limit):
        def load():
            quotes = self.provider.search(query, limit)
            if not isinstance(quotes, list):
                raise MarketDataError('invalid_provider_data', 'Provider returned malformed search results.')
            results, seen = [], set()
            for quote in quotes:
                if not isinstance(quote, dict):
                    continue
                symbol, kind = quote.get('symbol'), quote.get('quoteType')
                if not isinstance(symbol, str) or not re.fullmatch(SYMBOL_PATTERN, symbol):
                    continue
                if kind not in ('EQUITY', 'ETF') or symbol in seen:
                    continue
                seen.add(symbol)
                name = quote.get('longname') or quote.get('shortname') or symbol
                exchange = quote.get('exchDisp') or quote.get('exchange')
                results.append(SearchResult(symbol=symbol, name=name, exchange=exchange, quote_type=kind).model_dump())
                if len(results) == limit:
                    break
            return dict(query=query, results=results, fetched_at=datetime.now(timezone.utc))
        return self._cached(('search', query, limit), load)

    def history(self, symbol, start, end):
        def load():
            frame = self.provider.history(symbol, start, end)
            if not isinstance(frame, pd.DataFrame):
                raise MarketDataError('invalid_provider_data', 'Provider returned malformed price data.')
            if frame.empty:
                raise MarketDataError('no_market_data', 'No price data is available for this symbol and date range.', 404)
            columns = ['Open', 'High', 'Low', 'Close']
            if not all(col in frame for col in columns) or not isinstance(frame.index, pd.DatetimeIndex):
                raise MarketDataError('invalid_provider_data', 'Provider returned malformed price data.')
            frame = frame.sort_index()
            if len(frame) > 3660:
                raise MarketDataError('invalid_provider_data', 'Provider returned too many price observations.')
            prices, seen = [], set()
            for timestamp, row in frame.iterrows():
                if pd.isna(timestamp):
                    raise MarketDataError('invalid_provider_data', 'Provider returned a missing observation date.')
                day = timestamp.date()  # Preserve the exchange-local trading date.
                if not start <= day < end:
                    continue
                if day in seen:
                    raise MarketDataError('invalid_provider_data', 'Provider returned duplicate daily prices.')
                seen.add(day)
                values = np.asarray([row[col] for col in columns], dtype=float)
                if not np.isfinite(values).all() or np.any(values <= 0):
                    raise MarketDataError('invalid_provider_data', 'Provider returned missing or invalid OHLC prices.')
                opening, high, low, close = values
                if low > min(opening, close) or high < max(opening, close) or low > high:
                    raise MarketDataError('invalid_provider_data', 'Provider returned inconsistent OHLC prices.')
                volume = row.get('Volume')
                if volume is not None and not pd.isna(volume):
                    volume = float(volume)
                    if not np.isfinite(volume) or volume < 0 or not volume.is_integer():
                        raise MarketDataError('invalid_provider_data', 'Provider returned invalid volume.')
                    volume = int(volume)
                else:
                    volume = None
                prices.append(PriceBar(date=day, open=opening, high=high, low=low,
                                       close=close, volume=volume).model_dump())
            if not prices:
                raise MarketDataError('no_market_data', 'No prices fall inside the requested date range.', 404)
            return dict(symbol=symbol, start=start, end=end, prices=prices,
                        fetched_at=datetime.now(timezone.utc))
        return self._cached(('history', symbol, start, end), load)
