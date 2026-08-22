"""Streamlit chat UI for the financial analyst agent."""

import asyncio
import queue
import threading

import streamlit as st

from financial_analyst_agent.agent import build_agent, stream_query

EXAMPLE_QUERIES = [
    "What was Apple's net income based on their latest quarterly report?",
    "What are the top 5 public companies in healthcare by market cap?",
    "What was Stripe's net income last quarter?",
]


class BackgroundLoop:
    """Runs a single asyncio event loop on a dedicated thread for the life of the app.

    The agent's MCP tool connections are tied to whichever loop created them, so all
    calls must be dispatched to this one loop instead of using asyncio.run() per call.
    """

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result()

    def stream(self, agen_factory, event_queue: queue.Queue) -> None:
        """Run an async generator on the background loop, pushing each item onto a queue.

        Puts None onto the queue once the generator is exhausted (or errors), so the
        Streamlit thread can block on event_queue.get() until it sees the sentinel.
        """

        async def consume() -> None:
            try:
                async for event in agen_factory():
                    event_queue.put(event)
            except Exception as exc:
                event_queue.put({"type": "error", "content": str(exc)})
            finally:
                event_queue.put(None)

        asyncio.run_coroutine_threadsafe(consume(), self.loop)


@st.cache_resource
def get_background_loop() -> BackgroundLoop:
    return BackgroundLoop()


@st.cache_resource
def get_agent(_loop: BackgroundLoop):
    return _loop.run(build_agent())


def _format_args(args: dict, limit: int = 200) -> str:
    text = ", ".join(f"{key}={value!r}" for key, value in args.items())
    return text if len(text) <= limit else text[:limit] + "..."


st.set_page_config(page_title="Financial Analyst Agent", page_icon="📊")
st.title("📊 Financial Analyst Agent")
st.caption("Ask about public-company financials, filings, and market data.")

with st.sidebar:
    st.subheader("Example queries")
    for query in EXAMPLE_QUERIES:
        if st.button(query, use_container_width=True):
            st.session_state["pending_query"] = query
    if st.button("Clear chat", use_container_width=True):
        st.session_state["messages"] = []

if "messages" not in st.session_state:
    st.session_state["messages"] = []

loop = get_background_loop()
with st.spinner("Connecting to MCP tools...", show_time=True):
    agent = get_agent(loop)

for message in st.session_state["messages"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

query = st.chat_input("Ask a question...") or st.session_state.pop("pending_query", None)

if query:
    st.session_state["messages"].append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        answer = "The agent returned no result."
        with st.status("Working...", expanded=True) as status:
            event_queue: queue.Queue = queue.Queue()
            loop.stream(lambda: stream_query(agent, query), event_queue)

            while True:
                event = event_queue.get()
                if event is None:
                    break
                if event["type"] == "tool_calls":
                    for call in event["calls"]:
                        status.write(f"🔧 **{call['name']}**  \n`{_format_args(call['args'])}`")
                elif event["type"] == "tool_result":
                    status.write(f"✅ `{event['name']}` returned")
                elif event["type"] == "error":
                    answer = f"Error: {event['content']}"
                elif event["type"] == "final":
                    answer = event["content"]

            status.update(label="Done", state="complete")
        st.markdown(answer)
    st.session_state["messages"].append({"role": "assistant", "content": answer})
