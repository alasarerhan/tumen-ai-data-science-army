def get_tool_call_names(messages):
    """
    Method to extract the tool name from a list of Langchain messages

    Parameters
    -----------
    messages: list
        A list of Langchain messages

    Returns
    --------
    tool_calls: list
        A list of tool call names.
    """
    tool_calls = []
    for message in messages:
        try:
            if "tool_call_id" in list(dict(message).keys()):
                tool_calls.append(message.name)
        except Exception:
            pass
    return tool_calls
