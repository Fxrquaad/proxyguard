import redis
import sys
import asyncio
import aiohttp
import enum
import random
import time
import math


class StrategyType(enum.Enum):
    RANDOM = "random"
    SMART = "smart"
    SEQUENTIAL = "sequential"


class ProxyGuard:

    def __init__(
        self,
        api_key: str = None,
        amount: int = 250,
        fail_count: int = 3,
        host="localhost",
        port=6379,
        db=0,
        password: str = None,
    ):
        """
        A proxy management class that handles fetching, storing, and managing HTTP proxies
        using Redis for storage and Webshare.io API as the proxy source.
        """

        # proxy config
        self.api_key = api_key
        self.amount = amount
        self.fail_count = fail_count

        # redis config
        self.redis_host = host
        self.redis_port = port
        self.redis_db = db
        self.redis_password = password

        # utils
        self._sequential_index = 0

        self.__setup()

    def __setup(self):
        """
        Establish Redis connection. Exit if connection fails.
        """

        try:
            self.redis = redis.Redis(
                host=self.redis_host, port=self.redis_port, db=self.redis_db
            )
            if self.redis.ping():
                if self.redis.llen("proxy_list") == 0:
                    print(
                        "No proxies found in Redis. Run initialize_proxies() to load them."
                    )
            else:
                raise redis.ConnectionError("Redis ping failed")

        except redis.ConnectionError:
            print("Redis connection failed.")
            sys.exit(1)

    async def initialize_proxies(self):
        """
        Load proxies from Webshare if Redis proxy list is empty.
        """

        if self.redis.llen("proxy_list") == 0:
            await self._load_proxies()

    def _format_proxy(self, proxy):
        """
        Format the proxy as a dict for requests.
        """

        if not proxy or not isinstance(proxy, str):
            raise ValueError("Proxy must be a non-empty string")

        proxy.strip()
        if not proxy:
            raise ValueError("Proxy cannot be empty or whitespace only")

        if proxy.startswith("http://") or proxy.startswith("https://"):
            return {"http": proxy, "https": proxy}
        else:
            return {"http": f"http://{proxy}", "https": f"http://{proxy}"}

    def update_proxies(self):
        asyncio.run(self._update_proxies_async())

    async def _update_proxies_async(self):
        """
        Update the proxy list, deleting old proxies and loading new ones.
        """

        for key in self.redis.keys("proxy:*"):
            self.redis.delete(key)
        self.redis.delete("proxy_list")

        tasks = []
        total_pages = max(1, (self.amount + 249) // 250)

        for page in range(1, total_pages + 1):
            tasks.append(asyncio.create_task(self._load_proxies(page)))

        await asyncio.gather(*tasks)

    async def _load_proxies(self, page: int):
        """
        Fetch and store valid proxies from Webshare.io.
        """

        if self.api_key is None:
            raise Exception(
                "API Key is not set. Please set it before calling this method."
            )

        headers = {"Authorization": self.api_key}
        url = f"https://proxy.webshare.io/api/proxy/list/?page_size=250&page={page}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200 and "json" in resp.headers["Content-Type"]:
                    data = await resp.json()
                else:
                    raise Exception(f"Failed to fetch proxies: {resp.status}")

                if "results" in data:
                    results = data["results"]
                    for result in results:
                        valid = result["valid"]
                        if not valid:
                            continue

                        username = result["username"]
                        password = result["password"]
                        ip = result["proxy_address"]
                        port = result["ports"]["http"]

                        proxy = f"{username}:{password}@{ip}:{port}"
                        key = f"proxy:{proxy}"

                        if not self.redis.exists(key):
                            self.redis.hset(
                                key,
                                mapping={"success": 0, "failure": 0, "timestamp": 0},
                            )
                            self.redis.lpush("proxy_list", proxy)
                    print(f"Loaded {len(results)} proxies from Webshare.io")
                else:
                    raise Exception("No proxy results found in API response")

    def _get_timestamp(self, proxy):
        """
        Retrieve the last recorded timestamp for the given proxy from Redis.
        """

        key = f"proxy:{proxy}"
        return self.redis.hget(key, "timestamp")

    def _set_timestamp(self, proxy):
        """
        Update the timestamp for the given proxy in Redis to the current time.
        """

        key = f"proxy:{proxy}"
        self.redis.hset(key, "timestamp", int(time.time()))

    def _check_cooldown(self, proxy):
        """
        Return True if proxy's cooldown has passed, else False.
        """

        timestamp = int(self._get_timestamp(proxy) or 0)
        return (time.time() - timestamp) >= self.cooldown

    def _get_all_proxies(self):
        """
        Get all proxy strings from Redis list.
        """

        proxies = self.redis.lrange("proxy_list", 0, -1)
        return [proxy.decode() for proxy in proxies]

    def _get_smart_proxy(self):
        """
        Get the proxy with the highest success rate.
        """

        proxies = self._get_all_proxies()
        proxies = [p for p in proxies if self._check_cooldown(p)]
        if not proxies:
            return None

        def score(proxy):
            stats = self.redis.hgetall(f"proxy:{proxy}")
            success = int(stats.get(b"success", 0))
            failure = int(stats.get(b"failure", 0))
            return success / (success + failure + 0.1)

        proxy = max(proxies, key=score)
        self._set_timestamp(proxy)

        return proxy

    def _get_random_proxy(self):
        """
        Get a random proxy from the list.
        """

        proxies = self._get_all_proxies()
        proxies = [p for p in proxies if self._check_cooldown(p)]
        if not proxies:
            return None

        proxy = random.choice(proxies)
        self._set_timestamp(proxy)

        return proxy

    def _get_sequential_proxy(self):
        """
        Get proxies sequentially in round-robin order.
        """

        proxies = self._get_all_proxies()
        proxies = [p for p in proxies if self._check_cooldown(p)]
        total = len(proxies)
        if total == 0:
            return None

        proxy = proxies[self._sequential_index % total]
        self._sequential_index = (self._sequential_index + 1) % total
        self._set_timestamp(proxy)

        return proxy

    def _extract_proxy_string(self, proxy_input):
        """
        Normalize proxy input. Accepts string or dict and returns proxy string (user:pass@ip:port).
        """

        if isinstance(proxy_input, dict):
            proxy_url = proxy_input.get("http") or proxy_input.get("https")
            if not proxy_url:
                raise ValueError("Invalid proxy dict format")

            if proxy_url.startswith("http://"):
                proxy_url = proxy_url[len("http://") :]
            elif proxy_url.startswith("https://"):
                proxy_url = proxy_url[len("https://") :]
            return proxy_url
        elif isinstance(proxy_input, str):
            return proxy_input.strip()
        else:
            raise TypeError("Proxy must be a string or dict with 'http'/'https' keys")

    def report_proxy(self, proxy, success: bool):
        """
        Report a successful request with the proxy
        """

        proxy = self._extract_proxy_string(proxy)
        key = f"proxy:{proxy}"

        if success:
            self.redis.hincrby(key, "success", 1)
        else:
            failure_count = self.redis.hincrby(key, "failure", 1)

            # Remove proxy if it exceeds failure count
            if failure_count >= self.fail_count:
                self._remove_bad_proxy(proxy)

    def _remove_bad_proxy(self, proxy: str):
        """
        Remove a bad proxy from Redis storage
        """

        key = f"proxy:{proxy}"
        self.redis.delete(key)
        self.redis.lrem("proxy_list", 0, proxy)

    def get_proxy(self, strategy=StrategyType.SMART, cooldown: int = 60):
        """
        Get a proxy based on the configured strategy
        """

        self.cooldown = cooldown

        if strategy == StrategyType.SMART:
            proxy = self._get_smart_proxy()
        elif strategy == StrategyType.RANDOM:
            proxy = self._get_random_proxy()
        elif strategy == StrategyType.SEQUENTIAL:
            proxy = self._get_sequential_proxy()
        else:
            proxy = self._get_smart_proxy()

        return self._format_proxy(proxy)

    def get_stats(self):
        """
        Get statistics about proxy usage
        """

        proxies = self._get_all_proxies()
        proxy_details = {}
        total_success = 0
        total_failure = 0
        bad_proxies = 0

        for proxy in proxies:
            key = f"proxy:{proxy}"
            proxy_stats = self.redis.hgetall(key)
            success = int(proxy_stats.get(b"success", 0))
            failure = int(proxy_stats.get(b"failure", 0))

            total_success += success
            total_failure += failure

            if failure >= self.fail_count:
                bad_proxies += 1

            proxy_details[proxy] = {
                "success": success,
                "failure": failure,
                "total": success + failure,
                "success_rate": round(
                    (
                        (success / (success + failure) * 100)
                        if (success + failure) > 0
                        else 0
                    ),
                    2,
                ),
            }

        return {
            "total_proxies": len(proxies),
            "good_proxies": len(proxies) - bad_proxies,
            "bad_proxies": bad_proxies,
            "total_requests": total_success + total_failure,
            "total_success": total_success,
            "total_failure": total_failure,
            "overall_success_rate": round(
                (
                    (total_success / (total_success + total_failure) * 100)
                    if (total_success + total_failure) > 0
                    else 0
                ),
                2,
            ),
            "proxy_details": proxy_details,
        }
