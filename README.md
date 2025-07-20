# 🛡️ ProxyGuard

A Python library for managing HTTP proxies with Redis storage and smart rotation strategies.

## 📋 Prerequisites

- **Redis server** running locally or remotely
- **Webshare.io API key** from [webshare.io](https://webshare.io)

## 🚀 Installation

```bash
pip install proxyguard
```

## ⚡ Quick Start

```python
import asyncio
from proxyguard import ProxyGuard, StrategyType

async def main():
    guard = ProxyGuard(api_key="your_webshare_api_key")
    
    # Load proxies (first time only)
    await guard.initialize_proxies()
    
    # Get a smart proxy
    proxy = guard.get_proxy(strategy=StrategyType.SMART)
    
    # Use with requests
    import requests
    try:
        response = requests.get("https://httpbin.org/ip", proxies=proxy)
        guard.report_proxy(proxy, success=True)  # Report success
    except:
        guard.report_proxy(proxy, success=False)  # Report failure

asyncio.run(main())
```

## 🔧 Usage

### Initialize ProxyGuard
```python
guard = ProxyGuard(
    api_key="your_api_key",
    amount=100,           # number of proxies to fetch
    fail_count=3,         # remove proxy after 3 failures
    host="localhost",     # redis host
    port=6379            # redis port
)
```

### Get Proxies
```python
# Smart strategy (best success rate)
proxy = guard.get_proxy(strategy=StrategyType.SMART, cooldown=60)

# Random strategy
proxy = guard.get_proxy(strategy=StrategyType.RANDOM)

# Sequential strategy (round-robin)
proxy = guard.get_proxy(strategy=StrategyType.SEQUENTIAL)
```

### Report Results
```python
# Always report success/failure to maintain accuracy
guard.report_proxy(proxy, success=True)   # successful request
guard.report_proxy(proxy, success=False)  # failed request
```

### View Statistics
```python
stats = guard.get_stats()
print(f"Total proxies: {stats['total_proxies']}")
print(f"Success rate: {stats['overall_success_rate']}%")
```

### Update Proxies
```python
# Refresh proxy list with new proxies
guard.update_proxies()
```

## 🗄️ Redis Setup

**Local:**
```bash
# macOS
brew install redis && brew services start redis

# Ubuntu/Debian  
sudo apt install redis-server

# Docker
docker run -d -p 6379:6379 redis:latest
```