from typing import Optional


class AIDataScienceTeamError(Exception):
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class AgentError(AIDataScienceTeamError):
    pass


class AgentExecutionError(AgentError):
    def __init__(self, message: str, code: Optional[str] = None, retry_count: int = 0):
        super().__init__(message, {"code": code, "retry_count": retry_count})
        self.code = code
        self.retry_count = retry_count


class AgentCodeGenerationError(AgentError):
    def __init__(self, message: str, code_snippet: Optional[str] = None):
        super().__init__(message, {"code_snippet": code_snippet})
        self.code_snippet = code_snippet


class PipelineStudioError(AIDataScienceTeamError):
    pass


class ProjectNotFoundError(PipelineStudioError):
    def __init__(self, project_dir: str):
        super().__init__(f"Project not found: {project_dir}", {"project_dir": project_dir})
        self.project_dir = project_dir


class ProjectSaveError(PipelineStudioError):
    def __init__(self, project_name: str, cause: str):
        super().__init__(
            f"Failed to save project '{project_name}': {cause}", {"project_name": project_name}
        )
        self.project_name = project_name


class DatasetNotFoundError(PipelineStudioError):
    def __init__(self, dataset_id: str):
        super().__init__(f"Dataset not found: {dataset_id}", {"dataset_id": dataset_id})
        self.dataset_id = dataset_id


class UndoNotSupportedError(PipelineStudioError):
    def __init__(self, action_type: str):
        super().__init__(
            f"Undo not implemented for action type '{action_type}'", {"action_type": action_type}
        )
        self.action_type = action_type


class StateValidationError(AIDataScienceTeamError):
    pass


class ConfigurationError(AIDataScienceTeamError):
    pass


class ConnectionError(AIDataScienceTeamError):
    pass


class SQLConnectionError(ConnectionError):
    def __init__(self, url: str, cause: str):
        super().__init__(f"Failed to connect to SQL database: {cause}", {"url": url})
        self.url = url


class FileLoadError(ConnectionError):
    def __init__(self, file_path: str, cause: str):
        super().__init__(f"Failed to load file: {cause}", {"file_path": file_path})
        self.file_path = file_path


class WorkflowError(AIDataScienceTeamError):
    pass


class WorkflowRoutingError(WorkflowError):
    def __init__(self, message: str, available_workers: list[str]):
        super().__init__(message, {"available_workers": available_workers})
        self.available_workers = available_workers


class IntentParsingError(WorkflowError):
    def __init__(self, message: str, user_input: str):
        super().__init__(message, {"user_input": user_input})
        self.user_input = user_input
