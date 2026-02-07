from collections import defaultdict, deque

class ConversationStorage:
    def __init__(self, max_pairs=2):
        self.storage = defaultdict(lambda: deque(maxlen=max_pairs * 2))
        self.max_pairs = max_pairs
    
    def add_message(self, user_id: int, role: str, content: str):
        """Добавить сообщение в историю"""
        self.storage[user_id].append({"role": role, "content": content})
    
    def get_history(self, user_id: int) -> list:
        """Получить историю диалога"""
        return list(self.storage[user_id])
    
    def get_formatted_history(self, user_id: int) -> str:
        """Получить историю в XML формате"""
        history = self.get_history(user_id)
        if not history:
            return ""
        
        formatted = []
        for msg in history:
            role = "Пользователь" if msg["role"] == "user" else "Ассистент"
            formatted.append(f"{role}: {msg['content']}")
        
        return "\n".join(formatted)
    
    def clear_history(self, user_id: int):
        """Очистить историю пользователя"""
        if user_id in self.storage:
            del self.storage[user_id]

# Создаем глобальный объект, который будем импортировать
conversation_storage = ConversationStorage(max_pairs=2)

