import streamlit as st
from travel_agent import build_graph 

st.set_page_config(page_title="旅游助手", page_icon="🧳")
st.title(" 🧳旅游助手")

@st.cache_resource
def get_graph():
    return build_graph()

graph = get_graph()

if "history" not in st.session_state:
    st.session_state.history = []

for item in st.session_state.history:
    with st.chat_message(item["role"]):
        st.markdown(item["content"])

with st.form("trip_form"):
    col1, col2 = st.columns([3, 1])
    destination = col1.text_input("目的地", placeholder="例如：杭州")
    days = col2.number_input("天数", min_value=1, max_value=30, value=3,step=1)
    submitted = st.form_submit_button("生成行程")

if submitted:
    st.session_state.history.append({
        "role": "user",
        "content": f"{destination or '（空）'} / {days} 天"
    })

    with st.chat_message("user"):
        st.markdown(f"{destination or '（空）'} / {days} 天")

    with st.chat_message("assistant"):
        with st.spinner("正在查询景点、规划路线并生成行程..."):
            result = graph.invoke({
                "destination": destination,
                "days": int(days),
                "result": "",
                "attractions": [],
                "routes": [],
            })

        # 一、显示行程结果
        st.subheader(" 旅游行程")
        st.markdown(result.get("result", "暂无行程结果"))

        # 二、显示高德搜索到的景点
        st.subheader(" 高德地图景点")

        attractions = result.get("attractions", [])

        if attractions:
            for i, place in enumerate(attractions, start=1):
                name = place.get("name") or "未命名景点"

                with st.expander(f"{i}. {name}"):
                    st.write("**地址：**", place.get("address") or "暂无地址")
                    st.write("**坐标：**", place.get("location") or "暂无坐标")
        else:
            st.info("本次没有获取到景点数据。")

        # 三、显示高德返回的驾车路线参考
        st.subheader(" 景点间驾车路线参考")

        routes = result.get("routes", [])

        if routes:
            for route in routes:
                start = route.get("from", "未知起点")
                end = route.get("to", "未知终点")

                st.markdown(f"**{start} → {end}**")

                col1, col2 = st.columns(2)

                distance = route.get("distance_km")
                duration = route.get("duration_min")

                with col1:
                    if distance is not None:
                        st.metric("驾车距离", f"{distance} 公里")
                    else:
                        st.metric("驾车距离", "暂无数据")

                with col2:
                    if duration is not None:
                        st.metric("预计驾车时间", f"{duration} 分钟")
                    else:
                        st.metric("预计驾车时间", "暂无数据")

                st.divider()
        else:
            st.info("本次没有获取到可用的路线参考数据。")

        st.caption(
            "说明：路线信息为高德返回的景点间驾车参考，"
            "不代表最终行程已完成逐段路线验证。实际路况可能变化。"
        )

    # 保存聊天历史，保留原有的对话功能
    st.session_state.history.append({
        "role": "assistant",
        "content": result.get("result", "暂无行程结果")
    })
