from email_rag.rag.conversation import ConversationMemory


class TestConversationMemory:
    def test_add_and_get(self):
        mem = ConversationMemory(max_turns=5)
        mem.add_turn("s1", "Hello", "Hi there!")
        history = mem.get_history("s1")
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"

    def test_max_turns(self):
        mem = ConversationMemory(max_turns=2)
        mem.add_turn("s1", "Q1", "A1")
        mem.add_turn("s1", "Q2", "A2")
        mem.add_turn("s1", "Q3", "A3")
        turns = mem.get_turns("s1")
        assert len(turns) == 2
        assert turns[0].user_query == "Q2"

    def test_clear_session(self):
        mem = ConversationMemory()
        mem.add_turn("s1", "Q", "A")
        mem.clear_session("s1")
        assert not mem.has_session("s1")

    def test_separate_sessions(self):
        mem = ConversationMemory()
        mem.add_turn("s1", "Q1", "A1")
        mem.add_turn("s2", "Q2", "A2")
        assert len(mem.get_turns("s1")) == 1
        assert len(mem.get_turns("s2")) == 1

    def test_empty_session(self):
        mem = ConversationMemory()
        assert mem.get_history("nonexistent") == []
        assert not mem.has_session("nonexistent")
