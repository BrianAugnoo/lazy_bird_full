from lazy_bird.crud import agent as agent_crud
from lazy_bird.inference.types import ChatResult
from lazy_bird.schemas.agent import AgentIn


def make_agent(client, master: bool = True) -> dict:
    session = client.post("/sessions/", json={"title": "s"}).json()
    return agent_crud.create(AgentIn(name="agent", session_id=session["id"], master=master, instructions="Help.")).model_dump()


def test_a_conversation_is_streamed_over_the_websocket(client, fake_inference):
    fake_inference.script = [ChatResult(content="Hello you")]
    agent = make_agent(client)
    conversation = client.post("/conversations/", json={"agent_id": agent["id"]}).json()

    with client.websocket_connect(f"/ws/conversations/{conversation['id']}") as socket:
        assert socket.receive_json()["type"] == "conversation"
        socket.send_json({"type": "message", "content": "Hi"})
        events = []
        while not events or events[-1]["type"] != "done":
            events.append(socket.receive_json())

    kinds = [event["type"] for event in events]
    assert kinds[0] == "message" and events[0]["message"]["role"] == "user"
    assert [event["delta"] for event in events if event["type"] == "token"] == ["Hello", " you"]
    assert events[-1] == {"type": "done", "reason": "completed"}
    assert client.get(f"/conversations/{conversation['id']}").json()["messages"][-1]["content"] == "Hello you"


def test_websocket_refuses_to_answer_without_a_user_message(client, fake_inference):
    agent = make_agent(client)
    conversation = client.post("/conversations/", json={"agent_id": agent["id"]}).json()

    with client.websocket_connect(f"/ws/conversations/{conversation['id']}") as socket:
        socket.receive_json()
        socket.send_json({"type": "run"})
        assert socket.receive_json()["error"]["code"] == "nothing_to_answer"
        socket.send_json({"type": "dance"})
        assert socket.receive_json()["error"]["code"] == "invalid_command"


def test_the_session_master_receives_chats(client, fake_inference):
    fake_inference.script = [ChatResult(content="Answer")]
    agent = make_agent(client)

    conversation = client.post(f"/sessions/{agent['session_id']}/chat", json={"content": "Question"}).json()
    run = client.post(f"/conversations/{conversation['id']}/run").json()
    again = client.post(f"/sessions/{agent['session_id']}/chat", json={"content": "Follow-up"}).json()

    assert conversation["agent_id"] == agent["id"] and conversation["runnable"] is True
    assert run["reason"] == "completed" and run["messages"][-1]["content"] == "Answer"
    assert again["id"] == conversation["id"]


def test_sessions_without_master_say_so(client, fake_inference):
    agent = make_agent(client, master=False)

    response = client.post(f"/sessions/{agent['session_id']}/chat", json={"content": "Hi"})

    assert response.status_code == 409 and response.json()["error"]["code"] == "no_master_agent"


def test_editing_and_rewinding_lets_the_agent_answer_again(client, fake_inference):
    fake_inference.script = [ChatResult(content="First"), ChatResult(content="Second")]
    agent = make_agent(client)
    conversation = client.post("/conversations/", json={"agent_id": agent["id"]}).json()
    prompt = client.post(f"/conversations/{conversation['id']}/messages", json={"content": "Hi"}).json()
    client.post(f"/conversations/{conversation['id']}/run")

    assert client.post(f"/conversations/{conversation['id']}/run").json()["error"]["code"] == "nothing_to_answer"
    assert client.patch(f"/messages/{prompt['id']}", json={"content": "Hello"}).json()["content"] == "Hello"
    rewound = client.post(f"/conversations/{conversation['id']}/rewind", json={"message_id": prompt["id"]}).json()
    assert rewound["runnable"] is True and rewound["messages"][-1]["content"] == "Hello"
    assert client.post(f"/conversations/{conversation['id']}/run").json()["messages"][-1]["content"] == "Second"


def test_only_the_last_message_can_be_deleted_and_assistants_cannot_be_edited(client, fake_inference):
    fake_inference.script = [ChatResult(content="Answer")]
    agent = make_agent(client)
    conversation = client.post("/conversations/", json={"agent_id": agent["id"]}).json()
    prompt = client.post(f"/conversations/{conversation['id']}/messages", json={"content": "Hi"}).json()
    answer = client.post(f"/conversations/{conversation['id']}/run").json()["messages"][-1]

    assert client.delete(f"/messages/{prompt['id']}").json()["error"]["code"] == "message_not_last"
    assert client.patch(f"/messages/{answer['id']}", json={"content": "x"}).json()["error"]["code"] == "message_not_editable"
    assert client.delete(f"/messages/{answer['id']}").status_code == 204


def test_presets_can_be_tested_with_a_single_completion(client, fake_inference):
    fake_inference.script = [ChatResult(content="pong")]

    response = client.post("/inference/complete", json={"prompt": "ping"})

    assert response.json()["content"] == "pong"


def test_timestamps_are_sent_in_utc_with_their_offset(client, fake_inference):
    from datetime import datetime, timedelta, timezone

    agent = make_agent(client)
    conversation = client.post("/conversations/", json={"agent_id": agent["id"]}).json()
    session = client.get(f"/sessions/{agent['session_id']}").json()

    for value in (conversation["created_at"], session["updated_at"]):
        parsed = datetime.fromisoformat(value)
        assert parsed.utcoffset() == timedelta(0)
        assert abs(datetime.now(timezone.utc) - parsed) < timedelta(minutes=1)
