from typing import Any, List, Mapping, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from groq import Groq
from app.core.config import settings

class GroqChatModel(BaseChatModel):
    """Custom LLM class for Groq integration."""
    
    client: Any = None
    model_name: str = "llama3-70b-8192"  # Using LLaMA 3 70B model
    temperature: float = 0.1
    max_tokens: int = 8192
    top_p: float = 0.9
    
    def __init__(self, **kwargs):
        """Initialize the Groq chat model."""
        super().__init__(**kwargs)
        self.client = Groq(api_key=settings.GROQ_API_KEY)
    
    def _convert_messages_to_prompt(self, messages: List[BaseMessage]) -> List[dict]:
        """Convert messages to Groq chat format.
        
        Args:
            messages: List of messages
            
        Returns:
            List of message dictionaries in Groq format
        """
        groq_messages = []
        for message in messages:
            if isinstance(message, SystemMessage):
                role = "system"
            elif isinstance(message, HumanMessage):
                role = "user"
            elif isinstance(message, AIMessage):
                role = "assistant"
            else:
                role = "user"
            
            groq_messages.append({
                "role": role,
                "content": message.content
            })
        return groq_messages
    
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate a response using Groq.
        
        Args:
            messages: List of messages
            stop: Optional stop sequences
            run_manager: Optional run manager
            **kwargs: Additional arguments
            
        Returns:
            ChatResult containing the generated response
        """
        try:
            groq_messages = self._convert_messages_to_prompt(messages)
            
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=groq_messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                top_p=self.top_p,
                stream=False,
                stop=stop,
            )
            
            # Create ChatGeneration object
            message = AIMessage(content=completion.choices[0].message.content)
            gen = ChatGeneration(message=message)
            
            # Return ChatResult
            return ChatResult(generations=[gen])
            
        except Exception as e:
            raise ValueError(f"Error in Groq chat completion: {str(e)}")
    
    @property
    def _llm_type(self) -> str:
        """Return the type of LLM."""
        return "groq" 