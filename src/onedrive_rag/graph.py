"""LangGraph のワークフロー（1 質問受付 → 2 分類 → 3 振り分け → 4 回答作成 → 5 回答）"""
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from openai import OpenAI

from onedrive_rag import config, retriever

client = OpenAI()


class State(TypedDict, total=False):
    question: str
    category: str
    confidence: float
    folder: str
    contexts: list[dict]
    answer: str


# 1. 質問を受け取る
def receive_question(state: State) -> State:
    return {"question": state["question"].strip()}


# 2. OpenAI Decisions API で分類する
def classify(state: State) -> State:
    choices = [
        {"value": key, "description": c["description"]}
        for key, c in config.CATEGORIES.items()
    ]
    choices.append({"value": "other", "description": "上記のどれにも当てはまらない質問"})

    decision = client.decisions.create(
        model=config.DECISION_MODEL,
        input=state["question"],
        questions=[
            {
                "type": "choice",
                "name": "folder",
                "instructions": "この質問に答えるための資料が入っている部署フォルダを選んでください。",
                "choices": choices,
            }
        ],
    )
    answer = decision.answers[0]
    if answer.type != "choice":  # refusal（回答拒否）の場合
        return {"category": "other", "confidence": 0.0}
    return {"category": answer.choice, "confidence": answer.confidence}


def route(state: State) -> str:
    """分類結果で次のノードを決める（条件分岐）"""
    if state["category"] == "other" or state["confidence"] < config.MIN_CONFIDENCE:
        return "fallback"
    return "retrieve"


# 3. 該当フォルダに割り振り、文章を検索する
def retrieve(state: State) -> State:
    folder = config.CATEGORIES[state["category"]]["folder"]
    return {"folder": folder, "contexts": retriever.search(state["question"], folder)}


# 4. 文章から回答を作成する
def generate(state: State) -> State:
    if not state["contexts"]:
        return {"answer": f"「{state['folder']}」フォルダに参照できる文書がありませんでした。"}

    context = "\n\n".join(
        f"[資料{i}: {c['source']}]\n{c['text']}" for i, c in enumerate(state["contexts"], 1)
    )
    response = client.responses.create(
        model=config.ANSWER_MODEL,
        instructions=(
            "あなたは社内文書に基づいて回答するアシスタントです。"
            "必ず与えられた資料の内容だけを使って日本語で答えてください。"
            "資料に答えがない場合は「資料に記載がありません」と答えてください。"
            "回答の根拠にした資料番号を [資料1] のように示してください。"
        ),
        input=f"# 資料\n{context}\n\n# 質問\n{state['question']}",
        store=False,  # 社内文書と質問を OpenAI 側に保存しない（省略すると保存される）
    )
    return {"answer": response.output_text}


def fallback(state: State) -> State:
    return {
        "folder": "",
        "contexts": [],
        "answer": "どのフォルダの資料で答えるべきか判断できませんでした。質問をもう少し具体的にしてください。",
    }


# 5. ユーザーに回答する（出典を付けて整形）
def respond(state: State) -> State:
    answer = state["answer"]
    if state.get("contexts"):
        sources = sorted({c["source"] for c in state["contexts"]})
        answer += "\n\n参照: " + state["folder"] + " / " + ", ".join(sources)
    return {"answer": answer}


def build_graph():
    g = StateGraph(State)
    g.add_node("receive_question", receive_question)
    g.add_node("classify", classify)
    g.add_node("retrieve", retrieve)
    g.add_node("generate", generate)
    g.add_node("fallback", fallback)
    g.add_node("respond", respond)

    g.add_edge(START, "receive_question")
    g.add_edge("receive_question", "classify")
    g.add_conditional_edges("classify", route, {"retrieve": "retrieve", "fallback": "fallback"})
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", "respond")
    g.add_edge("fallback", "respond")
    g.add_edge("respond", END)
    return g.compile()
