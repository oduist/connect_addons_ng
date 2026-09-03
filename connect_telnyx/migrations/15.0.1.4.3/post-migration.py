"""Adopt the receptionist defaults without overwriting customized prompts."""


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        UPDATE connect_telnyx_ai_assistant
           SET instructions = %s
         WHERE instructions = %s
        """,
        (
            "You are a professional voice receptionist. Be concise, "
            "transparent, and use the available Odoo tools only when they "
            "are needed.",
            "You are a helpful voice assistant. Be concise, transparent, "
            "and use the available Odoo tools only when they are needed.",
        ),
    )
    cr.execute(
        """
        UPDATE connect_telnyx_ai_assistant
           SET greeting = %s
         WHERE greeting = %s
        """,
        (
            "Hello! I can register your request or connect you with a "
            "colleague. Before I do, could you briefly tell me what you are "
            "calling about?",
            "Hello! How can I help you today?",
        ),
    )
