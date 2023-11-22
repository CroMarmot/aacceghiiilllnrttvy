import getpass
import json
import os
from datetime import datetime, timedelta, timezone

# from dataclasses import dataclass
from functools import cmp_to_key
from typing import Any, List

import click
import requests
from rich.console import Console
from rich.style import Style
from rich.table import Table

# Create a rich console object
console = Console()

HTTP_STATUS_OK = 200  # lint: PLR2004 Magic value used in comparison, consider replacing 200 with a constant variable
time_format = "%Y-%m-%d %H:%M:%S"
home_directory = os.path.expanduser("~")
CFG_JSON_PATH = os.path.join(home_directory, ".v2ctlcfg.json")
API_SUFFIX = "http://127.0.0.1:2017/api"
REQUESTS_TIMEOUT = 120
REQ_FAILED_EXCEPTION = "RESP FAILED"

# TODO dataclasses
TOUCH_RESULT = Any


def cmp_latency(x: str, y: str) -> int:
    if x.endswith("ms") and y.endswith("ms"):
        return int(x[:-2]) - int(y[:-2])
    if x.endswith("ms"):
        return -1
    if y.endswith("ms"):
        return 1
    return -1 if x < y else 1


def api_url(op: str) -> str:
    return f"{API_SUFFIX}/{op}"


# TODO struct with dataclasses
def ls_read():
    try:
        with open(CFG_JSON_PATH) as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}
    except Exception as e:
        console.print("Error:", e)
        data = {}
    return data


def ls_write(data):
    with open(CFG_JSON_PATH, "w") as f:
        json.dump(data, f)


def get_headers():
    headers = {}
    cfg = ls_read()
    if "token" in cfg:
        headers["Authorization"] = cfg["token"]
    return headers


def timedelta_2_hms(td: timedelta) -> str:
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


@click.group()
def cli():
    """this is the main command group"""
    pass


@cli.command()
@click.argument("username")
def login(username):
    """auth with username and password"""
    pwd = getpass.getpass(prompt="Enter your password: ")

    res = norm_resp(
        requests.post(api_url("login"), json={"username": username, "password": pwd}, timeout=REQUESTS_TIMEOUT)
    )
    console.print(f"Auth Success. token saved into ({CFG_JSON_PATH})")
    cfg = ls_read()
    cfg["token"] = res["token"]
    ls_write(cfg)


def norm_resp(resp):  # ["data"] in json
    if resp.status_code == HTTP_STATUS_OK:
        res = json.loads(resp.text)
        if res["code"] == "FAIL":
            console.print("request failed")
            raise Exception(REQ_FAILED_EXCEPTION)
        elif res["code"] == "SUCCESS":
            return res["data"]
    else:
        console.print(f"Error: {resp.status_code}")
        raise Exception(REQ_FAILED_EXCEPTION)


def touch():
    resp = requests.get(api_url("touch"), headers=get_headers(), timeout=REQUESTS_TIMEOUT)
    return resp


@cli.command("touch")
@click.option("--fast-server", default=10, help="the X fast server")
def cli_touch(fast_server: int):
    """get the list of subscription"""
    res = norm_resp(touch())

    linked_server_dict = {}

    servers = res["touch"]["connectedServer"] or []
    for server in servers:
        s_id = server["id"]
        s_sub = server["sub"]
        if s_sub not in linked_server_dict:
            linked_server_dict[s_sub] = {}
        linked_server_dict[s_sub][s_id] = True

    for sub_idx, sb in enumerate(res["touch"]["subscriptions"]):
        remarks = f'({sb["remarks"]}) ' if "remarks" in sb else ""
        servers = sorted(sb["servers"], key=cmp_to_key(lambda x, y: cmp_latency(x["pingLatency"], y["pingLatency"])))

        up_time = datetime.strptime(sb["status"], time_format).astimezone(timezone.utc)
        # DTZ005 The use of `datetime.datetime.now()` without `tz` argument is not allowed
        cur_time = datetime.now(tz=timezone.utc)

        table = Table(
            title=f"""sub_idx:{sub_idx}
{sb['host']} {remarks}
{sb['status']}({timedelta_2_hms(cur_time-up_time)} ago)
total:{len(servers)}"""
        )
        table.add_column("id", style="magenta", justify="center")
        table.add_column("Name", style="cyan", no_wrap=True, justify="center")
        table.add_column("Address", style="magenta", justify="center")
        table.add_column("net", style="magenta", justify="center")
        table.add_column("pingLatency", style="green", justify="center")

        for server in servers[:fast_server]:  # fast 10
            linked = sub_idx in linked_server_dict and server["id"] in linked_server_dict[sub_idx]
            # https://rich.readthedocs.io/en/latest/appendix/colors.html#appendix-colors
            table.add_row(
                f"{server['id']}",
                server["name"],
                server["address"],
                server["net"],
                server["pingLatency"],
                style=Style(bgcolor="grey27" if linked else None),
            )

        # Print the table
        console.print(table)


@cli.command()
def version():
    """/api/version"""

    res = norm_resp(requests.get(api_url("version"), headers=get_headers(), timeout=REQUESTS_TIMEOUT))
    console.print(json.dumps(res, indent=2, ensure_ascii=False))


@cli.command()
def outbounds():
    """/api/outbounds"""

    res = norm_resp(requests.get(api_url("outbounds"), headers=get_headers(), timeout=REQUESTS_TIMEOUT))
    console.print(json.dumps(res, indent=2, ensure_ascii=False))


def update_latency(touch_res: TOUCH_RESULT, idx: int) -> TOUCH_RESULT:
    whiches = []
    for server in touch_res["touch"]["subscriptions"][idx]["servers"]:
        # console.print(f"Test Latency: {server['name']}")
        whiches.append(
            {
                "id": server["id"],
                "_type": server["_type"],
                "sub": idx,
            }
        )
    url = f"{API_SUFFIX}/httpLatency?whiches=" + json.dumps(whiches)
    res = norm_resp(requests.get(url, headers=get_headers(), timeout=REQUESTS_TIMEOUT))

    d = {}
    for s in res["whiches"]:
        s_id = s["id"]
        d[s_id] = s["pingLatency"]

    for server in touch_res["touch"]["subscriptions"][idx]["servers"]:
        s_id = server["id"]
        if s_id in d:
            server["pingLatency"] = d[s_id]
    return touch_res


def update_subscription(subscription_id: int) -> TOUCH_RESULT:
    url = f"{API_SUFFIX}/subscription"
    return norm_resp(
        requests.put(
            url, headers=get_headers(), json={"id": subscription_id, "_type": "subscription"}, timeout=REQUESTS_TIMEOUT
        )
    )


def clear_connection(touch_res: TOUCH_RESULT, outbound_id: str) -> TOUCH_RESULT:
    servers = touch_res["touch"]["connectedServer"] or []

    for server in servers:
        if server["outbound"] == outbound_id:
            touch_res = norm_resp(
                requests.delete(
                    api_url("connection"),
                    headers=get_headers(),
                    json={
                        "id": server["id"],
                        "outbound": server["outbound"],
                        "sub": server["sub"],
                        "_type": server["_type"],
                    },
                    timeout=REQUESTS_TIMEOUT,
                )
            )
    return touch_res


def do_connection(servers: List[Any], outbound_id: str, idx: int) -> TOUCH_RESULT:
    for server in servers:
        touch_res = norm_resp(
            requests.post(
                api_url("connection"),
                headers=get_headers(),
                json={
                    "id": server["id"],
                    "outbound": outbound_id,
                    "sub": idx,  #
                    "_type": server["_type"],
                },
                timeout=REQUESTS_TIMEOUT,
            )
        )
    return touch_res


def start_server(touch_res: TOUCH_RESULT) -> TOUCH_RESULT:
    if not touch_res["running"]:
        touch_res = norm_resp(requests.post(api_url("v2ray"), headers=get_headers(), timeout=REQUESTS_TIMEOUT))
    return touch_res


@cli.command("import")
@click.argument("url")
def cli_import(url):
    """import subscription"""
    res = norm_resp(
        requests.post(api_url("import"), headers=get_headers(), json={"url": url}, timeout=REQUESTS_TIMEOUT)
    )
    console.print(res)


@cli.command("account")
@click.argument("username")
def cli_account(username: str):
    """init create account with username and password"""
    pwd = getpass.getpass(prompt="Enter your password: ")
    res = norm_resp(
        requests.post(
            api_url("account"),
            headers=get_headers(),
            json={"username": username, "password": pwd},
            timeout=REQUESTS_TIMEOUT,
        )
    )

    console.print(f"Account Create Success. token saved into ({CFG_JSON_PATH})")
    cfg = ls_read()
    cfg["token"] = res["token"]
    ls_write(cfg)


@cli.command()
@click.option("--outbound", default="proxy", help="the name of outbound")
@click.option("--sub-idx", default=0, help="subscription index")
@click.option("--sub-update-hour", default=1)
@click.option("--fast-server", default=3, help="the fast X server")
def smart(outbound: str, sub_idx: int, sub_update_hour: int, fast_server: int):
    """one key select best server (login before using this)"""
    # 更新 订阅
    touch_res: TOUCH_RESULT = norm_resp(touch())
    console.print(f"[green]Touch success ({datetime.now(tz=timezone.utc).strftime(time_format)})[/green]")

    # for sb in touch_res["touch"]["subscriptions"]:
    # TODO 目前只处理单个订阅
    sb = touch_res["touch"]["subscriptions"][sub_idx]
    # DTZ007 The use of `datetime.datetime.strptime()` without %z
    #   must be followed by `.replace(tzinfo=)` or `.astimezone()`
    up_time = datetime.strptime(sb["status"], time_format).astimezone(timezone.utc)
    # DTZ005 The use of `datetime.datetime.now()` without `tz` argument is not allowed
    cur_time = datetime.now(tz=timezone.utc)
    time_diff = cur_time - up_time
    if time_diff.seconds > 60 * 60 * sub_update_hour:
        touch_res = update_subscription(sb["id"])
        console.print("[green]Subscription updated[/green]")
    else:
        console.print(f"[green]Subscription Cached {timedelta_2_hms(time_diff)}[/green]")

    touch_res = update_latency(touch_res, sub_idx)  # [0] index
    console.print(
        f"[green]Latency update success (count: {len(touch_res['touch']['subscriptions'][sub_idx]['servers'])})[/green]"
    )

    servers: List[Any] = touch_res["touch"]["subscriptions"][sub_idx]["servers"]
    servers.sort(key=cmp_to_key(lambda x, y: cmp_latency(x["pingLatency"], y["pingLatency"])))

    # 可以切换 outbounds 来批量切换, outbounds 可以配置 测速目标点,默认是google的204
    # 断开之前连接(同 outbounds)
    touch_res = clear_connection(touch_res, outbound)
    console.print("[green]Disconnect old server success[/green]")

    # 选择最快的3个新连接
    touch_res = do_connection(servers[:fast_server], outbound, sub_idx)
    console.print(f"[green]Connect fast {fast_server} server success[/green]")
    # 如果未启动,则启动
    start_server(touch_res)
    console.print(f"[green]Server started ({datetime.now(tz=timezone.utc).strftime(time_format)})[/green]")


# TODO outbound 增删, subscription 查/删
