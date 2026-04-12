from pydantic import BaseModel

class OverviewResponse(BaseModel):
    total_sections: int
    total_users: int
    active_agents: int
    suspended_agents: int
    completed_convs: int
    active_convs: int
    human_handovers: int
    knowledge_bases: int
    total_messages_sent: int
    total_tokens_used: int