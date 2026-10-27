import os
import requests
from typing import TypedDict
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END

# 1. 读取项目目录中的 .env 文件
load_dotenv()


# 2. 定义旅游助手需要保存的数据
class TravelState(TypedDict):
    destination: str
    days: int
    result: str
    attractions: list[dict]


# 3. 检查用户输入
def check_input(state: TravelState):
    destination = state.get("destination") or ""
    days = state.get("days")

    if not isinstance(destination, str):
        return {"result": "目的地必须是文本"}

    destination = destination.strip()

    if not destination:
        return {"result": "目的地不能为空"}

    if len(destination) > 50:
        return {"result": "目的地名称不能超过 50 个字符"}

    # bool 在 Python 中属于 int 的子类，因此单独排除
    if isinstance(days, bool) or not isinstance(days, int):
        return {"result": "旅行天数必须是整数"}

    if days < 1 or days > 30:
        return {"result": "旅行天数必须在 1 到 30 天之间"}

    return {"result": ""}

# 4：调用高德 API 搜索景点
def search_attractions(state: TravelState):
    api_key = os.getenv("AMAP_API_KEY")

    if not api_key:
        return {
            "result": "未读取到 AMAP_API_KEY，请检查项目中的 .env 文件",
            "attractions": [],
        }

    url = "https://restapi.amap.com/v5/place/text"

    params = {
        "key": api_key,
        "keywords": "景点",
        "region": state["destination"],
        "city_limit": "true",
        "page_size": 10,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "1":
            print("高德 API 错误：", data.get("info"))
            return {
                "result": "高德地点搜索失败，请检查 API 权限或接口返回信息",
                "attractions": [],
            }

        # 提取后续规划真正需要的信息
        attractions = []

        for place in data.get("pois", []):
            attractions.append({
                "name": place.get("name", ""),
                "address": place.get("address", ""),
                "location": place.get("location", ""),
            })

        if not attractions:
            return {
                "result": "高德没有搜索到景点，请检查目的地名称后重试",
                "attractions": [],
            }

        print(f"高德搜索成功，共获取 {len(attractions)} 个地点")

        return {
            "attractions": attractions,
            "result": "",
        }

    except Exception as e:
        print(f"高德搜索异常：{type(e).__name__}: {e}")
        return {
            "result": "高德地点搜索异常，请检查网络和控制台错误信息",
            "attractions": [],
        }


# 5. 调用 DeepSeek 生成行程
def plan_trip(state: TravelState):
    try:
        # 先检查 API Key 是否存在
        api_key = os.getenv("DEEPSEEK_API_KEY")

        if not api_key:
            return {
                "result": "未读取到 DEEPSEEK_API_KEY，请检查项目中的 .env 文件"
            }

        # 在调用节点中初始化模型
        llm = ChatOpenAI(
            model="deepseek-chat",
            api_key=api_key,
            base_url="https://api.deepseek.com",
            temperature=0.7,
        )

        # 把高德搜索结果整理成文本，交给大模型
        attractions_text = "\n".join(
            [
                f"- 景点：{place['name']}；"
                f"地址：{place['address']}；"
                f"坐标：{place['location']}"
                for place in state.get("attractions", [])
            ]
        )

        prompt = f"""
        你是一名旅游规划助手。

        用户目的地：{state['destination']}
        旅行天数：{state['days']} 天

        以下是高德地图 API 实际返回的地点候选数据：
        {attractions_text}

        请根据用户需求制定旅游行程。

        要求：
        1. 按天组织行程，每天分为上午、下午、晚上。
        2. 优先从上面的地点候选列表中选择景点。
        3. 不得声称已核实景点开放时间、票价或实时交通情况。
        4. 不要编造高德 API 没有提供的地址、坐标或路线距离。
        5. 如果候选景点不足以安排全部天数，请明确说明，
           不要为了凑够行程而编造已查询的地点。
        6. 每天安排适量活动，避免行程过度紧凑。
        7. 不要重复安排相同景点。

        请使用清晰的中文标题和列表输出。
        """

        response = llm.invoke(prompt)
        return {"result": response.content}

    except Exception as e:
        # 详细错误留在开发终端中，便于排查
        print(f"行程生成异常：{type(e).__name__}: {e}")

        return {
            "result": (
                "行程生成失败。请检查网络连接、API Key、"
                "模型服务状态及控制台错误信息，然后重试。"
            )
        }


# 6. 根据输入检查结果决定下一步
def route_after_check(state: TravelState):
    if state.get("result"):
        return "fail"

    return "ok"
def route_after_search(state: TravelState):
    if state.get("result"):
        return "fail"

    return "ok"

# 7. 构建 LangGraph 工作流
def build_graph():
    graph = StateGraph(TravelState)

    graph.add_node("check_input", check_input)
    graph.add_node("search_attractions", search_attractions)
    graph.add_node("plan_trip", plan_trip)

    graph.add_edge(START, "check_input")

    # 输入校验失败就结束，成功才继续
    graph.add_conditional_edges(
        "check_input",
        route_after_check,
        {
            "ok": "search_attractions",
            "fail": END,
        },
    )

    # 高德搜索失败就结束，成功才生成行程
    graph.add_conditional_edges(
        "search_attractions",
        route_after_search,
        {
            "ok": "plan_trip",
            "fail": END,
        },
    )

    graph.add_edge("plan_trip", END)

    return graph.compile()
# 8. 本地测试
if __name__ == "__main__":
    graph = build_graph()

    test_cases = [
        {"destination": "杭州", "days": 3, "result": ""},
        {"destination": "", "days": 3, "result": ""},
        {"destination": "成都", "days": 0, "result": ""},
        {"destination": "苏州", "days": 3.5, "result": ""},
    ]

    for case in test_cases:
        result = graph.invoke(case)

        print(
            f"[{case['destination'] or '空'} / "
            f"{case['days']} 天] -> "
            f"{result['result']}\n"
        )